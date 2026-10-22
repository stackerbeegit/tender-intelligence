import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    DeadlineType,
    DocumentType,
    EligibilityStatus,
    OpportunityStatus,
    OrganisationType,
    TenderCategory as TenderCategoryEnum,
    TenderStatus,
)


class LocationIn(BaseModel):
    state: str | None = None
    city: str | None = None
    pincode: str | None = None


class DocumentIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=500)
    document_type: DocumentType = DocumentType.OTHER
    source_url: str | None = None


class ManualTenderCreate(BaseModel):
    """The Rule 12 manual-upload fallback: staff enter a tender directly
    rather than any portal being scraped without a verified access path."""

    title: str = Field(min_length=1, max_length=1000)
    tender_number: str | None = None
    source_tender_id: str | None = Field(
        default=None, description="Only set if this mirrors a specific portal reference number"
    )
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
    locations: list[LocationIn] = Field(default_factory=list)
    categories: list[TenderCategoryEnum] = Field(default_factory=list)
    documents: list[DocumentIn] = Field(default_factory=list)


class OrganisationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: OrganisationType
    state: str | None
    city: str | None


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    state: str | None
    city: str | None
    pincode: str | None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: TenderCategoryEnum
    confidence: Decimal | None


class DeadlineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    deadline_type: DeadlineType
    deadline_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_name: str
    document_type: DocumentType
    source_url: str | None
    storage_path: str | None
    checksum_sha256: str | None
    file_size_bytes: int | None
    page_count: int | None
    ocr_status: str
    extraction_status: str
    extracted_text: str | None
    last_processing_error: str | None


class QualificationBrief(BaseModel):
    """Rule-based assessment (see GET /tenders/{id}/qualification for the
    evidence behind it)."""

    model_config = ConfigDict(from_attributes=True)

    eligibility_status: EligibilityStatus
    relevance_score: int


class OpportunityBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: OpportunityStatus


class TenderListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    tender_number: str | None
    organisation: OrganisationRead | None
    tender_value: Decimal | None
    published_date: date | None
    closing_date: datetime | None
    status: TenderStatus
    source_id: uuid.UUID
    categories: list[CategoryRead]
    locations: list[LocationRead]
    qualification: QualificationBrief | None = None
    opportunity: OpportunityBrief | None = None


class TenderDetail(TenderListItem):
    url: str | None
    emd_amount: Decimal | None
    tender_fee: Decimal | None
    source_tender_id: str | None
    raw_metadata: dict
    deadlines: list[DeadlineRead]
    documents: list[DocumentRead]
    created_at: datetime
    updated_at: datetime


class TenderListResponse(BaseModel):
    items: list[TenderListItem]
    total: int
    page: int
    page_size: int
