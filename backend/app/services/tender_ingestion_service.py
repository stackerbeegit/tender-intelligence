"""
The single place that turns a `NormalisedTender` (from any connector, or
from the manual-entry fallback) into `tenders` + related rows, handling
deduplication and deadline-change history. Connectors and the manual-entry
API both call `ingest_tender()` — neither one duplicates this logic.

Two dedup keys, checked in order:
1. `(source_id, source_tender_id)` — the strong key: "have we already seen
   this exact portal's reference number before".
2. `fingerprint_hash` — a fallback for the same tender appearing on a
   different source/re-publication, computed from title + organisation +
   value + published_date only (deliberately *not* closing_date, since
   that's the one field corrigenda are expected to change — see
   docs/database.md §3).
"""
import hashlib
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base.types import NormalisedTender
from app.models.enums import DeadlineType, OrganisationType, TenderStatus
from app.models.tender import Tender
from app.models.tender_category import TenderCategory
from app.models.tender_deadline import TenderDeadline
from app.models.tender_document import TenderDocument
from app.models.tender_location import TenderLocation
from app.models.tender_organisation import TenderOrganisation


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def compute_fingerprint(
    title: str,
    organisation_name: str | None,
    tender_value: Decimal | None,
    published_date,
) -> str:
    parts = [
        _normalize_text(title),
        _normalize_text(organisation_name),
        str(tender_value) if tender_value is not None else "",
        published_date.isoformat() if published_date else "",
    ]
    digest_input = "|".join(parts).encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()


def get_or_create_organisation(db: Session, normalised: NormalisedTender) -> TenderOrganisation | None:
    if not normalised.organisation_name:
        return None

    normalized_name = _normalize_text(normalised.organisation_name)
    existing = db.scalar(select(TenderOrganisation).where(TenderOrganisation.normalized_name == normalized_name))
    if existing:
        # Fill in location fields a later connector version can supply, but
        # never overwrite what's already set (e.g. by a manual edit).
        if existing.state is None and normalised.organisation_state:
            existing.state = normalised.organisation_state
            if normalised.organisation_type == OrganisationType.STATE_GOVT:
                existing.type = OrganisationType.STATE_GOVT
        if existing.city is None and normalised.organisation_city:
            existing.city = normalised.organisation_city
        return existing

    organisation = TenderOrganisation(
        name=normalised.organisation_name,
        normalized_name=normalized_name,
        type=normalised.organisation_type,
        state=normalised.organisation_state,
        city=normalised.organisation_city,
    )
    db.add(organisation)
    db.flush()
    return organisation


def _find_existing(db: Session, source_id: uuid.UUID, normalised: NormalisedTender, fingerprint: str) -> Tender | None:
    if normalised.source_tender_id:
        existing = db.scalar(
            select(Tender).where(
                Tender.source_id == source_id,
                Tender.source_tender_id == normalised.source_tender_id,
            )
        )
        if existing:
            return existing

    candidate = db.scalar(select(Tender).where(Tender.fingerprint_hash == fingerprint))
    if candidate is not None and _is_distinct_listing(candidate, source_id, normalised):
        return None
    return candidate


def _is_distinct_listing(candidate: Tender, source_id: uuid.UUID, normalised: NormalisedTender) -> bool:
    """Two listings from the same source with different IDs are different
    tenders, however alike they look. GeM routinely has several bids with
    the same title, buyer and start date (e.g. one per site, or a bid and its
    reverse auction); fingerprint matching is only for listings that carry
    no ID of their own (manual entry) or come from another source."""
    return (
        normalised.source_tender_id is not None
        and candidate.source_id == source_id
        and candidate.source_tender_id is not None
        and candidate.source_tender_id != normalised.source_tender_id
    )


def _comparable(dt: datetime) -> datetime:
    """Normalise to a naive UTC instant before comparing. SQLite's
    DateTime(timezone=True) doesn't actually round-trip tzinfo (every value
    comes back naive), so comparing a freshly-reloaded `tender.closing_date`
    against an incoming tz-aware value would otherwise look "changed" on
    every re-ingestion even when nothing moved. Postgres preserves tzinfo
    correctly, but normalising both sides the same way is correct there too."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _apply_deadline_change(db: Session, tender: Tender, new_closing_date: datetime | None) -> None:
    if new_closing_date is None:
        return

    if tender.closing_date is None:
        db.add(TenderDeadline(tender_id=tender.id, deadline_type=DeadlineType.BID_SUBMISSION, deadline_at=new_closing_date))
        tender.closing_date = new_closing_date
        return

    if _comparable(tender.closing_date) != _comparable(new_closing_date):
        db.add(TenderDeadline(tender_id=tender.id, deadline_type=DeadlineType.EXTENDED, deadline_at=new_closing_date))
        tender.closing_date = new_closing_date
        tender.status = TenderStatus.CORRIGENDUM


def _sync_child_rows(db: Session, tender: Tender, normalised: NormalisedTender) -> None:
    existing_location_keys = {(loc.state, loc.city, loc.pincode) for loc in tender.locations}
    for loc in normalised.locations:
        key = (loc.state, loc.city, loc.pincode)
        if key not in existing_location_keys:
            db.add(TenderLocation(tender_id=tender.id, state=loc.state, city=loc.city, pincode=loc.pincode))
            existing_location_keys.add(key)

    existing_categories = {cat.category for cat in tender.categories}
    for category in normalised.categories:
        if category not in existing_categories:
            db.add(TenderCategory(tender_id=tender.id, category=category))
            existing_categories.add(category)

    existing_doc_keys = {(doc.file_name, doc.source_url) for doc in tender.documents}
    for doc in normalised.documents:
        key = (doc.file_name, doc.source_url)
        if key not in existing_doc_keys:
            db.add(
                TenderDocument(
                    tender_id=tender.id,
                    file_name=doc.file_name,
                    document_type=doc.document_type,
                    source_url=doc.source_url,
                )
            )
            existing_doc_keys.add(key)


def ingest_tender(db: Session, source_id: uuid.UUID, normalised: NormalisedTender) -> tuple[Tender, bool]:
    """Returns (tender, created) — created=False means an existing tender was matched/updated."""
    fingerprint = compute_fingerprint(
        normalised.title, normalised.organisation_name, normalised.tender_value, normalised.published_date
    )

    existing = _find_existing(db, source_id, normalised, fingerprint)

    if existing:
        existing.title = normalised.title
        existing.tender_number = normalised.tender_number or existing.tender_number
        existing.url = normalised.url or existing.url
        existing.tender_value = normalised.tender_value if normalised.tender_value is not None else existing.tender_value
        existing.emd_amount = normalised.emd_amount if normalised.emd_amount is not None else existing.emd_amount
        existing.tender_fee = normalised.tender_fee if normalised.tender_fee is not None else existing.tender_fee
        existing.raw_metadata = {**existing.raw_metadata, **normalised.raw_metadata}
        # Called even when already linked so a newer connector can backfill
        # the organisation's missing location fields.
        organisation = get_or_create_organisation(db, normalised)
        if organisation and existing.organisation_id is None:
            existing.organisation_id = organisation.id

        _apply_deadline_change(db, existing, normalised.closing_date)
        db.flush()
        _sync_child_rows(db, existing, normalised)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing, False

    if db.scalar(select(Tender.id).where(Tender.fingerprint_hash == fingerprint)) is not None:
        # A look-alike listing from this source already holds the fingerprint
        # (see _is_distinct_listing); fingerprint_hash is unique, so make this
        # one's distinct by folding in its own ID.
        fingerprint = hashlib.sha256(f"{fingerprint}|{normalised.source_tender_id}".encode("utf-8")).hexdigest()

    organisation = get_or_create_organisation(db, normalised)
    tender = Tender(
        source_id=source_id,
        source_tender_id=normalised.source_tender_id,
        fingerprint_hash=fingerprint,
        tender_number=normalised.tender_number,
        title=normalised.title,
        organisation_id=organisation.id if organisation else None,
        url=normalised.url,
        published_date=normalised.published_date,
        closing_date=normalised.closing_date,
        tender_value=normalised.tender_value,
        emd_amount=normalised.emd_amount,
        tender_fee=normalised.tender_fee,
        status=normalised.status,
        raw_metadata=normalised.raw_metadata,
    )
    db.add(tender)
    db.flush()

    if normalised.closing_date:
        db.add(TenderDeadline(tender_id=tender.id, deadline_type=DeadlineType.BID_SUBMISSION, deadline_at=normalised.closing_date))

    for loc in normalised.locations:
        db.add(TenderLocation(tender_id=tender.id, state=loc.state, city=loc.city, pincode=loc.pincode))

    for category in normalised.categories:
        db.add(TenderCategory(tender_id=tender.id, category=category))

    for doc in normalised.documents:
        db.add(
            TenderDocument(
                tender_id=tender.id, file_name=doc.file_name, document_type=doc.document_type, source_url=doc.source_url
            )
        )

    db.commit()
    db.refresh(tender)
    return tender, True
