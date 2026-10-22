"""
Plain inputs and outputs of the matching engine. The engine never touches
the database or a model: `app/services/qualification_service.py` converts
ORM rows into these, so every rule in this package is unit-testable with
hand-built data and the same inputs always produce the same result.

Amounts are floats in INR — exact enough for threshold comparisons at
tender scale, and free of Decimal/float mixing inside the rules.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.enums import (
    CriterionOutcome,
    CustomerType,
    EligibilityCriterionType,
    EligibilityStatus,
    RequirementCategory,
    RiskSeverity,
    TenderCategory,
    TenderStatus,
)

# ---------------------------------------------------------------- inputs


@dataclass(frozen=True)
class Citation:
    """Where a fact came from — copied onto every reason/risk built from it."""

    fact_id: str
    document_id: str
    file_name: str
    page_number: int
    quote: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "document_id": self.document_id,
            "file_name": self.file_name,
            "page_number": self.page_number,
            "quote": self.quote,
        }


@dataclass(frozen=True)
class EligibilityFact:
    criterion_type: EligibilityCriterionType
    summary: str
    value: dict[str, Any]
    citation: Citation

    @property
    def text(self) -> str:
        return self.citation.quote


@dataclass(frozen=True)
class RequirementFact:
    category: RequirementCategory
    summary: str
    details: dict[str, Any]
    citation: Citation

    @property
    def text(self) -> str:
        return self.citation.quote


@dataclass(frozen=True)
class TenderCategoryTag:
    category: TenderCategory
    confidence: float | None  # None = set manually


@dataclass(frozen=True)
class TenderFacts:
    tender_id: str
    status: TenderStatus
    closing_date: datetime | None
    tender_value_inr: float | None
    categories: list[TenderCategoryTag]
    delivery_states: list[str]
    buyer_state: str | None
    analysed: bool  # a successful intelligence run exists
    eligibility: list[EligibilityFact] = field(default_factory=list)
    requirements: list[RequirementFact] = field(default_factory=list)


@dataclass(frozen=True)
class TurnoverYear:
    financial_year: str  # "2024-25"
    amount_inr: float


@dataclass(frozen=True)
class Capability:
    category: TenderCategory
    technologies: list[str]
    certifications: list[str]


@dataclass(frozen=True)
class Experience:
    id: str
    project_name: str
    customer_type: CustomerType
    capability: TenderCategory | None
    technologies: list[str]
    value_inr: float | None
    year: int | None


@dataclass(frozen=True)
class CompanyProfile:
    msme_registered: bool | None
    startup_registered: bool | None
    turnover_by_year: list[TurnoverYear]
    net_worth_inr: float | None
    years_in_business: int | None
    employee_count: int | None
    locations: list[str]
    certifications: list[str]
    capabilities: list[Capability] = field(default_factory=list)
    experience: list[Experience] = field(default_factory=list)

    @property
    def all_certifications(self) -> list[str]:
        return self.certifications + [c for cap in self.capabilities for c in cap.certifications]

    @property
    def all_technologies(self) -> list[str]:
        return [t for cap in self.capabilities for t in cap.technologies] + [
            t for exp in self.experience for t in exp.technologies
        ]


# --------------------------------------------------------------- outputs


@dataclass
class CriterionCheck:
    """One eligibility fact compared against the profile. `profile_evidence`
    records exactly which profile data the decision used."""

    criterion_type: EligibilityCriterionType | None
    outcome: CriterionOutcome
    text: str
    citation: Citation | None
    profile_evidence: dict[str, Any] = field(default_factory=dict)
    polarity_override: str | None = None

    @property
    def is_gate(self) -> bool:
        return self.outcome is not CriterionOutcome.INFO

    @property
    def polarity(self) -> str:
        if self.polarity_override:
            return self.polarity_override
        return {
            CriterionOutcome.MET: "support",
            CriterionOutcome.NOT_MET: "concern",
            CriterionOutcome.UNKNOWN: "concern",
            CriterionOutcome.INFO: "neutral",
        }[self.outcome]

    def as_dict(self) -> dict[str, Any]:
        return {
            "criterion_type": self.criterion_type.value if self.criterion_type else None,
            "outcome": self.outcome.value,
            "polarity": self.polarity,
            "text": self.text,
            "evidence": self.citation.as_dict() if self.citation else None,
            "profile_evidence": self.profile_evidence,
        }


@dataclass
class Factor:
    score: int  # 0-100; 50 when not `known`
    weight: int
    known: bool
    explanation: str
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "weight": self.weight,
            "known": self.known,
            "explanation": self.explanation,
            "evidence": self.evidence,
        }


@dataclass
class Risk:
    risk: str
    severity: RiskSeverity
    explanation: str
    citation: Citation | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "risk": self.risk,
            "severity": self.severity.value,
            "explanation": self.explanation,
            "evidence": self.citation.quote if self.citation else None,
            "fact_id": self.citation.fact_id if self.citation else None,
            "document_id": self.citation.document_id if self.citation else None,
            "file_name": self.citation.file_name if self.citation else None,
            "page": self.citation.page_number if self.citation else None,
        }


@dataclass
class QualificationOutcome:
    eligibility_status: EligibilityStatus
    checks: list[CriterionCheck]
    factors: dict[str, Factor]
    relevance_score: int
    risks: list[Risk]
