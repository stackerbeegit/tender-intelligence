"""
The daily digest e-mail: what's new since yesterday, ranked by relevance,
and what needs the reader's attention on their own opportunities.

`build_digest` gathers the data (one query set per user, given a shared
list of new tenders); `render_digest` turns it into subject + plain text +
HTML. Both are plain functions so the rendered e-mail is unit-testable.
HTML is escaped by hand (`html.escape`) — the project has no template
engine and two small tables don't justify adding one.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import EligibilityStatus
from app.models.opportunity import Opportunity
from app.models.opportunity_assignment import OpportunityAssignment
from app.models.qualification_result import QualificationResult
from app.models.tender import Tender
from app.models.user import User
from app.services.opportunity_service import FINAL_STATUSES, label

MAX_NEW_TENDERS = 10
CLOSING_SOON_DAYS = 7
_STATUS_TEXT = {
    EligibilityStatus.ELIGIBLE: "Eligible",
    EligibilityStatus.NOT_ELIGIBLE: "Not eligible",
    EligibilityStatus.UNCERTAIN: "Uncertain",
}


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@dataclass
class DigestTender:
    id: str
    title: str
    organisation: str | None
    closing_date: datetime | None
    relevance_score: int | None
    eligibility: str | None


@dataclass
class DigestOpportunity:
    id: str
    title: str
    status: str
    closing_date: datetime | None
    closing_soon: bool


@dataclass
class DigestChange:
    opportunity_id: str
    title: str
    from_status: str | None
    to_status: str
    by: str
    comment: str | None


@dataclass
class Digest:
    generated_at: datetime
    new_tenders: list[DigestTender] = field(default_factory=list)
    my_opportunities: list[DigestOpportunity] = field(default_factory=list)
    changes: list[DigestChange] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.new_tenders or self.my_opportunities or self.changes)


def new_tenders_since(db: Session, since: datetime) -> list[DigestTender]:
    """Tenders added since `since`, most relevant first (unscored last)."""
    rows = db.execute(
        select(Tender, QualificationResult)
        .outerjoin(QualificationResult, QualificationResult.tender_id == Tender.id)
        .where(Tender.created_at >= since)
        .options(selectinload(Tender.organisation))
        .order_by(QualificationResult.relevance_score.desc().nulls_last(), Tender.closing_date.asc().nulls_last())
        .limit(MAX_NEW_TENDERS)
    ).all()
    return [
        DigestTender(
            id=str(tender.id),
            title=tender.title,
            organisation=tender.organisation.name if tender.organisation else None,
            closing_date=_aware(tender.closing_date),
            relevance_score=result.relevance_score if result else None,
            eligibility=_STATUS_TEXT[result.eligibility_status] if result else None,
        )
        for tender, result in rows
    ]


def build_digest(db: Session, user: User, now: datetime, new_tenders: list[DigestTender] | None = None) -> Digest:
    since = now - timedelta(hours=24)
    digest = Digest(generated_at=now)
    digest.new_tenders = new_tenders if new_tenders is not None else new_tenders_since(db, since)

    mine = (
        db.execute(
            select(Opportunity)
            .outerjoin(OpportunityAssignment, OpportunityAssignment.opportunity_id == Opportunity.id)
            .where(or_(Opportunity.owner_id == user.id, OpportunityAssignment.user_id == user.id))
            .options(selectinload(Opportunity.tender), selectinload(Opportunity.status_history))
        )
        .scalars()
        .unique()
        .all()
    )
    soon = now + timedelta(days=CLOSING_SOON_DAYS)
    open_mine = [o for o in mine if o.status not in FINAL_STATUSES]
    open_mine.sort(key=lambda o: (_aware(o.tender.closing_date) or datetime.max.replace(tzinfo=timezone.utc)))
    digest.my_opportunities = [
        DigestOpportunity(
            id=str(o.id),
            title=o.title,
            status=label(o.status),
            closing_date=_aware(o.tender.closing_date),
            closing_soon=bool(o.tender.closing_date and now <= _aware(o.tender.closing_date) <= soon),
        )
        for o in open_mine
    ]

    for opportunity in mine:
        for entry in opportunity.status_history:
            changed_at = _aware(entry.changed_at)
            if changed_at < since or entry.from_status is None or entry.changed_by_id == user.id:
                continue
            digest.changes.append(
                DigestChange(
                    opportunity_id=str(opportunity.id),
                    title=opportunity.title,
                    from_status=label(entry.from_status),
                    to_status=label(entry.to_status),
                    by=entry.changed_by.full_name if entry.changed_by else "System",
                    comment=entry.comment,
                )
            )
    return digest


def _date(value: datetime | None) -> str:
    return value.strftime("%d %b %Y") if value else "no closing date"


def render_digest(digest: Digest, recipient_name: str, base_url: str) -> tuple[str, str, str]:
    base = base_url.rstrip("/")
    day = digest.generated_at.strftime("%d %b %Y")
    soon = sum(1 for o in digest.my_opportunities if o.closing_soon)
    subject = f"Tender digest {day}: {len(digest.new_tenders)} new tender(s)" + (
        f", {soon} of your opportunities closing within {CLOSING_SOON_DAYS} days" if soon else ""
    )

    def tender_line(t: DigestTender) -> str:
        score = f"relevance {t.relevance_score}/100, {t.eligibility}" if t.relevance_score is not None else "not scored yet"
        return f"{t.title} — {t.organisation or 'organisation not stated'} — closes {_date(t.closing_date)} — {score}"

    text = [f"Hello {recipient_name},", ""]
    text.append(f"NEW TENDERS (last 24 hours, most relevant first): {len(digest.new_tenders)}")
    text += [f"- {tender_line(t)}\n  {base}/tenders/{t.id}" for t in digest.new_tenders] or ["- none"]
    text += ["", f"YOUR OPEN OPPORTUNITIES: {len(digest.my_opportunities)}"]
    text += [
        f"- {'[CLOSING SOON] ' if o.closing_soon else ''}{o.title} — {o.status} — closes {_date(o.closing_date)}\n"
        f"  {base}/opportunities/{o.id}"
        for o in digest.my_opportunities
    ] or ["- none"]
    if digest.changes:
        text += ["", "STATUS CHANGES BY OTHERS:"]
        text += [
            f"- {c.title}: {c.from_status} → {c.to_status} by {c.by}" + (f" ({c.comment})" if c.comment else "")
            for c in digest.changes
        ]
    text += ["", "Relevance and eligibility are rule-based assessments — check the evidence before deciding."]

    cell = 'style="padding:6px 8px;border-bottom:1px solid #e5e7eb;vertical-align:top"'
    head = 'style="padding:6px 8px;text-align:left;border-bottom:2px solid #d1d5db;font-size:12px;color:#6b7280"'

    def tender_row(t: DigestTender) -> str:
        score = f"{t.relevance_score}" if t.relevance_score is not None else "—"
        return (
            f"<tr><td {cell}><a href=\"{escape(base)}/tenders/{escape(t.id)}\">{escape(t.title)}</a>"
            f"<br><span style=\"color:#6b7280;font-size:12px\">{escape(t.organisation or '')}</span></td>"
            f"<td {cell}>{escape(_date(t.closing_date))}</td><td {cell}>{escape(score)}</td>"
            f"<td {cell}>{escape(t.eligibility or 'Not assessed')}</td></tr>"
        )

    def opportunity_row(o: DigestOpportunity) -> str:
        flag = ' <strong style="color:#b91c1c">closing soon</strong>' if o.closing_soon else ""
        return (
            f"<tr><td {cell}><a href=\"{escape(base)}/opportunities/{escape(o.id)}\">{escape(o.title)}</a></td>"
            f"<td {cell}>{escape(o.status)}</td><td {cell}>{escape(_date(o.closing_date))}{flag}</td></tr>"
        )

    html = [
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#111827;max-width:720px">',
        f"<p>Hello {escape(recipient_name)},</p>",
        f"<h3>New tenders ({len(digest.new_tenders)})</h3>",
    ]
    if digest.new_tenders:
        html.append(
            f'<table style="border-collapse:collapse;width:100%"><tr><th {head}>Tender</th><th {head}>Closes</th>'
            f"<th {head}>Relevance</th><th {head}>Eligibility</th></tr>"
            + "".join(tender_row(t) for t in digest.new_tenders)
            + "</table>"
        )
    else:
        html.append("<p>No new tenders in the last 24 hours.</p>")
    html.append(f"<h3>Your open opportunities ({len(digest.my_opportunities)})</h3>")
    if digest.my_opportunities:
        html.append(
            f'<table style="border-collapse:collapse;width:100%"><tr><th {head}>Opportunity</th>'
            f"<th {head}>Status</th><th {head}>Closes</th></tr>"
            + "".join(opportunity_row(o) for o in digest.my_opportunities)
            + "</table>"
        )
    else:
        html.append("<p>None assigned to you.</p>")
    if digest.changes:
        html.append("<h3>Status changes by others</h3><ul>")
        html += [
            f"<li><a href=\"{escape(base)}/opportunities/{escape(c.opportunity_id)}\">{escape(c.title)}</a>: "
            f"{escape(c.from_status or '')} → {escape(c.to_status)} by {escape(c.by)}"
            + (f" — <em>{escape(c.comment)}</em>" if c.comment else "")
            + "</li>"
            for c in digest.changes
        ]
        html.append("</ul>")
    html.append(
        '<p style="color:#6b7280;font-size:12px">Relevance and eligibility are rule-based assessments from the '
        "extracted facts and the company profile. Check the evidence before deciding.</p></div>"
    )
    return subject, "\n".join(text), "".join(html)
