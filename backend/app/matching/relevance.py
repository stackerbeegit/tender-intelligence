"""
Relevance scoring (docs/architecture.md §7): eight named factors, each a
0–100 score with a weight, an explanation and the evidence it used. A
factor whose inputs are missing is marked `known: false` and scored a
neutral 50, so missing data neither boosts nor sinks a tender.

The overall score is only ever `relevance_score(factors)` — a weighted
mean of the stored factors — so "why is this relevant?" is answered by
the factor rows, not by re-asking anything.
"""
import re
from datetime import datetime

from app.matching.eligibility import effective_categories, msme_clause_applies
from app.matching.text import format_inr, normalise, number
from app.matching.types import CompanyProfile, CriterionCheck, Factor, TenderFacts
from app.models.enums import CriterionOutcome, EligibilityCriterionType, EligibilityStatus, RequirementCategory

WEIGHTS: dict[str, int] = {
    "technical": 30,
    "eligibility": 20,
    "experience": 15,
    "manpower": 10,
    "commercial": 10,
    "location": 5,
    "msme": 5,
    "deadline": 5,
}
NEUTRAL = 50
_ANYWHERE = {"panindia", "allindia", "india", "remote", "anywhere"}


def relevance_score(factors: dict[str, Factor] | dict[str, dict]) -> int:
    """Weighted mean of factor scores. Accepts stored dicts too, which is
    how tests prove a stored score is reconstructable from its factors."""
    rows = [f.as_dict() if isinstance(f, Factor) else f for f in factors.values()]
    total_weight = sum(r["weight"] for r in rows)
    if total_weight == 0:
        return 0
    return round(sum(r["score"] * r["weight"] for r in rows) / total_weight)


def _unknown(name: str, explanation: str) -> Factor:
    return Factor(score=NEUTRAL, weight=WEIGHTS[name], known=False, explanation=explanation)


def _known(name: str, score: float, explanation: str, evidence: list[dict] | None = None) -> Factor:
    return Factor(
        score=int(round(min(max(score, 0), 100))),
        weight=WEIGHTS[name],
        known=True,
        explanation=explanation,
        evidence=evidence or [],
    )


def _tokens(name: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", name.lower()))


def _technology_matches(required: str, offered: list[str]) -> bool:
    """Same name once punctuation is ignored ("Node.js" = "NodeJS"), or one
    name's words contained in the other's ("REST" covers "REST API") —
    whole words only, so "Java" does not cover "JavaScript"."""
    req_norm, req_tokens = normalise(required), _tokens(required)
    for name in offered:
        tokens = _tokens(name)
        if normalise(name) == req_norm or (tokens and req_tokens and (tokens <= req_tokens or req_tokens <= tokens)):
            return True
    return False


def technical_fit(tender: TenderFacts, profile: CompanyProfile) -> Factor:
    capabilities = {cap.category for cap in profile.capabilities}
    categories = sorted(effective_categories(tender), key=lambda t: -(t.confidence if t.confidence is not None else 1))
    subs: list[float] = []
    parts: list[str] = []
    evidence: list[dict] = []

    if categories and capabilities:
        matched = [t.category for t in categories if t.category in capabilities]
        if not matched:
            subs.append(0)
            parts.append("none of the tender's categories is a company capability")
        elif categories[0].category in capabilities:
            subs.append(100)
            parts.append(f"primary category {categories[0].category.value} is a company capability")
        else:
            subs.append(60)
            parts.append(f"secondary category matches ({', '.join(c.value for c in matched)})")
        evidence.append(
            {"tender_categories": [t.category.value for t in categories], "matched": [c.value for c in matched]}
        )

    offered = [t for t in profile.all_technologies if normalise(t)]
    required: dict[str, str] = {}
    for req in tender.requirements:
        for tech in req.details.get("technologies") or []:
            required.setdefault(normalise(tech), tech)
    required.pop("", None)
    if required and offered:
        covered = [name for name in required.values() if _technology_matches(name, offered)]
        missing = [name for name in required.values() if name not in covered]
        subs.append(100 * len(covered) / len(required))
        parts.append(f"{len(covered)} of {len(required)} named technologies covered")
        evidence.append({"technologies_covered": covered, "technologies_missing": missing})

    if not subs:
        if not capabilities:
            return _unknown("technical", "No capabilities are recorded in the company profile.")
        return _unknown("technical", "The tender has no category or named technologies to compare against.")
    return _known("technical", sum(subs) / len(subs), "; ".join(parts).capitalize() + ".", evidence)


def eligibility_confidence(status: EligibilityStatus, checks: list[CriterionCheck]) -> Factor:
    gates = [c for c in checks if c.is_gate and c.criterion_type is not None]
    if not gates:
        return _unknown("eligibility", "No pass/fail eligibility criteria have been checked.")
    met = sum(1 for c in gates if c.outcome is CriterionOutcome.MET)
    summary = f"{met} of {len(gates)} criteria met"
    if status is EligibilityStatus.ELIGIBLE:
        return _known("eligibility", 100, f"Eligible: {summary}.")
    if status is EligibilityStatus.NOT_ELIGIBLE:
        return _known("eligibility", 0, f"Not eligible: {summary}.")
    return _known("eligibility", 30 + 40 * met / len(gates), f"Uncertain: {summary}, the rest unconfirmed.")


def experience_fit(tender: TenderFacts, profile: CompanyProfile) -> Factor:
    if not profile.experience:
        return _unknown("experience", "No past projects are recorded in the company profile.")
    categories = {t.category for t in effective_categories(tender)}
    if not categories:
        return _unknown("experience", "The tender has no category to compare past projects against.")
    relevant = [e for e in profile.experience if e.capability in categories]
    score = {0: 10, 1: 50, 2: 75}.get(len(relevant), 100)
    return _known(
        "experience",
        score,
        f"{len(relevant)} past project(s) in this tender's categories.",
        [{"id": e.id, "project_name": e.project_name} for e in relevant],
    )


def manpower_fit(tender: TenderFacts, profile: CompanyProfile) -> Factor:
    manpower = [r for r in tender.requirements if r.category is RequirementCategory.MANPOWER]
    if not manpower:
        return _unknown("manpower", "The tender states no manpower requirement.")
    if not profile.employee_count:
        return _unknown("manpower", "Employee count is not recorded in the company profile.")
    required = sum(int(number(r.details.get("resource_count")) or 1) for r in manpower)
    share = required / profile.employee_count
    score = 100 if share <= 0.1 else 75 if share <= 0.25 else 50 if share <= 0.5 else 25 if share <= 1 else 0
    uncounted = sum(1 for r in manpower if number(r.details.get("resource_count")) is None)
    note = f" ({uncounted} role(s) state no count; 1 assumed each)" if uncounted else ""
    return _known(
        "manpower",
        score,
        f"{required} resource(s) required against {profile.employee_count} employees ({share:.0%}){note}.",
        [{"fact_id": r.citation.fact_id, "role": r.details.get("role"), "count": r.details.get("resource_count")}
         for r in manpower],
    )


def commercial_fit(tender: TenderFacts, profile: CompanyProfile) -> Factor:
    if tender.tender_value_inr is None:
        return _unknown("commercial", "The tender value is not stated.")
    value = tender.tender_value_inr
    project_values = [e.value_inr for e in profile.experience if e.value_inr]
    if project_values:
        largest = max(project_values)
        ratio = value / largest
        score = 100 if ratio <= 1 else 75 if ratio <= 2 else 40 if ratio <= 5 else 10
        return _known(
            "commercial",
            score,
            f"Tender value {format_inr(value)} is {ratio:.1f}× the largest past project ({format_inr(largest)}).",
        )
    if profile.turnover_by_year:
        latest = max(profile.turnover_by_year, key=lambda y: y.financial_year)
        ratio = value / latest.amount_inr if latest.amount_inr else float("inf")
        score = 100 if ratio <= 0.5 else 60 if ratio <= 1 else 20
        return _known(
            "commercial",
            score,
            f"Tender value {format_inr(value)} against {latest.financial_year} turnover of "
            f"{format_inr(latest.amount_inr)} (no past project values recorded).",
        )
    return _unknown("commercial", "No past project values or turnover are recorded to compare the tender value to.")


def location_fit(tender: TenderFacts, profile: CompanyProfile) -> Factor:
    locations = {normalise(loc) for loc in profile.locations if normalise(loc)}
    if not locations:
        return _unknown("location", "No operating locations are recorded in the company profile.")
    states = [s for s in tender.delivery_states if s] or ([tender.buyer_state] if tender.buyer_state else [])
    if not states:
        return _unknown("location", "The tender states no delivery location.")
    if locations & _ANYWHERE:
        return _known("location", 100, "The company operates pan-India.")
    matched = [s for s in states if normalise(s) in locations]
    if matched:
        return _known("location", 100, f"Delivery in {', '.join(matched)}, where the company operates.")
    return _known("location", 40, f"Delivery in {', '.join(states)}, outside the company's recorded locations.")


def msme_relevance(tender: TenderFacts, profile: CompanyProfile) -> Factor:
    clauses = [f for f in tender.eligibility if f.criterion_type is EligibilityCriterionType.MSME_STARTUP]
    if not clauses:
        return _unknown("msme", "The tender has no MSME/startup provisions.")
    applies = [msme_clause_applies(f, profile) for f in clauses]
    evidence = [{"fact_id": f.citation.fact_id, "applies": a} for f, a in zip(clauses, applies)]
    if any(a is True for a in applies):
        return _known("msme", 100, "The company qualifies for an MSME/startup provision in this tender.", evidence)
    if any(a is None for a in applies):
        return _unknown("msme", "MSME/startup registration status is not recorded in the company profile.")
    return _known("msme", 25, "The tender's MSME/startup provisions do not apply to the company.", evidence)


def deadline_fit(tender: TenderFacts, now: datetime) -> Factor:
    if tender.closing_date is None:
        return _unknown("deadline", "No closing date is recorded.")
    days = (tender.closing_date - now).total_seconds() / 86400
    if days < 0:
        return _known("deadline", 0, "Bid submission has closed.")
    score = 15 if days < 3 else 40 if days < 7 else 70 if days < 14 else 100
    return _known("deadline", score, f"{days:.0f} day(s) left to prepare the bid.")


def compute_factors(
    tender: TenderFacts,
    profile: CompanyProfile,
    status: EligibilityStatus,
    checks: list[CriterionCheck],
    now: datetime,
) -> dict[str, Factor]:
    return {
        "technical": technical_fit(tender, profile),
        "eligibility": eligibility_confidence(status, checks),
        "experience": experience_fit(tender, profile),
        "manpower": manpower_fit(tender, profile),
        "commercial": commercial_fit(tender, profile),
        "location": location_fit(tender, profile),
        "msme": msme_relevance(tender, profile),
        "deadline": deadline_fit(tender, now),
    }
