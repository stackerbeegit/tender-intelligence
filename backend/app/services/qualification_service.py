"""
Database side of the matching engine: converts a tender's verified fact
rows and the company profile into the engine's plain inputs, runs
`app.matching.engine.qualify`, and stores the outcome on
`qualification_results` (one row per tender, replaced on each run).

A stored result is *stale* when the profile, the tender's facts or the
engine's rules changed after it was computed; the API reports that rather
than silently recomputing on read, so a reviewer always knows which
inputs a result reflects.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.matching.engine import ENGINE_VERSION, qualify
from app.matching.types import (
    Capability,
    Citation,
    CompanyProfile,
    EligibilityFact,
    Experience,
    RequirementFact,
    TenderCategoryTag,
    TenderFacts,
    TurnoverYear,
)
from app.models.enums import AnalysisStatus
from app.models.qualification_result import QualificationResult
from app.models.stackerbee_profile import StackerbeeProfile
from app.models.tender import Tender
from app.services import opportunity_service
from app.services.profile_service import get_profile, require_profile

logger = get_logger(__name__)


def _aware(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything here is UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _float(value) -> float | None:
    return None if value is None else float(value)


def tender_facts(tender: Tender) -> TenderFacts:
    analysed = bool(tender.eligibility_criteria or tender.requirements) or (
        tender.analysis is not None and tender.analysis.status is AnalysisStatus.DONE
    )
    return TenderFacts(
        tender_id=str(tender.id),
        status=tender.status,
        closing_date=_aware(tender.closing_date),
        tender_value_inr=_float(tender.tender_value),
        categories=[
            TenderCategoryTag(category=row.category, confidence=_float(row.confidence)) for row in tender.categories
        ],
        delivery_states=[loc.state for loc in tender.locations if loc.state],
        buyer_state=tender.organisation.state if tender.organisation else None,
        analysed=analysed,
        eligibility=[
            EligibilityFact(
                criterion_type=row.criterion_type,
                summary=row.summary,
                value=row.extracted_value or {},
                citation=Citation(
                    fact_id=str(row.id),
                    document_id=str(row.document_id),
                    file_name=row.document.file_name,
                    page_number=row.page_number,
                    quote=row.criterion_text,
                ),
            )
            for row in tender.eligibility_criteria
        ],
        requirements=[
            RequirementFact(
                category=row.category,
                summary=row.summary,
                details=row.details or {},
                citation=Citation(
                    fact_id=str(row.id),
                    document_id=str(row.document_id),
                    file_name=row.document.file_name,
                    page_number=row.page_number,
                    quote=row.requirement_text,
                ),
            )
            for row in tender.requirements
        ],
    )


def company_profile(profile: StackerbeeProfile) -> CompanyProfile:
    return CompanyProfile(
        msme_registered=profile.msme_registered,
        startup_registered=profile.startup_registered,
        turnover_by_year=[
            TurnoverYear(financial_year=y["financial_year"], amount_inr=float(y["amount_inr"]))
            for y in profile.turnover_by_year or []
        ],
        net_worth_inr=_float(profile.net_worth_inr),
        years_in_business=profile.years_in_business,
        employee_count=profile.employee_count,
        locations=list(profile.locations or []),
        certifications=list(profile.certifications or []),
        capabilities=[
            Capability(category=c.capability, technologies=list(c.technologies), certifications=list(c.certifications))
            for c in profile.capabilities
        ],
        experience=[
            Experience(
                id=str(e.id),
                project_name=e.project_name,
                customer_type=e.customer_type,
                capability=e.capability,
                technologies=list(e.technologies),
                value_inr=_float(e.project_value_inr),
                year=e.year,
            )
            for e in profile.experience
        ],
    )


def compute(db: Session, tender: Tender, now: datetime | None = None) -> QualificationResult:
    """Raises ProfileNotConfiguredError if there is no profile to match against."""
    profile = require_profile(db)
    now = now or datetime.now(timezone.utc)
    outcome = qualify(tender_facts(tender), company_profile(profile), now)

    result = tender.qualification
    if result is None:
        result = QualificationResult(tender_id=tender.id)
        tender.qualification = result
    result.eligibility_status = outcome.eligibility_status
    result.reasons = [c.as_dict() for c in outcome.checks]
    result.relevance_factors = {name: f.as_dict() for name, f in outcome.factors.items()}
    result.relevance_score = outcome.relevance_score
    result.risks = [r.as_dict() for r in outcome.risks]
    result.engine_version = ENGINE_VERSION
    result.computed_at = now
    db.commit()
    db.refresh(result)
    logger.info(
        "Qualified tender=%s status=%s score=%s", tender.id, outcome.eligibility_status.value, outcome.relevance_score
    )
    opportunity_service.auto_promote(db, tender, result, get_settings().opportunity_auto_promote_min_score)
    return result


def compute_if_profile_exists(db: Session, tender: Tender) -> QualificationResult | None:
    """Used after an analysis run: refresh the result when it can be
    computed, and do nothing (rather than fail the analysis) when no
    profile has been set up yet."""
    if get_profile(db) is None:
        return None
    return compute(db, tender)


def is_stale(tender: Tender, result: QualificationResult, profile: StackerbeeProfile | None) -> bool:
    if result.engine_version != ENGINE_VERSION or profile is None:
        return True
    computed_at = _aware(result.computed_at)
    changed = [_aware(profile.updated_at), _aware(tender.updated_at)]
    analysis = tender.analysis
    if analysis is not None and analysis.status is AnalysisStatus.DONE and analysis.finished_at is not None:
        changed.append(_aware(analysis.finished_at))  # a failed run leaves the facts untouched
    changed += [_aware(row.created_at) for row in tender.categories]
    return any(moment is not None and moment > computed_at for moment in changed)
