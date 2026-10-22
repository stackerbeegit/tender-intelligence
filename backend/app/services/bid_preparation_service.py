"""
Bid preparation for an opportunity: the submission checklist (built from
the tender's verified `tender_submission_documents`, pre-filled from the
company profile) and versioned AI draft bids (app/bidding/draft.py).

`prepare_bid` is what a sales user's "Interested — prepare bid" runs: it
makes sure the tender is an opportunity with the user assigned, syncs the
checklist and tries to generate a draft. It does not move the workflow —
the bid / no-bid decision stays a separate, human step — and nothing here
submits anything.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.bidding import checklist as checklist_rules
from app.bidding import draft as draft_rules
from app.bidding import export
from app.core.exceptions import DomainError, LLMNotConfiguredError, LLMResponseError
from app.core.logging import get_logger
from app.intelligence.llm import LLMClient, get_llm_client
from app.matching.text import format_inr
from app.models.bid_checklist_item import BidChecklistItem
from app.models.bid_draft import BidDraft
from app.models.enums import ChecklistItemStatus, SubmissionDocumentKind
from app.models.opportunity import Opportunity
from app.models.stackerbee_profile import StackerbeeProfile
from app.models.tender import Tender
from app.models.user import User
from app.services import audit_service, opportunity_service, profile_service, qualification_service
from app.services.profile_service import ProfileNotConfiguredError

logger = get_logger(__name__)


class TenderNotAnalysedError(DomainError):
    pass


@dataclass
class PreparationOutcome:
    opportunity: Opportunity
    created: bool
    draft: BidDraft | None
    draft_error: str | None
    draft_problems: list[str]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _date(value: datetime | None) -> str | None:
    return value.strftime("%d %b %Y %H:%M") if value else None


# ------------------------------------------------------------- checklist


def sync_checklist(db: Session, opportunity: Opportunity) -> list[BidChecklistItem]:
    """Adds an item for every submission-document fact not yet on the
    checklist, re-links items whose fact was replaced by a re-analysis, and
    refreshes the pre-filled status of items nobody has edited. Statuses a
    person set are never overwritten; manual items are left alone."""
    tender = opportunity.tender
    profile_row = profile_service.get_profile(db)
    profile = qualification_service.company_profile(profile_row) if profile_row else None
    msme_ref = profile_row.msme_certificate_ref if profile_row else None
    startup_ref = profile_row.startup_certificate_ref if profile_row else None

    items = list(opportunity.checklist_items)
    by_fact = {item.submission_document_id: item for item in items if item.submission_document_id}
    by_clause = {checklist_rules.match_key(item.source_clause): item for item in items if not item.is_manual}
    next_position = max((item.position for item in items), default=0) + 1

    for fact in tender.submission_documents:
        item = by_fact.get(fact.id) or by_clause.get(checklist_rules.match_key(fact.clause_text))
        if item is None:
            item = BidChecklistItem(position=next_position, is_manual=False, status_set_by_user=False)
            next_position += 1
            opportunity.checklist_items.append(item)
        item.submission_document_id = fact.id
        item.title = fact.document_name
        item.kind = fact.kind
        item.mandatory = fact.mandatory
        item.format_instructions = fact.format_instructions
        item.form_reference = fact.form_reference
        item.source_clause = fact.clause_text
        item.source_document_id = fact.document_id
        item.source_file_name = fact.document.file_name
        item.source_page = fact.page_number
        if not item.status_set_by_user:
            item.status, item.prefill_reason = checklist_rules.prefill(
                fact.kind, fact.clause_text, profile, msme_ref, startup_ref
            )
    db.commit()
    db.refresh(opportunity)
    return list(opportunity.checklist_items)


def add_manual_item(db: Session, opportunity: Opportunity, title: str, user: User) -> BidChecklistItem:
    item = BidChecklistItem(
        position=max((i.position for i in opportunity.checklist_items), default=0) + 1,
        title=title.strip()[:500],
        kind=SubmissionDocumentKind.OTHER,
        is_manual=True,
        status=ChecklistItemStatus.TO_PREPARE,
        status_set_by_user=False,
    )
    opportunity.checklist_items.append(item)
    db.commit()
    db.refresh(item)
    audit_service.record(
        db, action="bid.checklist_item_added", user_id=user.id, entity_type="opportunity",
        entity_id=str(opportunity.id), details={"title": item.title},
    )
    return item


def update_item(db: Session, item: BidChecklistItem, changes: dict, user: User) -> BidChecklistItem:
    if "status" in changes and changes["status"] is not None:
        item.status = changes["status"]
        item.status_set_by_user = True
    if "owner_id" in changes:
        item.owner_id = changes["owner_id"]
    if "note" in changes:
        item.note = (changes["note"] or "").strip() or None
    db.commit()
    db.refresh(item)
    audit_service.record(
        db, action="bid.checklist_item_updated", user_id=user.id, entity_type="bid_checklist_item",
        entity_id=str(item.id), details={k: str(v) if v is not None else None for k, v in changes.items()},
    )
    return item


def checklist_rows(opportunity: Opportunity) -> list[dict]:
    return [
        {
            "title": i.title,
            "kind": i.kind.value,
            "mandatory": i.mandatory,
            "format_instructions": i.format_instructions,
            "form_reference": i.form_reference,
            "source_clause": i.source_clause,
            "source_file_name": i.source_file_name,
            "source_page": i.source_page,
            "status": i.status.value,
            "owner": i.owner.full_name if i.owner else None,
            "note": i.note,
            "prefill_reason": i.prefill_reason,
        }
        for i in opportunity.checklist_items
    ]


# ----------------------------------------------------------------- draft


def _tender_summary(tender: Tender) -> dict:
    return {
        "title": tender.title,
        "tender_number": tender.tender_number,
        "organisation": tender.organisation.name if tender.organisation else None,
        "closing_date": _date(tender.closing_date),
        "tender_value": format_inr(float(tender.tender_value)) if tender.tender_value is not None else None,
        "emd": format_inr(float(tender.emd_amount)) if tender.emd_amount is not None else None,
    }


def _citation(row) -> dict:
    return {"document_id": str(row.document_id), "file_name": row.document.file_name, "page_number": row.page_number}


def build_inputs(tender: Tender, profile: StackerbeeProfile, opportunity: Opportunity) -> draft_rules.DraftInputs:
    """Refs are numbered in a stable order (page, then clause text), so the
    same facts always get the same R#/E# ids."""
    reasons = {r["evidence"]["fact_id"]: r for r in (tender.qualification.reasons if tender.qualification else [])
               if r.get("evidence")}
    requirements = sorted(tender.requirements, key=lambda r: (r.page_number, r.requirement_text))
    eligibility = sorted(tender.eligibility_criteria, key=lambda e: (e.page_number, e.criterion_text))

    extra_amounts: set[float] = set()
    extra_years: set[int] = set()
    for e in eligibility:
        for key in ("amount_inr", "min_project_value_inr"):
            if isinstance(e.extracted_value.get(key), (int, float)):
                extra_amounts.add(float(e.extracted_value[key]))
        for key in ("period_years", "years"):
            if isinstance(e.extracted_value.get(key), (int, float)):
                extra_years.add(int(e.extracted_value[key]))
    for r in requirements:
        if isinstance(r.details.get("min_experience_years"), (int, float)):
            extra_years.add(int(r.details["min_experience_years"]))

    turnover = [
        {"financial_year": y["financial_year"], "turnover": format_inr(float(y["amount_inr"]))}
        for y in profile.turnover_by_year or []
    ]
    extra_amounts |= {float(y["amount_inr"]) for y in profile.turnover_by_year or []}
    company = {
        "company_name": profile.company_name,
        "msme_registered": profile.msme_registered,
        "msme_certificate_ref": profile.msme_certificate_ref,
        "startup_registered": profile.startup_registered,
        "startup_certificate_ref": profile.startup_certificate_ref,
        "turnover_by_year": turnover,
        "net_worth": format_inr(float(profile.net_worth_inr)) if profile.net_worth_inr is not None else None,
        "years_in_business": profile.years_in_business,
        "employee_count": profile.employee_count,
        "locations": profile.locations,
        "certifications": profile.certifications,
        "capabilities": [
            {"capability": c.capability.value, "technologies": c.technologies, "certifications": c.certifications}
            for c in profile.capabilities
        ],
    }
    if profile.net_worth_inr is not None:
        extra_amounts.add(float(profile.net_worth_inr))
    if profile.years_in_business is not None:
        extra_years.add(profile.years_in_business)
    company["not_recorded"] = [k for k, v in company.items() if v in (None, [], "")]
    company = {k: v for k, v in company.items() if v not in (None, [], "") or k == "not_recorded"}

    projects = []
    for i, e in enumerate(sorted(profile.experience, key=lambda e: (-(e.year or 0), e.project_name)), start=1):
        value = float(e.project_value_inr) if e.project_value_inr is not None else None
        if value is not None:
            extra_amounts.add(value)
        projects.append(
            draft_rules.ProjectRef(
                ref=f"P{i}",
                project_name=e.project_name,
                client_name=e.client_name,
                customer_type=e.customer_type.value,
                capability=e.capability.value if e.capability else None,
                value_inr=value,
                year=e.year,
                technologies=list(e.technologies),
            )
        )

    for value in (tender.tender_value, tender.emd_amount, tender.tender_fee):
        if value is not None:
            extra_amounts.add(float(value))

    return draft_rules.DraftInputs(
        tender=_tender_summary(tender),
        requirements=[
            draft_rules.FactRef(
                ref=f"R{i}",
                kind=r.category.value,
                summary=r.summary,
                clause=r.requirement_text,
                citation=_citation(r),
                details=r.details or {},
            )
            for i, r in enumerate(requirements, start=1)
        ],
        eligibility=[
            draft_rules.FactRef(
                ref=f"E{i}",
                kind=e.criterion_type.value,
                summary=e.summary,
                clause=e.criterion_text,
                citation=_citation(e),
                details=e.extracted_value or {},
                assessment=reasons.get(str(e.id), {}).get("outcome"),
                assessment_note=reasons.get(str(e.id), {}).get("text"),
            )
            for i, e in enumerate(eligibility, start=1)
        ],
        company=company,
        projects=projects,
        enclosures=[
            {"title": i.title, "mandatory": i.mandatory, "status": i.status.value, "form_reference": i.form_reference}
            for i in opportunity.checklist_items
        ],
        extra_amounts=extra_amounts,
        extra_years=extra_years,
    )


def generate_draft(db: Session, opportunity: Opportunity, user: User, llm: LLMClient | None = None) -> BidDraft:
    """Raises ProfileNotConfiguredError, TenderNotAnalysedError,
    LLMNotConfiguredError, LLMResponseError or DraftGroundingError — a
    rejected draft is never stored, and the rejection is audited."""
    tender = opportunity.tender
    profile = profile_service.require_profile(db)
    if not (tender.requirements or tender.eligibility_criteria):
        raise TenderNotAnalysedError("Analyse the tender documents first — a draft is written from their clauses")
    if tender.qualification is None or qualification_service.is_stale(tender, tender.qualification, profile):
        qualification_service.compute(db, tender)
        db.refresh(tender)

    inputs = build_inputs(tender, profile, opportunity)
    prompt = draft_rules.build_prompt(inputs)
    llm = llm or get_llm_client()
    response = llm.complete_json(system=draft_rules.DRAFT_SYSTEM, user=prompt, schema=draft_rules.BID_DRAFT_SCHEMA)

    problems = draft_rules.verify(response.data, inputs, prompt)
    if problems:
        audit_service.record(
            db, action="bid.draft_rejected", user_id=user.id, entity_type="opportunity",
            entity_id=str(opportunity.id), details={"model": response.model, "problems": problems},
        )
        logger.warning("Draft for opportunity=%s rejected: %s", opportunity.id, problems)
        raise draft_rules.DraftGroundingError(problems)

    content, placeholders = draft_rules.assemble(response.data, inputs, _now(), response.model)
    version = max((d.version for d in opportunity.bid_drafts), default=0) + 1
    draft = BidDraft(
        version=version,
        content=content,
        placeholders=placeholders,
        generated_by_model=response.model,
        created_by_id=user.id,
    )
    opportunity.bid_drafts.append(draft)
    db.commit()
    db.refresh(draft)
    audit_service.record(
        db, action="bid.draft_generated", user_id=user.id, entity_type="opportunity", entity_id=str(opportunity.id),
        details={"version": version, "model": response.model, "placeholders": len(placeholders)},
    )
    return draft


def prepare_bid(db: Session, tender: Tender, user: User, llm: LLMClient | None = None) -> PreparationOutcome:
    opportunity, created = opportunity_service.ensure_opportunity(
        db, tender, user, comment=f"Created by {user.full_name} to prepare a bid"
    )
    team = opportunity_service.ROLE_TEAM.get(user.role.name)
    if team is not None:
        opportunity_service.assign(db, opportunity, user, team, by=user)
    sync_checklist(db, opportunity)
    audit_service.record(
        db, action="bid.preparation_started", user_id=user.id, entity_type="opportunity",
        entity_id=str(opportunity.id), details={"tender_id": str(tender.id), "opportunity_created": created},
    )

    draft, error, problems = None, None, []
    try:
        draft = generate_draft(db, opportunity, user, llm)
    except draft_rules.DraftGroundingError as exc:
        error, problems = str(exc), exc.problems
    except ProfileNotConfiguredError:
        error = "Set up the company profile before a draft can be written"
    except (TenderNotAnalysedError, LLMNotConfiguredError, LLMResponseError) as exc:
        error = str(exc)
    db.refresh(opportunity)
    return PreparationOutcome(opportunity, created, draft, error, problems)


# ------------------------------------------------------------- downloads


def base_filename(opportunity: Opportunity) -> str:
    tender = opportunity.tender
    return export.safe_filename(tender.tender_number or tender.title)


def draft_document(draft: BidDraft) -> bytes:
    return export.draft_docx(draft.content, draft.version)


def checklist_document(opportunity: Opportunity) -> bytes:
    return export.checklist_xlsx(_tender_summary(opportunity.tender), checklist_rows(opportunity), _now())


def bid_pack(opportunity: Opportunity) -> bytes:
    latest = opportunity.bid_drafts[0] if opportunity.bid_drafts else None
    return export.bid_pack_zip(
        base_filename(opportunity), draft_document(latest) if latest else None, checklist_document(opportunity)
    )
