"""
Prompt text for the two LLM tasks. Kept static (no timestamps or ids in
the system prompts) so provider-side prompt caching can reuse them.
"""
import json
from typing import Any

EXTRACTION_SYSTEM = """\
You read excerpts of Indian government tender documents (NIT, RFP, BOQ, \
annexures) and extract the requirements and eligibility criteria they state. \
Your output is stored as evidence that a bid team relies on, so accuracy \
matters more than coverage.

Each excerpt page is preceded by a marker line like `=== PAGE 7 ===`.

For every item you extract:
- `quote` must be copied exactly, character for character, from a single \
page of the excerpt: the shortest contiguous span (usually one sentence or \
table row) that states the requirement. Do not paraphrase, merge text from \
two places, fix typos, or add ellipses. Items whose quote cannot be found \
verbatim on the stated page are discarded automatically.
- `page_number` is the number from the marker of the page the quote is on.
- `summary` is a short plain-English restatement (under 25 words).
- Fill structured fields only with values the quote itself states. Convert \
Indian amounts to rupees as numbers (1 lakh = 100000, 1 crore = 10000000). \
Leave a field null when the quote does not state it. Never infer or assume.

Requirements (`requirements`): what the bidder must deliver or provide — \
technologies, software, platforms, infrastructure, integrations, support, \
SLAs, security, certifications of the solution, manpower (one item per role, \
with role, resource_count, min_experience_years, qualification where stated), \
and contract duration or delivery timelines (category `contract`).

Eligibility (`eligibility`): what the bidder must be or have to qualify — \
turnover (set is_average when the clause says average), net worth, EMD, \
tender fee, performance security, similar-project experience (project_count, \
min_project_value_inr), years in business, government/PSU experience, \
bidder certifications (ISO, CMMI, etc.), and any MSME / Startup / MSE clause \
(criterion_type `msme_startup`, with msme_clause_kind). Record an MSME clause \
exactly as written; do not conclude that any particular bidder qualifies.

Skip boilerplate that is not a requirement (headers, contact details, \
generic legal text, instructions on how to submit). If the excerpt states no \
requirements or eligibility criteria, return empty arrays."""


def build_extraction_user_prompt(tender_title: str, file_name: str, pages: list[tuple[int, str]]) -> str:
    """`pages` is a list of (1-indexed page number, page text)."""
    body = "\n\n".join(f"=== PAGE {number} ===\n{text}" for number, text in pages)
    return (
        f"Tender: {tender_title}\n"
        f"Document: {file_name}\n"
        f"Pages in this excerpt: {pages[0][0]}-{pages[-1][0]}\n\n"
        f"{body}"
    )


SUMMARY_SYSTEM = """\
You write executive summaries of government tenders for a bid team at \
Stackerbee, an Indian IT services company. You are given the tender's \
metadata and a list of facts already extracted from its documents, each \
with an id like R3 (requirement) or E2 (eligibility criterion).

Rules:
- Use only the information provided. Never add requirements, numbers, dates \
or organisations that are not in the input. If something is unknown, leave \
it out (or null) rather than guessing.
- Bullet strings should be short and end with the ids of the facts they \
rest on in square brackets, e.g. "Average turnover of ₹10 Cr over 3 years [E1]".
- `points_to_review` lists clauses a bid team should look at closely \
(demanding eligibility thresholds, heavy SLAs or penalties, large manpower \
commitments, unusual certifications). Describe what the tender requires; do \
not judge whether Stackerbee qualifies.
- `categories`: which of the given focus areas this tender belongs to, each \
with a confidence between 0 and 1. Include only categories that clearly \
apply; use `other` if none do.
- `contract_duration`: as stated in the facts, else null."""


def build_summary_user_prompt(
    tender_metadata: dict[str, Any], requirements: list[dict[str, Any]], eligibility: list[dict[str, Any]]
) -> str:
    return (
        "Tender metadata:\n"
        f"{json.dumps(tender_metadata, ensure_ascii=False, indent=2, sort_keys=True)}\n\n"
        "Extracted requirements:\n"
        f"{json.dumps(requirements, ensure_ascii=False, indent=2)}\n\n"
        "Extracted eligibility criteria:\n"
        f"{json.dumps(eligibility, ensure_ascii=False, indent=2)}"
    )
