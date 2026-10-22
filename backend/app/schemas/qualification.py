import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import CriterionOutcome, EligibilityCriterionType, EligibilityStatus, RiskSeverity


class FactEvidence(BaseModel):
    """The verified `tender_eligibility` clause a reason was derived from."""

    fact_id: str
    document_id: str
    file_name: str
    page_number: int
    quote: str


class ReasonRead(BaseModel):
    criterion_type: EligibilityCriterionType | None
    outcome: CriterionOutcome
    polarity: str  # support | concern | neutral
    text: str
    evidence: FactEvidence | None
    profile_evidence: dict[str, Any]


class FactorRead(BaseModel):
    score: int
    weight: int
    known: bool
    explanation: str
    evidence: list[dict[str, Any]]


class RiskRead(BaseModel):
    risk: str
    severity: RiskSeverity
    explanation: str
    evidence: str | None
    fact_id: str | None
    document_id: str | None
    file_name: str | None
    page: int | None


class QualificationRead(BaseModel):
    """INTERPRETATION, computed by deterministic rules from cited facts and
    the company profile. `relevance_score` = weighted mean of
    `relevance_factors`."""

    model_config = ConfigDict(from_attributes=True)

    eligibility_status: EligibilityStatus
    reasons: list[ReasonRead]
    relevance_score: int
    relevance_factors: dict[str, FactorRead]
    risks: list[RiskRead]
    engine_version: str
    computed_at: datetime


class QualificationResponse(BaseModel):
    tender_id: uuid.UUID
    profile_configured: bool
    # True when the profile, the tender's facts or the engine changed after
    # this result was computed — it should be recomputed before relying on it.
    is_stale: bool
    qualification: QualificationRead | None
