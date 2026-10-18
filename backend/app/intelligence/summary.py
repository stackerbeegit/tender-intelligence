"""
Executive summary + category classification (brief Module 10). Written
from the tender's metadata and its *already verified* fact rows — never
from raw document text — so the summary can only restate what was
extracted with a citation. Bullets reference facts by short ids (R1,
E2, ...); `fact_refs` in the returned dict maps each id to the stored
row's UUID so the UI can link a bullet back to its document/page.
"""
from typing import Any

from app.intelligence.extraction.prompts import SUMMARY_SYSTEM, build_summary_user_prompt
from app.intelligence.extraction.schemas import SUMMARY_SCHEMA
from app.intelligence.llm.base import LLMClient, LLMResult
from app.models.tender import Tender
from app.models.tender_eligibility import TenderEligibility
from app.models.tender_requirement import TenderRequirement


def _tender_metadata(tender: Tender) -> dict[str, Any]:
    return {
        "title": tender.title,
        "tender_number": tender.tender_number,
        "organisation": tender.organisation.name if tender.organisation else None,
        "tender_value_inr": str(tender.tender_value) if tender.tender_value is not None else None,
        "emd_inr": str(tender.emd_amount) if tender.emd_amount is not None else None,
        "tender_fee_inr": str(tender.tender_fee) if tender.tender_fee is not None else None,
        "published_date": tender.published_date.isoformat() if tender.published_date else None,
        "closing_date": tender.closing_date.isoformat() if tender.closing_date else None,
        "locations": [", ".join(filter(None, [loc.city, loc.state])) for loc in tender.locations],
    }


def generate_summary(
    llm: LLMClient,
    tender: Tender,
    requirements: list[TenderRequirement],
    eligibility: list[TenderEligibility],
) -> tuple[dict[str, Any], LLMResult]:
    fact_refs: dict[str, str] = {}
    requirement_inputs = []
    for index, row in enumerate(requirements, start=1):
        ref = f"R{index}"
        fact_refs[ref] = str(row.id)
        requirement_inputs.append(
            {"id": ref, "category": row.category.value, "summary": row.summary, "details": row.details}
        )
    eligibility_inputs = []
    for index, row in enumerate(eligibility, start=1):
        ref = f"E{index}"
        fact_refs[ref] = str(row.id)
        eligibility_inputs.append(
            {
                "id": ref,
                "criterion_type": row.criterion_type.value,
                "summary": row.summary,
                "value": row.extracted_value,
            }
        )

    response = llm.complete_json(
        system=SUMMARY_SYSTEM,
        user=build_summary_user_prompt(_tender_metadata(tender), requirement_inputs, eligibility_inputs),
        schema=SUMMARY_SCHEMA,
    )
    summary = dict(response.data)
    summary["fact_refs"] = fact_refs
    return summary, response
