"""
JSON Schemas the LLM's output is constrained to, plus the dataclasses the
validated output is converted into. Written by hand (rather than
generated from Pydantic) to stay inside the subset both providers'
strict modes accept: every property required, `additionalProperties:
false` everywhere, optional values expressed as `anyOf [..., null]`, and
no numeric/string-length constraints.
"""
from dataclasses import dataclass, field
from typing import Any

from app.models.enums import EligibilityCriterionType, RequirementCategory, TenderCategory

MSME_CLAUSE_KINDS = [
    "msme_exemption",
    "msme_preference",
    "startup_exemption",
    "emd_exemption",
    "tender_fee_exemption",
    "experience_relaxation",
    "turnover_relaxation",
    "mse_purchase_preference",
]


def _nullable(type_name: str) -> dict[str, Any]:
    return {"anyOf": [{"type": type_name}, {"type": "null"}]}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_REQUIREMENT_DETAILS = _object(
    {
        "role": _nullable("string"),
        "resource_count": _nullable("integer"),
        "min_experience_years": _nullable("number"),
        "qualification": _nullable("string"),
        "location": _nullable("string"),
        "duration_months": _nullable("number"),
        "technologies": {"type": "array", "items": {"type": "string"}},
    }
)

_ELIGIBILITY_VALUE = _object(
    {
        "amount_inr": _nullable("number"),
        "period_years": _nullable("number"),
        "is_average": _nullable("boolean"),
        "project_count": _nullable("integer"),
        "min_project_value_inr": _nullable("number"),
        "years": _nullable("number"),
        "msme_clause_kind": {"anyOf": [{"type": "string", "enum": MSME_CLAUSE_KINDS}, {"type": "null"}]},
    }
)

EXTRACTION_SCHEMA: dict[str, Any] = _object(
    {
        "requirements": {
            "type": "array",
            "items": _object(
                {
                    "category": {"type": "string", "enum": [c.value for c in RequirementCategory]},
                    "summary": {"type": "string"},
                    "quote": {"type": "string"},
                    "page_number": {"type": "integer"},
                    "details": _REQUIREMENT_DETAILS,
                }
            ),
        },
        "eligibility": {
            "type": "array",
            "items": _object(
                {
                    "criterion_type": {"type": "string", "enum": [c.value for c in EligibilityCriterionType]},
                    "summary": {"type": "string"},
                    "quote": {"type": "string"},
                    "page_number": {"type": "integer"},
                    "value": _ELIGIBILITY_VALUE,
                }
            ),
        },
    }
)

SUMMARY_SCHEMA: dict[str, Any] = _object(
    {
        "project": {"type": "string"},
        "overview": {"type": "string"},
        "contract_duration": _nullable("string"),
        "core_requirements": {"type": "array", "items": {"type": "string"}},
        "manpower": {"type": "array", "items": {"type": "string"}},
        "eligibility_highlights": {"type": "array", "items": {"type": "string"}},
        "msme_provisions": {"type": "array", "items": {"type": "string"}},
        "points_to_review": {"type": "array", "items": {"type": "string"}},
        "categories": {
            "type": "array",
            "items": _object(
                {
                    "category": {"type": "string", "enum": [c.value for c in TenderCategory]},
                    "confidence": {"type": "number"},
                }
            ),
        },
    }
)


@dataclass(frozen=True)
class ExtractedRequirement:
    document_id: str
    category: RequirementCategory
    summary: str
    quote: str
    page_number: int  # 1-indexed
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractedEligibility:
    document_id: str
    criterion_type: EligibilityCriterionType
    summary: str
    quote: str
    page_number: int  # 1-indexed
    value: dict[str, Any] = field(default_factory=dict)


def drop_nulls(values: dict[str, Any]) -> dict[str, Any]:
    """The schema forces every key to be present; only the ones the model
    actually filled in are worth storing."""
    return {k: v for k, v in values.items() if v is not None and v != []}
