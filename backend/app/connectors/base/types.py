"""
The common intermediate representation every connector normalises into.
`CrawlerRunner` and `app.services.tender_ingestion_service` only ever deal
with `NormalisedTender` — they don't know or care whether it came from a
live portal connector or the manual-entry fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.models.enums import DocumentType, OrganisationType, TenderCategory, TenderStatus


@dataclass(frozen=True)
class DiscoveredTenderRef:
    """One item returned by `discover()` — just enough to fetch it later."""

    source_tender_id: str
    url: str | None = None
    hint: dict = field(default_factory=dict)


@dataclass(frozen=True)
class NormalisedLocation:
    state: str | None = None
    city: str | None = None
    pincode: str | None = None


@dataclass(frozen=True)
class NormalisedDocument:
    file_name: str
    document_type: DocumentType = DocumentType.OTHER
    source_url: str | None = None


@dataclass(frozen=True)
class NormalisedTender:
    source_tender_id: str | None
    title: str
    tender_number: str | None = None
    organisation_name: str | None = None
    organisation_type: OrganisationType = OrganisationType.OTHER
    organisation_state: str | None = None
    organisation_city: str | None = None
    url: str | None = None
    published_date: date | None = None
    closing_date: datetime | None = None
    tender_value: Decimal | None = None
    emd_amount: Decimal | None = None
    tender_fee: Decimal | None = None
    status: TenderStatus = TenderStatus.OPEN
    locations: tuple[NormalisedLocation, ...] = field(default_factory=tuple)
    categories: tuple[TenderCategory, ...] = field(default_factory=tuple)
    documents: tuple[NormalisedDocument, ...] = field(default_factory=tuple)
    raw_metadata: dict = field(default_factory=dict)
