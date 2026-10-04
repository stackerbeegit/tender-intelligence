"""
The Rule 12 manual-upload ingestion path: staff enter a tender's details
directly (from a PDF they were emailed, a portal page they're allowed to
view but that has no automated access path yet, etc.) rather than any
portal being scraped without a verified terms-of-use/API check. Builds the
same `NormalisedTender` a connector would and hands off to the shared
`tender_ingestion_service`, so manual entries and crawled tenders are
indistinguishable once ingested.
"""
from sqlalchemy.orm import Session

from app.connectors.base.types import NormalisedDocument, NormalisedLocation, NormalisedTender
from app.core.exceptions import DomainError
from app.models.enums import SourceType
from app.models.tender import Tender
from app.repositories.source_repository import SourceRepository
from app.schemas.tender import ManualTenderCreate
from app.services import tender_ingestion_service

__all__ = ["create_manual_tender"]


def create_manual_tender(db: Session, payload: ManualTenderCreate) -> tuple[Tender, bool]:
    source = SourceRepository(db).get_by_type(SourceType.MANUAL)
    if source is None:
        raise DomainError("No 'manual' source is configured — expected the seeded Manual Entry source to exist")

    normalised = NormalisedTender(
        source_tender_id=payload.source_tender_id,
        title=payload.title,
        tender_number=payload.tender_number,
        organisation_name=payload.organisation_name,
        organisation_type=payload.organisation_type,
        organisation_state=payload.organisation_state,
        organisation_city=payload.organisation_city,
        url=payload.url,
        published_date=payload.published_date,
        closing_date=payload.closing_date,
        tender_value=payload.tender_value,
        emd_amount=payload.emd_amount,
        tender_fee=payload.tender_fee,
        status=payload.status,
        locations=tuple(NormalisedLocation(state=l.state, city=l.city, pincode=l.pincode) for l in payload.locations),
        categories=tuple(payload.categories),
        documents=tuple(
            NormalisedDocument(file_name=d.file_name, document_type=d.document_type, source_url=d.source_url)
            for d in payload.documents
        ),
        raw_metadata={"entry_method": "manual"},
    )

    return tender_ingestion_service.ingest_tender(db, source.id, normalised)
