"""
Document -> verified facts. Pages are batched into excerpts bounded by
settings.llm_max_chars_per_call (so a large tender is never sent to the
LLM whole), each excerpt is one `complete_json` call, and every returned
item goes through the citation check before it is kept.

Pure with respect to the database: takes page text in, returns
dataclasses out. Persisting them is the service layer's job.
"""
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.intelligence.extraction.citations import normalise, quote_on_page
from app.intelligence.extraction.prompts import EXTRACTION_SYSTEM, build_extraction_user_prompt
from app.intelligence.extraction.schemas import (
    EXTRACTION_SCHEMA,
    ExtractedEligibility,
    ExtractedRequirement,
    drop_nulls,
)
from app.intelligence.llm.base import LLMClient
from app.models.enums import EligibilityCriterionType, RequirementCategory

logger = get_logger(__name__)


@dataclass
class DocumentExtraction:
    requirements: list[ExtractedRequirement] = field(default_factory=list)
    eligibility: list[ExtractedEligibility] = field(default_factory=list)
    llm_calls: int = 0
    pages_read: int = 0
    dropped_unverified: int = 0
    dropped_duplicates: int = 0
    dropped_examples: list[dict] = field(default_factory=list)  # first few, for the run log
    input_tokens: int = 0
    output_tokens: int = 0


_MAX_DROPPED_EXAMPLES = 5


def batch_pages(pages: list[str], max_chars: int) -> list[list[tuple[int, str]]]:
    """
    Groups non-empty pages into excerpts of at most `max_chars` of page
    text, keeping 1-indexed page numbers. A single page longer than
    `max_chars` (e.g. a dense BOQ sheet) is split into several excerpts
    that all carry that same page number, so citations stay correct.
    """
    batches: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    current_size = 0

    for index, raw in enumerate(pages):
        text = raw.strip()
        if not text:
            continue
        page_number = index + 1

        if len(text) > max_chars:
            if current:
                batches.append(current)
                current, current_size = [], 0
            for start in range(0, len(text), max_chars):
                batches.append([(page_number, text[start : start + max_chars])])
            continue

        if current and current_size + len(text) > max_chars:
            batches.append(current)
            current, current_size = [], 0
        current.append((page_number, text))
        current_size += len(text)

    if current:
        batches.append(current)
    return batches


def extract_document(
    llm: LLMClient,
    *,
    document_id: str,
    file_name: str,
    tender_title: str,
    pages: list[str],
    max_chars_per_call: int,
) -> DocumentExtraction:
    """Raises `LLMResponseError` if any call fails — a partially-read
    document is reported as a failed run, not stored as if complete."""
    result = DocumentExtraction()
    seen: set[tuple[str, str, int]] = set()

    for batch in batch_pages(pages, max_chars_per_call):
        result.llm_calls += 1
        result.pages_read += len({number for number, _ in batch})
        response = llm.complete_json(
            system=EXTRACTION_SYSTEM,
            user=build_extraction_user_prompt(tender_title, file_name, batch),
            schema=EXTRACTION_SCHEMA,
        )
        result.input_tokens += response.usage.get("input_tokens", 0)
        result.output_tokens += response.usage.get("output_tokens", 0)

        for item in response.data.get("requirements", []):
            if not _verified(item, pages, result, kind="requirement"):
                continue
            if _is_duplicate(seen, "requirement", item, result):
                continue
            result.requirements.append(
                ExtractedRequirement(
                    document_id=document_id,
                    category=RequirementCategory(item["category"]),
                    summary=item["summary"].strip()[:500],
                    quote=item["quote"].strip(),
                    page_number=item["page_number"],
                    details=drop_nulls(item.get("details") or {}),
                )
            )

        for item in response.data.get("eligibility", []):
            if not _verified(item, pages, result, kind="eligibility"):
                continue
            if _is_duplicate(seen, "eligibility", item, result):
                continue
            result.eligibility.append(
                ExtractedEligibility(
                    document_id=document_id,
                    criterion_type=EligibilityCriterionType(item["criterion_type"]),
                    summary=item["summary"].strip()[:500],
                    quote=item["quote"].strip(),
                    page_number=item["page_number"],
                    value=drop_nulls(item.get("value") or {}),
                )
            )

    logger.info(
        "Extracted document=%s calls=%d requirements=%d eligibility=%d dropped_unverified=%d",
        document_id,
        result.llm_calls,
        len(result.requirements),
        len(result.eligibility),
        result.dropped_unverified,
    )
    return result


def _verified(item: dict, pages: list[str], result: DocumentExtraction, *, kind: str) -> bool:
    page_number = item.get("page_number")
    quote = item.get("quote") or ""
    ok = (
        isinstance(page_number, int)
        and 1 <= page_number <= len(pages)
        and quote_on_page(quote, pages[page_number - 1])
    )
    if not ok:
        result.dropped_unverified += 1
        if len(result.dropped_examples) < _MAX_DROPPED_EXAMPLES:
            result.dropped_examples.append({"kind": kind, "page_number": page_number, "quote": quote[:300]})
        logger.warning("Dropped unverified %s on page %s: %r", kind, page_number, quote[:120])
    return ok


def _is_duplicate(seen: set[tuple[str, str, int]], kind: str, item: dict, result: DocumentExtraction) -> bool:
    """Overlapping excerpts (a page split across calls) can yield the same
    clause twice; same normalised quote on the same page is one fact."""
    key = (kind, normalise(item["quote"]), item["page_number"])
    if key in seen:
        result.dropped_duplicates += 1
        return True
    seen.add(key)
    return False
