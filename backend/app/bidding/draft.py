"""
Draft bid generation: one LLM call that writes the prose of a bid from
the tender's verified facts, its qualification result and the company
profile, then deterministic code that checks and assembles it.

Pure with respect to the database — the service builds `DraftInputs`
from ORM rows. Flow:

    build_prompt(inputs) -> llm.complete_json(BID_DRAFT_SCHEMA)
    -> verify(data, inputs)  (grounding + reference checks; any problem
       rejects the draft)
    -> assemble(data, inputs)  (every requirement/criterion gets a row —
       one the model skipped becomes a [TO FILL] placeholder — and
       citations, projects and enclosures come from stored data, not the
       model)
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.bidding import grounding
from app.core.exceptions import DomainError
from app.matching.text import format_inr

DRAFT_DISCLAIMER = (
    "AI DRAFT — review before use. Written by an AI model from the tender's verified clauses and the company "
    "profile, and checked so it states no amount, certification or project that isn't in them. Every "
    "[TO FILL] item must be completed, and every statement checked, by the bid team before submission. "
    "The system does not submit bids."
)


UNMET = {"NOT_MET", "UNKNOWN"}


class DraftGroundingError(DomainError):
    def __init__(self, problems: list[str]):
        super().__init__(f"The generated draft was rejected: {len(problems)} unsupported statement(s)")
        self.problems = problems


def _nullable(type_name: str) -> dict[str, Any]:
    return {"anyOf": [{"type": type_name}, {"type": "null"}]}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


BID_DRAFT_SCHEMA: dict[str, Any] = _object(
    {
        "covering_letter": {"type": "string"},
        "company_overview": {"type": "string"},
        "eligibility_compliance": {
            "type": "array",
            "items": _object({"criterion_ref": {"type": "string"}, "statement": {"type": "string"}}),
        },
        "technical_compliance": {
            "type": "array",
            "items": _object({"requirement_ref": {"type": "string"}, "response": {"type": "string"}}),
        },
        "manpower_plan": {
            "type": "array",
            "items": _object({"requirement_ref": {"type": "string"}, "proposed_resource": {"type": "string"}}),
        },
        "relevant_project_refs": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
    }
)

DRAFT_SYSTEM = """\
You draft bids for an Indian IT services company responding to a government \
tender. You receive the tender's verified clauses (requirements R#, \
eligibility criteria E#), the company's own assessment of each criterion, the \
company profile, its past projects (P#) and the list of documents to enclose. \
Write in clear, formal bid language.

Strict rules — the draft is checked automatically and rejected if broken:
- Use only the input. Every amount, turnover, net worth, certification, \
number of years, employee count or other fact about the company must come \
from `company` or `past_projects`. Never invent or round figures.
- Where something needed is not in the input (a name, signatory, date, \
reference number, document detail, missing figure), write a placeholder in \
exactly this form: [TO FILL: what is needed]. Prefer a placeholder to a guess.
- Never state that the company meets a criterion whose `assessment` is \
NOT_MET or UNKNOWN. For those, state what the criterion needs and put the \
company's evidence in a [TO FILL: ...] placeholder.
- Do not name past projects or clients in the text. List the relevant ones \
by their P# ids in `relevant_project_refs`; they are inserted from the \
profile.
- `eligibility_compliance`: one entry per E# criterion, `criterion_ref` set to \
its id. `technical_compliance`: one entry per non-manpower R# requirement. \
`manpower_plan`: one entry per manpower R# requirement; proposed resource \
names are always [TO FILL: ...].
- `covering_letter`: addressed to the issuing organisation if named in the \
input, else a placeholder; signatory name, designation and date are \
placeholders.
- `assumptions`: short, neutral points the bid team should confirm. Do not \
introduce new commercial terms or commitments."""


@dataclass
class FactRef:
    ref: str
    kind: str  # requirement category / criterion type
    summary: str
    clause: str
    citation: dict[str, Any]  # document_id, file_name, page_number
    details: dict[str, Any] = field(default_factory=dict)
    assessment: str | None = None  # eligibility only: MET / NOT_MET / UNKNOWN / INFO
    assessment_note: str | None = None


@dataclass
class ProjectRef:
    ref: str
    project_name: str
    client_name: str | None
    customer_type: str
    capability: str | None
    value_inr: float | None
    year: int | None
    technologies: list[str]


@dataclass
class DraftInputs:
    tender: dict[str, Any]  # title, tender_number, organisation, closing_date, tender_value_inr, emd_inr
    requirements: list[FactRef]
    eligibility: list[FactRef]
    company: dict[str, Any]  # profile fields that are recorded + `not_recorded`
    projects: list[ProjectRef]
    enclosures: list[dict[str, Any]]  # checklist rows
    # Structured numbers the text may legitimately restate.
    extra_amounts: set[float] = field(default_factory=set)
    extra_years: set[int] = field(default_factory=set)

    @property
    def manpower_refs(self) -> set[str]:
        return {r.ref for r in self.requirements if r.kind == "manpower"}


def build_prompt(inputs: DraftInputs) -> str:
    payload = {
        "tender": inputs.tender,
        "requirements": [
            {"ref": r.ref, "category": r.kind, "summary": r.summary, "clause": r.clause, "details": r.details}
            for r in inputs.requirements
        ],
        "eligibility": [
            {
                "ref": e.ref,
                "criterion_type": e.kind,
                "summary": e.summary,
                "clause": e.clause,
                "assessment": e.assessment,
                "assessment_note": e.assessment_note,
            }
            for e in inputs.eligibility
        ],
        "company": inputs.company,
        "past_projects": [
            {
                "ref": p.ref,
                "project_name": p.project_name,
                "client_name": p.client_name,
                "customer_type": p.customer_type,
                "capability": p.capability,
                "value": format_inr(p.value_inr) if p.value_inr is not None else None,
                "year": p.year,
                "technologies": p.technologies,
            }
            for p in inputs.projects
        ],
        "documents_to_enclose": [e["title"] for e in inputs.enclosures],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _allowed(inputs: DraftInputs, prompt: str) -> tuple[set[float], set[int], set[str]]:
    amounts = set(grounding.amounts(prompt)) | inputs.extra_amounts
    years = grounding.years(prompt) | inputs.extra_years
    # A certification may be restated only if the company holds it (profile)
    # or it is part of what the solution must deliver (requirement clauses) —
    # never just because an eligibility clause asks for it.
    held = " ".join(map(str, inputs.company.get("certifications", [])))
    held += " " + " ".join(c for cap in inputs.company.get("capabilities", []) for c in cap.get("certifications", []))
    certs = grounding.certifications(held) | grounding.certifications(" ".join(r.clause for r in inputs.requirements))
    return amounts, years, certs


def _texts(data: dict[str, Any]) -> list[tuple[str, str]]:
    out = [("covering letter", data.get("covering_letter", "")), ("company overview", data.get("company_overview", ""))]
    out += [(f"eligibility {e.get('criterion_ref')}", e.get("statement", "")) for e in data.get("eligibility_compliance", [])]
    out += [(f"technical {t.get('requirement_ref')}", t.get("response", "")) for t in data.get("technical_compliance", [])]
    out += [(f"manpower {m.get('requirement_ref')}", m.get("proposed_resource", "")) for m in data.get("manpower_plan", [])]
    out += [("assumptions", a) for a in data.get("assumptions", [])]
    return out


def verify(data: dict[str, Any], inputs: DraftInputs, prompt: str) -> list[str]:
    """Every problem found; an empty list means the draft may be stored."""
    problems: list[str] = []
    e_refs = {e.ref for e in inputs.eligibility}
    r_refs = {r.ref for r in inputs.requirements}
    p_refs = {p.ref for p in inputs.projects}
    for e in data.get("eligibility_compliance", []):
        if e.get("criterion_ref") not in e_refs:
            problems.append(f"eligibility: unknown criterion reference {e.get('criterion_ref')!r}")
    for t in data.get("technical_compliance", []):
        if t.get("requirement_ref") not in r_refs:
            problems.append(f"technical: unknown requirement reference {t.get('requirement_ref')!r}")
    for m in data.get("manpower_plan", []):
        if m.get("requirement_ref") not in inputs.manpower_refs:
            problems.append(f"manpower: {m.get('requirement_ref')!r} is not a manpower requirement")
    for ref in data.get("relevant_project_refs", []):
        if ref not in p_refs:
            problems.append(f"projects: unknown past project reference {ref!r}")

    amounts, years, certs = _allowed(inputs, prompt)
    criteria = {e.ref: e for e in inputs.eligibility}
    for where, text in _texts(data):
        allowed_certs = certs
        if where.startswith("eligibility "):
            criterion = criteria.get(where.removeprefix("eligibility "))
            if criterion is not None:
                # A statement may restate what its own criterion asks for...
                allowed_certs = certs | grounding.certifications(criterion.clause)
                # ...but one the company doesn't meet must leave the evidence open.
                if criterion.assessment in UNMET and not grounding.find_placeholders(text or ""):
                    problems.append(
                        f"{where}: the company's assessment is {criterion.assessment}, so the statement must leave "
                        "the evidence as a [TO FILL] placeholder rather than claim compliance"
                    )
        problems += grounding.check_text(
            where, text or "", allowed_amounts=amounts, allowed_years=years, allowed_certifications=allowed_certs
        )
    return problems


def _placeholder(what: str) -> str:
    return f"[TO FILL: {what}]"


def assemble(data: dict[str, Any], inputs: DraftInputs, generated_at: datetime, model: str) -> tuple[dict, list]:
    """The stored draft. Rows come from the stored facts in their order, so a
    requirement the model skipped still appears — as a placeholder."""
    by_e = {e["criterion_ref"]: e["statement"] for e in data.get("eligibility_compliance", [])}
    by_t = {t["requirement_ref"]: t["response"] for t in data.get("technical_compliance", [])}
    by_m = {m["requirement_ref"]: m["proposed_resource"] for m in data.get("manpower_plan", [])}
    projects = {p.ref: p for p in inputs.projects}

    content = {
        "disclaimer": DRAFT_DISCLAIMER,
        "generated_at": generated_at.isoformat(),
        "generated_by_model": model,
        "tender": inputs.tender,
        "company_name": inputs.company.get("company_name"),
        "covering_letter": data.get("covering_letter") or _placeholder("covering letter"),
        "company_overview": data.get("company_overview") or _placeholder("company overview"),
        "eligibility_compliance": [
            {
                "ref": e.ref,
                "criterion_type": e.kind,
                "criterion": e.summary,
                "assessment": e.assessment,
                "statement": by_e.get(e.ref) or _placeholder("compliance statement and supporting evidence"),
                "citation": e.citation,
            }
            for e in inputs.eligibility
        ],
        "technical_compliance": [
            {
                "ref": r.ref,
                "category": r.kind,
                "requirement": r.summary,
                "response": by_t.get(r.ref) or _placeholder("compliance response"),
                "citation": r.citation,
            }
            for r in inputs.requirements
            if r.kind != "manpower"
        ],
        "manpower_plan": [
            {
                "ref": r.ref,
                "role": r.details.get("role") or r.summary,
                "count": r.details.get("resource_count"),
                "min_experience_years": r.details.get("min_experience_years"),
                "proposed_resource": by_m.get(r.ref) or _placeholder("name(s) of proposed resource"),
                "citation": r.citation,
            }
            for r in inputs.requirements
            if r.kind == "manpower"
        ],
        "relevant_projects": [
            {
                "project_name": p.project_name,
                "client_name": p.client_name,
                "customer_type": p.customer_type,
                "value_inr": p.value_inr,
                "year": p.year,
            }
            for ref in data.get("relevant_project_refs", [])
            if (p := projects.get(ref))
        ],
        "assumptions": list(data.get("assumptions", [])),
        "enclosures": inputs.enclosures,
    }

    placeholders = []
    for where, text in _texts(
        {
            "covering_letter": content["covering_letter"],
            "company_overview": content["company_overview"],
            "eligibility_compliance": [
                {"criterion_ref": e["ref"], "statement": e["statement"]} for e in content["eligibility_compliance"]
            ],
            "technical_compliance": [
                {"requirement_ref": t["ref"], "response": t["response"]} for t in content["technical_compliance"]
            ],
            "manpower_plan": [
                {"requirement_ref": m["ref"], "proposed_resource": m["proposed_resource"]}
                for m in content["manpower_plan"]
            ],
            "assumptions": content["assumptions"],
        }
    ):
        placeholders += [{"section": where, "text": p} for p in grounding.find_placeholders(text)]
    return content, placeholders
