import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import AnalysisStatus, EligibilityCriterionType, RequirementCategory


class CitationRead(BaseModel):
    document_id: uuid.UUID
    file_name: str
    page_number: int


class RequirementRead(BaseModel):
    """FACT: `requirement_text` is a verbatim quote verified to occur on
    the cited page."""

    id: uuid.UUID
    category: RequirementCategory
    summary: str
    requirement_text: str
    details: dict[str, Any]
    citation: CitationRead
    generated_by_model: str


class EligibilityRead(BaseModel):
    """FACT: what the tender requires — not whether Stackerbee meets it."""

    id: uuid.UUID
    criterion_type: EligibilityCriterionType
    summary: str
    criterion_text: str
    extracted_value: dict[str, Any]
    citation: CitationRead
    generated_by_model: str


class AnalysisRunRead(BaseModel):
    """`summary` is AI INTERPRETATION written from the facts above;
    clients must label it as AI-generated."""

    model_config = ConfigDict(from_attributes=True)

    status: AnalysisStatus
    summary: dict[str, Any] | None
    run_stats: dict[str, Any]
    documents_analysed: int
    generated_by_model: str | None
    started_at: datetime
    finished_at: datetime | None
    error: str | None


class TenderAnalysisResponse(BaseModel):
    tender_id: uuid.UUID
    analysis: AnalysisRunRead | None
    requirements: list[RequirementRead]
    eligibility: list[EligibilityRead]
