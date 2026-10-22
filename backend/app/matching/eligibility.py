"""
Deterministic eligibility checks: each verified `tender_eligibility` fact
is compared against the company profile and gets an outcome.

The rule throughout: a criterion is MET or NOT_MET only when the data
settles it. Missing profile data, a value the extraction could not read,
or a clause that reads two ways all give UNKNOWN — never a silent pass
and never a silent fail. Where a clause is ambiguous (e.g. "turnover of
X" without saying average or each year), every reading is evaluated and
a definite outcome is given only when they all agree.

Payment and benefit clauses (EMD, tender fee, performance security,
MSME/startup provisions) are INFO, not pass/fail gates.
"""
import re
from collections.abc import Callable

from app.matching.text import format_inr, normalise, number
from app.matching.types import (
    CompanyProfile,
    CriterionCheck,
    EligibilityFact,
    Experience,
    TenderCategoryTag,
    TenderFacts,
)
from app.models.enums import (
    CriterionOutcome,
    CustomerType,
    EligibilityCriterionType,
    EligibilityStatus,
    TenderCategory,
)

MET, NOT_MET, UNKNOWN, INFO = (
    CriterionOutcome.MET,
    CriterionOutcome.NOT_MET,
    CriterionOutcome.UNKNOWN,
    CriterionOutcome.INFO,
)

DEFAULT_TURNOVER_PERIOD_YEARS = 3
GOVERNMENT_CUSTOMERS = {CustomerType.GOVERNMENT, CustomerType.PSU}
# A clause naming any of these restricts which past projects count.
_GOVT_CLIENT_PATTERN = re.compile(
    r"\b(government|govt|psus?|public sector|ministry|ministries|local bod(y|ies)|municipal)",
    re.IGNORECASE,
)
_ANY_ONE_YEAR_PATTERN = re.compile(r"\bany\s+(one\s+)?(of\s+the\s+)?(last|preceding|previous)\b", re.IGNORECASE)
_STARTUP_PATTERN = re.compile(r"\bstart[\s-]?ups?\b", re.IGNORECASE)
_MSE_PATTERN = re.compile(r"\b(msmes?|mses?|micro|small enterprises?|udyam|nsic)\b", re.IGNORECASE)

MSE_KINDS = {"msme_exemption", "msme_preference", "mse_purchase_preference"}
STARTUP_KINDS = {"startup_exemption"}
RELAXATION_TARGETS = {
    "turnover_relaxation": {EligibilityCriterionType.TURNOVER},
    "experience_relaxation": {
        EligibilityCriterionType.SIMILAR_PROJECTS,
        EligibilityCriterionType.YEARS_OF_EXPERIENCE,
        EligibilityCriterionType.GOVERNMENT_EXPERIENCE,
    },
}


def _check(fact: EligibilityFact, outcome: CriterionOutcome, text: str, **profile_evidence) -> CriterionCheck:
    return CriterionCheck(
        criterion_type=fact.criterion_type,
        outcome=outcome,
        text=text,
        citation=fact.citation,
        profile_evidence=profile_evidence,
    )


def _all_or_unknown(fact: EligibilityFact, readings: dict[str, bool], met: str, not_met: str, **evidence):
    """Definite outcome only if every reading of the clause agrees."""
    if all(readings.values()):
        return _check(fact, MET, met, readings=readings, **evidence)
    if not any(readings.values()):
        return _check(fact, NOT_MET, not_met, readings=readings, **evidence)
    passing = ", ".join(name for name, ok in readings.items() if ok)
    failing = ", ".join(name for name, ok in readings.items() if not ok)
    return _check(
        fact,
        UNKNOWN,
        f"Depends on how the clause is read: met on {passing}, not met on {failing}. Review the clause.",
        readings=readings,
        **evidence,
    )


# ------------------------------------------------------------ financial


def check_turnover(fact: EligibilityFact, profile: CompanyProfile) -> CriterionCheck:
    required = number(fact.value.get("amount_inr"))
    if required is None:
        return _check(fact, UNKNOWN, "The required turnover amount could not be read from the clause.")
    if not profile.turnover_by_year:
        return _check(fact, UNKNOWN, "No turnover figures are recorded in the company profile.")

    period = number(fact.value.get("period_years"))
    period_note = ""
    if period is None:
        period = DEFAULT_TURNOVER_PERIOD_YEARS
        period_note = f" The clause does not state a period; the last {DEFAULT_TURNOVER_PERIOD_YEARS} years were used."
    period = int(period)

    years = sorted(profile.turnover_by_year, key=lambda y: y.financial_year, reverse=True)[:period]
    used = {y.financial_year: y.amount_inr for y in years}
    if len(years) < period:
        return _check(
            fact,
            UNKNOWN,
            f"The clause covers {period} financial years but the profile records only {len(years)}.",
            turnover_used=used,
        )

    amounts = [y.amount_inr for y in years]
    average, lowest, highest = sum(amounts) / len(amounts), min(amounts), max(amounts)
    figures = (
        f"Average {format_inr(average)}, lowest {format_inr(lowest)} over {', '.join(sorted(used))}"
        f" against {format_inr(required)} required.{period_note}"
    )

    is_average = fact.value.get("is_average")
    if _ANY_ONE_YEAR_PATTERN.search(fact.text):
        readings = {"best year": highest >= required}
    elif is_average is True:
        readings = {"average": average >= required}
    elif is_average is False:
        readings = {"every year": lowest >= required}
    else:
        readings = {"average": average >= required, "every year": lowest >= required}

    return _all_or_unknown(
        fact, readings, f"Turnover requirement met. {figures}", f"Turnover below requirement. {figures}",
        turnover_used=used,
    )


def check_net_worth(fact: EligibilityFact, profile: CompanyProfile) -> CriterionCheck:
    if profile.net_worth_inr is None:
        return _check(fact, UNKNOWN, "Net worth is not recorded in the company profile.")
    evidence = {"net_worth_inr": profile.net_worth_inr}
    required = number(fact.value.get("amount_inr"))
    if required is None:
        if re.search(r"\bpositive\b", fact.text, re.IGNORECASE):
            ok = profile.net_worth_inr > 0
            return _check(
                fact, MET if ok else NOT_MET, f"Clause requires positive net worth; profile records "
                f"{format_inr(profile.net_worth_inr)}.", **evidence,
            )
        return _check(fact, UNKNOWN, "The required net worth could not be read from the clause.", **evidence)
    ok = profile.net_worth_inr >= required
    return _check(
        fact,
        MET if ok else NOT_MET,
        f"Net worth {format_inr(profile.net_worth_inr)} against {format_inr(required)} required.",
        **evidence,
    )


# ----------------------------------------------------------- experience


def _and3(values: list[bool | None]) -> bool | None:
    """Three-valued AND: False beats None beats True."""
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True


def _count_projects(
    fact: EligibilityFact,
    profile: CompanyProfile,
    tender: TenderFacts,
    *,
    require_govt: bool,
    require_similar: bool,
    label: str,
) -> CriterionCheck:
    if not profile.experience:
        return _check(fact, UNKNOWN, "No past projects are recorded in the company profile.")

    needed = int(number(fact.value.get("project_count")) or 1)
    min_value = number(fact.value.get("min_project_value_inr"))
    categories = {tag.category for tag in effective_categories(tender)}

    def qualifies(exp: Experience) -> bool | None:
        tests: list[bool | None] = []
        if min_value is not None:
            tests.append(None if exp.value_inr is None else exp.value_inr >= min_value)
        if require_govt:
            tests.append(exp.customer_type in GOVERNMENT_CUSTOMERS)
        if require_similar:
            tests.append(None if not categories or exp.capability is None else exp.capability in categories)
        return _and3(tests)

    results = {exp.id: qualifies(exp) for exp in profile.experience}
    definite = [exp for exp in profile.experience if results[exp.id] is True]
    possible = [exp for exp in profile.experience if results[exp.id] is not False]

    conditions = []
    if min_value is not None:
        conditions.append(f"worth at least {format_inr(min_value)}")
    if require_govt:
        conditions.append("for government/PSU clients")
    if require_similar:
        conditions.append("in this tender's categories")
    need_text = f"{needed} {label}{'s' if needed != 1 else ''}" + (f" {', '.join(conditions)}" if conditions else "")
    evidence = {
        "qualifying_projects": [{"id": e.id, "project_name": e.project_name} for e in definite],
        "unconfirmed_projects": [
            {"id": e.id, "project_name": e.project_name} for e in possible if results[e.id] is None
        ],
    }

    if len(definite) >= needed:
        return _check(fact, MET, f"Needs {need_text}; {len(definite)} recorded project(s) qualify.", **evidence)
    if len(possible) >= needed:
        reasons = []
        if require_similar and not categories:
            reasons.append("the tender has no category to judge similarity against")
        if any(e.capability is None for e in possible if results[e.id] is None) and require_similar:
            reasons.append("some projects have no capability set")
        if min_value is not None and any(e.value_inr is None for e in possible if results[e.id] is None):
            reasons.append("some projects have no value recorded")
        why = f" ({'; '.join(reasons)})" if reasons else ""
        return _check(
            fact,
            UNKNOWN,
            f"Needs {need_text}; {len(definite)} confirmed, {len(possible) - len(definite)} more cannot be "
            f"confirmed from the profile{why}.",
            **evidence,
        )
    return _check(fact, NOT_MET, f"Needs {need_text}; only {len(definite)} recorded project(s) qualify.", **evidence)


def check_similar_projects(fact: EligibilityFact, profile: CompanyProfile, tender: TenderFacts) -> CriterionCheck:
    return _count_projects(
        fact,
        profile,
        tender,
        require_govt=bool(_GOVT_CLIENT_PATTERN.search(fact.text)),
        require_similar=True,
        label="similar project",
    )


def check_government_experience(
    fact: EligibilityFact, profile: CompanyProfile, tender: TenderFacts
) -> CriterionCheck:
    return _count_projects(
        fact, profile, tender, require_govt=True, require_similar=False, label="government/PSU project"
    )


def check_years_of_experience(fact: EligibilityFact, profile: CompanyProfile) -> CriterionCheck:
    required = number(fact.value.get("years"))
    if required is None:
        return _check(fact, UNKNOWN, "The required number of years could not be read from the clause.")
    if profile.years_in_business is None:
        return _check(fact, UNKNOWN, "Years in business is not recorded in the company profile.")
    ok = profile.years_in_business >= required
    return _check(
        fact,
        MET if ok else NOT_MET,
        f"{profile.years_in_business} years in business against {required:g} required.",
        years_in_business=profile.years_in_business,
    )


# -------------------------------------------------------- certification

_ISO_PATTERN = re.compile(r"\bISO\s*/?\s*(?:IEC\s*)?[:\-]?\s*(\d{4,5})", re.IGNORECASE)
_CMMI_PATTERN = re.compile(r"\bCMMI\b[^.;\d]{0,30}?(?:level|ML|L)\s*[-:]?\s*(\d)", re.IGNORECASE)
_CERT_IN_PATTERN = re.compile(r"\bCERT[\s-]?In\b", re.IGNORECASE)


def parse_certifications(text: str) -> dict[str, int | bool]:
    """Recognised certificates in `text` → `{"iso:27001": True,
    "cmmi": 3, "cert-in": True}` (CMMI keyed by its level)."""
    found: dict[str, int | bool] = {f"iso:{m}": True for m in _ISO_PATTERN.findall(text)}
    levels = [int(level) for level in _CMMI_PATTERN.findall(text)]
    if levels:
        found["cmmi"] = min(levels)
    if _CERT_IN_PATTERN.search(text):
        found["cert-in"] = True
    return found


def check_certification(fact: EligibilityFact, profile: CompanyProfile) -> CriterionCheck:
    held_names = profile.all_certifications
    if not held_names:
        return _check(fact, UNKNOWN, "No certifications are recorded in the company profile.")

    held: dict[str, int | bool] = {}
    for name in held_names:
        for key, value in parse_certifications(name).items():
            held[key] = max(held.get(key, 0), value) if key == "cmmi" else True

    required = parse_certifications(fact.text)
    if not required:
        clause = normalise(fact.text)
        matched = [name for name in held_names if normalise(name) and normalise(name) in clause]
        if matched:
            return _check(fact, MET, f"Profile holds {', '.join(matched)}, named in the clause.", held=held_names)
        return _check(
            fact, UNKNOWN, "Could not identify which certification the clause requires.", held=held_names
        )

    def has(key: str, value: int | bool) -> bool:
        if key == "cmmi":
            return int(held.get("cmmi", 0)) >= int(value)
        return key in held

    def label(key: str, value: int | bool) -> str:
        return f"CMMI Level {value}" if key == "cmmi" else key.replace("iso:", "ISO ").replace("cert-in", "CERT-In")

    status = {label(k, v): has(k, v) for k, v in required.items()}
    any_of = len(required) > 1 and re.search(r"\bor\b", fact.text, re.IGNORECASE)
    ok = any(status.values()) if any_of else all(status.values())
    held_list = [name for name, ok_ in status.items() if ok_]
    missing = [name for name, ok_ in status.items() if not ok_]
    if ok:
        text = f"Profile holds {', '.join(held_list)}" + (" (any one is accepted)." if any_of else ".")
    else:
        text = f"Profile does not hold {' or '.join(missing) if any_of else ', '.join(missing)}."
    return _check(fact, MET if ok else NOT_MET, text, required=list(status), held=held_names)


# ------------------------------------------------------- payments, MSME


def msme_clause_applies(fact: EligibilityFact, profile: CompanyProfile) -> bool | None:
    """Whether an MSME/startup clause benefits this company: True/False, or
    None when the relevant registration status isn't recorded."""
    kind = fact.value.get("msme_clause_kind")
    if kind in MSE_KINDS:
        groups = ["mse"]
    elif kind in STARTUP_KINDS:
        groups = ["startup"]
    else:
        groups = [
            g for g, pattern in (("mse", _MSE_PATTERN), ("startup", _STARTUP_PATTERN)) if pattern.search(fact.text)
        ] or ["mse", "startup"]
    flags = [profile.msme_registered if g == "mse" else profile.startup_registered for g in groups]
    if any(f is True for f in flags):
        return True
    if any(f is None for f in flags):
        return None
    return False


def check_msme(fact: EligibilityFact, profile: CompanyProfile) -> CriterionCheck:
    applies = msme_clause_applies(fact, profile)
    kind = (fact.value.get("msme_clause_kind") or "provision").replace("_", " ")
    evidence = {"msme_registered": profile.msme_registered, "startup_registered": profile.startup_registered}
    if applies is True:
        check = _check(fact, INFO, f"MSME/startup {kind} — the company's registration qualifies.", **evidence)
        check.polarity_override = "support"
        return check
    if applies is None:
        return _check(fact, INFO, f"MSME/startup {kind} — registration status not recorded in the profile.", **evidence)
    return _check(fact, INFO, f"MSME/startup {kind} — does not apply to the company.", **evidence)


def check_payment(fact: EligibilityFact, profile: CompanyProfile, exemptions: list[EligibilityFact]) -> CriterionCheck:
    amount = number(fact.value.get("amount_inr"))
    name = {
        EligibilityCriterionType.EMD: "EMD",
        EligibilityCriterionType.TENDER_FEE: "Tender fee",
        EligibilityCriterionType.PERFORMANCE_SECURITY: "Performance security",
    }[fact.criterion_type]
    text = f"{name} of {format_inr(amount)} payable." if amount is not None else f"{name} payable."
    if exemptions:
        pages = ", ".join(f"p.{e.citation.page_number}" for e in exemptions)
        text += f" An exemption the company qualifies for applies ({pages})."
    return _check(fact, INFO, text, amount_inr=amount, exempt=bool(exemptions))


# ---------------------------------------------------------------- driver


def effective_categories(tender: TenderFacts) -> list[TenderCategoryTag]:
    """Categories trusted for matching: manual ones, and AI-assigned ones
    with confidence >= 0.5. `other` never counts as a match."""
    return [
        tag
        for tag in tender.categories
        if tag.category is not TenderCategory.OTHER and (tag.confidence is None or tag.confidence >= 0.5)
    ]


def check_criteria(tender: TenderFacts, profile: CompanyProfile) -> list[CriterionCheck]:
    msme_facts = [f for f in tender.eligibility if f.criterion_type is EligibilityCriterionType.MSME_STARTUP]
    applicable_msme = [f for f in msme_facts if msme_clause_applies(f, profile) is True]
    exemption_for = {
        EligibilityCriterionType.EMD: [
            f for f in applicable_msme if f.value.get("msme_clause_kind") in ("emd_exemption", "msme_exemption")
        ],
        EligibilityCriterionType.TENDER_FEE: [
            f for f in applicable_msme if f.value.get("msme_clause_kind") in ("tender_fee_exemption", "msme_exemption")
        ],
        EligibilityCriterionType.PERFORMANCE_SECURITY: [],
    }

    checkers: dict[EligibilityCriterionType, Callable[[EligibilityFact], CriterionCheck]] = {
        EligibilityCriterionType.TURNOVER: lambda f: check_turnover(f, profile),
        EligibilityCriterionType.NET_WORTH: lambda f: check_net_worth(f, profile),
        EligibilityCriterionType.SIMILAR_PROJECTS: lambda f: check_similar_projects(f, profile, tender),
        EligibilityCriterionType.GOVERNMENT_EXPERIENCE: lambda f: check_government_experience(f, profile, tender),
        EligibilityCriterionType.YEARS_OF_EXPERIENCE: lambda f: check_years_of_experience(f, profile),
        EligibilityCriterionType.CERTIFICATION: lambda f: check_certification(f, profile),
        EligibilityCriterionType.MSME_STARTUP: lambda f: check_msme(f, profile),
        EligibilityCriterionType.EMD: lambda f: check_payment(f, profile, exemption_for[f.criterion_type]),
        EligibilityCriterionType.TENDER_FEE: lambda f: check_payment(f, profile, exemption_for[f.criterion_type]),
        EligibilityCriterionType.PERFORMANCE_SECURITY: lambda f: check_payment(f, profile, []),
    }

    checks = []
    for fact in tender.eligibility:
        checker = checkers.get(fact.criterion_type)
        if checker is None:
            checks.append(_check(fact, UNKNOWN, "This criterion cannot be checked automatically — review the clause."))
            continue
        check = checker(fact)
        if check.outcome is NOT_MET:
            _apply_relaxations(check, fact, applicable_msme)
        checks.append(check)
    return checks


def _apply_relaxations(check: CriterionCheck, fact: EligibilityFact, applicable_msme: list[EligibilityFact]) -> None:
    """A failed turnover/experience criterion is downgraded to UNKNOWN when
    the tender relaxes it for MSEs/startups and the company qualifies —
    whether the relaxation covers this exact criterion is for a person."""
    relaxing = [
        f for f in applicable_msme
        if fact.criterion_type in RELAXATION_TARGETS.get(f.value.get("msme_clause_kind"), set())
    ]
    if relaxing:
        pages = ", ".join(f"{r.citation.file_name} p.{r.citation.page_number}" for r in relaxing)
        check.outcome = UNKNOWN
        check.text += f" However, the tender relaxes this for MSEs/startups ({pages}) and the company qualifies — " \
            "confirm the relaxation covers this criterion."
        check.profile_evidence["relaxed_by"] = [r.citation.fact_id for r in relaxing]


def overall_status(tender: TenderFacts, checks: list[CriterionCheck]) -> tuple[EligibilityStatus, list[CriterionCheck]]:
    """Verdict plus any synthetic reasons explaining an UNCERTAIN with no
    failing criterion to point at. ELIGIBLE needs at least one gate
    criterion checked and every gate MET."""
    gates = [c for c in checks if c.is_gate]
    extra: list[CriterionCheck] = []
    if any(c.outcome is NOT_MET for c in gates):
        return EligibilityStatus.NOT_ELIGIBLE, extra
    if not gates:
        if not tender.analysed:
            text = "The tender documents have not been analysed yet, so no eligibility criteria are known."
        else:
            text = "No pass/fail eligibility criteria were found in the analysed documents — check them manually."
        extra.append(CriterionCheck(criterion_type=None, outcome=UNKNOWN, text=text, citation=None))
        return EligibilityStatus.UNCERTAIN, extra
    if any(c.outcome is UNKNOWN for c in gates):
        return EligibilityStatus.UNCERTAIN, extra
    return EligibilityStatus.ELIGIBLE, extra
