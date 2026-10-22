"""
Sprint 5 exit criteria, against the pure matching engine:

- ELIGIBLE / NOT_ELIGIBLE / UNCERTAIN verdicts, and UNKNOWN (never a pass,
  never a fail) whenever the data needed to decide is missing.
- The relevance score is always reconstructable from the stored factors.

The eligibility facts are the five verified clauses of the Sprint 4
representative RFP (tests/fixtures/intelligence/sample_rfp_expected.json),
so these rules are exercised on the same shape of data a real run stores.
"""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.matching.engine import qualify
from app.matching.relevance import WEIGHTS, relevance_score
from app.matching.types import (
    Capability,
    Citation,
    CompanyProfile,
    EligibilityFact,
    Experience,
    RequirementFact,
    TenderCategoryTag,
    TenderFacts,
    TurnoverYear,
)
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

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
EXPECTED = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "intelligence" / "sample_rfp_expected.json").read_text()
)
CR = 10_000_000  # one crore


def _citation(i: int, quote: str, page: int) -> Citation:
    return Citation(fact_id=f"fact-{i}", document_id="doc-1", file_name="RFP.pdf", page_number=page, quote=quote)


def eligibility_fact(criterion_type, quote, value=None, page=3, i=0) -> EligibilityFact:
    return EligibilityFact(
        criterion_type=EligibilityCriterionType(criterion_type),
        summary=quote[:60],
        value=value or {},
        citation=_citation(i, quote, page),
    )


RFP_ELIGIBILITY = [
    eligibility_fact(e["criterion_type"], e["criterion_text"], e["extracted_value"], e["page_number"], i)
    for i, e in enumerate(EXPECTED["eligibility"])
]
RFP_REQUIREMENTS = [
    RequirementFact(
        category=RequirementCategory(r["category"]),
        summary=r["requirement_text"][:60],
        details=r["details"],
        citation=_citation(100 + i, r["requirement_text"], r["page_number"]),
    )
    for i, r in enumerate(EXPECTED["requirements"])
]


def make_tender(**overrides) -> TenderFacts:
    base = TenderFacts(
        tender_id="t-1",
        status=TenderStatus.OPEN,
        closing_date=NOW + timedelta(days=30),
        tender_value_inr=5 * CR,
        categories=[TenderCategoryTag(TenderCategory.SOFTWARE_DEVELOPMENT, None)],
        delivery_states=["Punjab"],
        buyer_state="Punjab",
        analysed=True,
        eligibility=list(RFP_ELIGIBILITY),
        requirements=list(RFP_REQUIREMENTS),
    )
    return replace(base, **overrides)


def govt_project(i: int, value: float = 3 * CR, capability=TenderCategory.SOFTWARE_DEVELOPMENT, customer=None):
    return Experience(
        id=f"exp-{i}",
        project_name=f"State portal {i}",
        customer_type=customer or CustomerType.GOVERNMENT,
        capability=capability,
        technologies=["Java", "PostgreSQL", "REST"],
        value_inr=value,
        year=2024,
    )


def make_profile(**overrides) -> CompanyProfile:
    base = CompanyProfile(
        msme_registered=True,
        startup_registered=False,
        turnover_by_year=[
            TurnoverYear("2024-25", 14 * CR),
            TurnoverYear("2023-24", 12 * CR),
            TurnoverYear("2022-23", 11 * CR),
        ],
        net_worth_inr=6 * CR,
        years_in_business=9,
        employee_count=120,
        locations=["Punjab", "Haryana"],
        certifications=["ISO/IEC 27001:2022", "ISO 9001"],
        capabilities=[
            Capability(TenderCategory.SOFTWARE_DEVELOPMENT, ["Java", "PostgreSQL", "REST", "DigiLocker"], []),
        ],
        experience=[govt_project(1), govt_project(2), govt_project(3)],
    )
    return replace(base, **overrides)


def reason_for(outcome, criterion_type: str):
    return next(r for r in outcome.checks if r.criterion_type and r.criterion_type.value == criterion_type)


# ---------------------------------------------------------------- verdicts


def test_eligible_when_every_gate_criterion_is_met():
    outcome = qualify(make_tender(), make_profile(), NOW)

    assert outcome.eligibility_status is EligibilityStatus.ELIGIBLE
    gates = {r.criterion_type.value: r.outcome for r in outcome.checks if r.is_gate}
    assert gates == {
        "turnover": CriterionOutcome.MET,
        "similar_projects": CriterionOutcome.MET,
        "certification": CriterionOutcome.MET,
    }
    # EMD and the MSME clause are informational, not gates.
    assert reason_for(outcome, "emd").outcome is CriterionOutcome.INFO
    assert reason_for(outcome, "msme_startup").polarity == "support"


def test_every_reason_carries_the_clause_it_was_derived_from():
    outcome = qualify(make_tender(), make_profile(), NOW)
    for reason in outcome.checks:
        assert reason.citation is not None
        stored = reason.as_dict()["evidence"]
        assert stored["file_name"] == "RFP.pdf" and stored["page_number"] == 3
        assert stored["quote"] in {e["criterion_text"] for e in EXPECTED["eligibility"]}


def test_not_eligible_when_a_criterion_fails():
    low_turnover = [TurnoverYear(fy, 4 * CR) for fy in ("2024-25", "2023-24", "2022-23")]
    outcome = qualify(make_tender(), make_profile(turnover_by_year=low_turnover, msme_registered=False), NOW)

    assert outcome.eligibility_status is EligibilityStatus.NOT_ELIGIBLE
    turnover = reason_for(outcome, "turnover")
    assert turnover.outcome is CriterionOutcome.NOT_MET
    assert turnover.polarity == "concern"
    assert "₹4 Cr" in turnover.text and "₹10 Cr" in turnover.text
    assert any(r.severity is RiskSeverity.HIGH and r.risk == "Eligibility criterion not met" for r in outcome.risks)


def test_uncertain_when_a_criterion_cannot_be_confirmed():
    outcome = qualify(make_tender(), make_profile(certifications=["ISO 9001"]), NOW)
    # ISO 9001 recorded, 27001 required: a definite fail.
    assert outcome.eligibility_status is EligibilityStatus.NOT_ELIGIBLE

    only_two_years = [TurnoverYear("2024-25", 14 * CR), TurnoverYear("2023-24", 12 * CR)]
    outcome = qualify(make_tender(), make_profile(turnover_by_year=only_two_years), NOW)
    assert outcome.eligibility_status is EligibilityStatus.UNCERTAIN
    assert reason_for(outcome, "turnover").outcome is CriterionOutcome.UNKNOWN
    assert "only 2" in reason_for(outcome, "turnover").text


def test_not_met_beats_unknown():
    outcome = qualify(
        make_tender(),
        make_profile(turnover_by_year=[], certifications=["ISO 9001"]),  # turnover UNKNOWN, cert NOT_MET
        NOW,
    )
    assert outcome.eligibility_status is EligibilityStatus.NOT_ELIGIBLE


# ------------------------------------------------- UNKNOWN on missing data

TURNOVER = eligibility_fact("turnover", "Average annual turnover of Rs. 10 Crore in the last three years.",
                            {"amount_inr": 10 * CR, "period_years": 3, "is_average": True})
NET_WORTH = eligibility_fact("net_worth", "Net worth of at least Rs. 2 Crore.", {"amount_inr": 2 * CR})
YEARS = eligibility_fact("years_of_experience", "At least 5 years in IT services.", {"years": 5})
SIMILAR = eligibility_fact("similar_projects", "Two similar projects of Rs. 1 Crore each.",
                           {"project_count": 2, "min_project_value_inr": CR})
GOVT = eligibility_fact("government_experience", "Experience with at least one Government department.", {})
CERT = eligibility_fact("certification", "The bidder must hold ISO 27001.", {})


@pytest.mark.parametrize(
    "fact, profile_overrides",
    [
        (TURNOVER, {"turnover_by_year": []}),
        (NET_WORTH, {"net_worth_inr": None}),
        (YEARS, {"years_in_business": None}),
        (SIMILAR, {"experience": []}),
        (GOVT, {"experience": []}),
        (CERT, {"certifications": [], "capabilities": []}),
    ],
    ids=["turnover", "net_worth", "years", "similar_projects", "govt_experience", "certification"],
)
def test_missing_profile_data_gives_unknown_never_pass_or_fail(fact, profile_overrides):
    outcome = qualify(make_tender(eligibility=[fact]), make_profile(**profile_overrides), NOW)

    assert outcome.checks[0].outcome is CriterionOutcome.UNKNOWN
    assert outcome.eligibility_status is EligibilityStatus.UNCERTAIN


@pytest.mark.parametrize(
    "fact",
    [
        eligibility_fact("turnover", "Turnover as per Annexure 4.", {}),
        eligibility_fact("net_worth", "Net worth as specified in Annexure 4.", {}),
        eligibility_fact("years_of_experience", "Adequate years of experience.", {}),
        eligibility_fact("certification", "Relevant quality certifications.", {}),
        eligibility_fact("other", "The bidder must not be blacklisted.", {}),
    ],
    ids=["turnover", "net_worth", "years", "certification", "other"],
)
def test_unreadable_requirement_gives_unknown(fact):
    outcome = qualify(make_tender(eligibility=[fact]), make_profile(), NOW)
    assert outcome.checks[0].outcome is CriterionOutcome.UNKNOWN
    assert outcome.eligibility_status is EligibilityStatus.UNCERTAIN


def test_unanalysed_tender_is_uncertain_with_an_explanation_and_a_high_risk():
    outcome = qualify(make_tender(eligibility=[], requirements=[], analysed=False), make_profile(), NOW)

    assert outcome.eligibility_status is EligibilityStatus.UNCERTAIN
    assert outcome.checks[0].outcome is CriterionOutcome.UNKNOWN
    assert "not been analysed" in outcome.checks[0].text
    assert outcome.risks[0].risk == "Tender documents not analysed"
    assert outcome.risks[0].severity is RiskSeverity.HIGH


def test_payment_clauses_alone_never_make_a_tender_eligible():
    emd = eligibility_fact("emd", "EMD of Rs. 50,000.", {"amount_inr": 50_000})
    outcome = qualify(make_tender(eligibility=[emd]), make_profile(), NOW)
    assert outcome.eligibility_status is EligibilityStatus.UNCERTAIN
    assert "No pass/fail eligibility criteria" in outcome.checks[-1].text


# ------------------------------------------------------- individual rules


@pytest.mark.parametrize(
    "is_average, amounts, expected",
    [
        (None, [14, 12, 11], CriterionOutcome.MET),  # passes on both readings
        (None, [4, 4, 4], CriterionOutcome.NOT_MET),  # fails on both readings
        (None, [20, 12, 5], CriterionOutcome.UNKNOWN),  # average ok, one year short
        (True, [20, 12, 5], CriterionOutcome.MET),
        (False, [20, 12, 5], CriterionOutcome.NOT_MET),
    ],
)
def test_turnover_is_definite_only_when_every_reading_agrees(is_average, amounts, expected):
    fact = eligibility_fact("turnover", "Annual turnover of Rs. 10 Crore in the last three financial years.",
                            {"amount_inr": 10 * CR, "period_years": 3, "is_average": is_average})
    years = [TurnoverYear(fy, a * CR) for fy, a in zip(("2024-25", "2023-24", "2022-23"), amounts)]
    outcome = qualify(make_tender(eligibility=[fact]), make_profile(turnover_by_year=years), NOW)
    assert outcome.checks[0].outcome is expected


def test_turnover_in_any_one_year_uses_the_best_year():
    fact = eligibility_fact("turnover", "Turnover of Rs. 10 Crore in any one of the last three financial years.",
                            {"amount_inr": 10 * CR, "period_years": 3})
    years = [TurnoverYear(fy, a * CR) for fy, a in zip(("2024-25", "2023-24", "2022-23"), (11, 3, 2))]
    outcome = qualify(make_tender(eligibility=[fact]), make_profile(turnover_by_year=years), NOW)
    assert outcome.checks[0].outcome is CriterionOutcome.MET


def test_turnover_uses_the_most_recent_years():
    years = [TurnoverYear("2019-20", 1 * CR), TurnoverYear("2024-25", 14 * CR),
             TurnoverYear("2023-24", 12 * CR), TurnoverYear("2022-23", 11 * CR)]
    outcome = qualify(make_tender(eligibility=[TURNOVER]), make_profile(turnover_by_year=years), NOW)
    assert outcome.checks[0].outcome is CriterionOutcome.MET
    assert "2019-20" not in outcome.checks[0].profile_evidence["turnover_used"]


def test_similar_projects_counts_only_government_work_when_the_clause_says_so():
    projects = [govt_project(1), govt_project(2), govt_project(3, customer=CustomerType.PRIVATE)]
    outcome = qualify(make_tender(), make_profile(experience=projects), NOW)
    similar = reason_for(outcome, "similar_projects")
    assert similar.outcome is CriterionOutcome.NOT_MET
    assert len(similar.profile_evidence["qualifying_projects"]) == 2


def test_similar_projects_with_unrecorded_values_is_unknown_not_a_fail():
    projects = [govt_project(1), govt_project(2), govt_project(3, value=None)]
    outcome = qualify(make_tender(), make_profile(experience=projects), NOW)
    similar = reason_for(outcome, "similar_projects")
    assert similar.outcome is CriterionOutcome.UNKNOWN
    assert "no value recorded" in similar.text


def test_projects_in_another_category_are_not_similar():
    projects = [govt_project(i, capability=TenderCategory.NETWORKING_INFRASTRUCTURE) for i in range(3)]
    outcome = qualify(make_tender(), make_profile(experience=projects), NOW)
    assert reason_for(outcome, "similar_projects").outcome is CriterionOutcome.NOT_MET


def test_similarity_cannot_be_judged_without_a_tender_category():
    outcome = qualify(make_tender(categories=[]), make_profile(), NOW)
    similar = reason_for(outcome, "similar_projects")
    assert similar.outcome is CriterionOutcome.UNKNOWN
    assert "no category" in similar.text


@pytest.mark.parametrize(
    "clause, held, expected",
    [
        ("Valid CMMI Level 3 certification.", ["CMMI Level 5"], CriterionOutcome.MET),
        ("Valid CMMI Level 3 certification.", ["CMMI ML 2"], CriterionOutcome.NOT_MET),
        ("ISO 9001 or ISO 27001 certification.", ["ISO 27001"], CriterionOutcome.MET),
        ("ISO 9001 and ISO 27001 certification.", ["ISO 27001"], CriterionOutcome.NOT_MET),
        ("Empanelment with CERT-In.", ["CERT-In empanelled"], CriterionOutcome.MET),
        ("Must be an authorised Oracle partner.", ["Oracle Partner"], CriterionOutcome.MET),
    ],
)
def test_certification_matching(clause, held, expected):
    fact = eligibility_fact("certification", clause)
    outcome = qualify(make_tender(eligibility=[fact]), make_profile(certifications=held, capabilities=[]), NOW)
    assert outcome.checks[0].outcome is expected


def test_msme_turnover_relaxation_turns_a_fail_into_a_review():
    relaxation = eligibility_fact(
        "msme_startup", "Turnover criteria are relaxed for Micro and Small Enterprises.",
        {"msme_clause_kind": "turnover_relaxation"}, i=9,
    )
    low = [TurnoverYear(fy, 2 * CR) for fy in ("2024-25", "2023-24", "2022-23")]
    tender = make_tender(eligibility=[TURNOVER, relaxation])

    registered = qualify(tender, make_profile(turnover_by_year=low, msme_registered=True), NOW)
    assert registered.checks[0].outcome is CriterionOutcome.UNKNOWN
    assert "relaxes" in registered.checks[0].text
    assert registered.checks[0].profile_evidence["relaxed_by"] == ["fact-9"]

    not_registered = qualify(tender, make_profile(turnover_by_year=low, msme_registered=False), NOW)
    assert not_registered.checks[0].outcome is CriterionOutcome.NOT_MET


def test_emd_exemption_is_noted_for_a_registered_mse():
    outcome = qualify(make_tender(), make_profile(msme_registered=True), NOW)
    emd = reason_for(outcome, "emd")
    assert emd.profile_evidence["exempt"] is True
    assert not any(r.risk == "EMD to be deposited" for r in outcome.risks)

    outcome = qualify(make_tender(), make_profile(msme_registered=False), NOW)
    assert any(r.risk == "EMD to be deposited" for r in outcome.risks)


# --------------------------------------------------------------- relevance


def test_relevance_score_is_reconstructable_from_stored_factors():
    for profile in (make_profile(), make_profile(experience=[], employee_count=None, locations=[])):
        outcome = qualify(make_tender(), profile, NOW)
        stored = {name: f.as_dict() for name, f in outcome.factors.items()}

        assert set(stored) == set(WEIGHTS)
        assert relevance_score(stored) == outcome.relevance_score
        total = sum(f["weight"] for f in stored.values())
        assert outcome.relevance_score == round(sum(f["score"] * f["weight"] for f in stored.values()) / total)


def test_unknown_factors_are_neutral_and_flagged():
    outcome = qualify(make_tender(), make_profile(experience=[], employee_count=None, locations=[]), NOW)
    for name in ("experience", "manpower", "location"):
        assert outcome.factors[name].known is False
        assert outcome.factors[name].score == 50


def test_strong_match_outscores_weak_match():
    strong = qualify(make_tender(), make_profile(), NOW)
    weak = qualify(
        make_tender(),
        make_profile(
            capabilities=[Capability(TenderCategory.NETWORKING_INFRASTRUCTURE, ["Cisco"], [])],
            experience=[govt_project(1, value=20 * 100_000, capability=TenderCategory.NETWORKING_INFRASTRUCTURE)],
            turnover_by_year=[TurnoverYear(fy, 2 * CR) for fy in ("2024-25", "2023-24", "2022-23")],
            msme_registered=False,
        ),
        NOW,
    )
    assert strong.relevance_score > 80
    assert weak.relevance_score < 40


def test_technology_matching_uses_whole_words():
    tender = make_tender(
        requirements=[
            RequirementFact(RequirementCategory.TECHNOLOGY, "stack", {"technologies": ["JavaScript", "REST API"]},
                            _citation(1, "q", 1))
        ]
    )
    profile = make_profile(capabilities=[Capability(TenderCategory.SOFTWARE_DEVELOPMENT, ["Java", "REST"], [])],
                           experience=[])
    evidence = qualify(tender, profile, NOW).factors["technical"].evidence[1]
    assert evidence == {"technologies_covered": ["REST API"], "technologies_missing": ["JavaScript"]}


def test_low_confidence_ai_categories_are_ignored():
    tender = make_tender(categories=[TenderCategoryTag(TenderCategory.SOFTWARE_DEVELOPMENT, 0.3)])
    outcome = qualify(tender, make_profile(), NOW)
    assert reason_for(outcome, "similar_projects").outcome is CriterionOutcome.UNKNOWN


# ------------------------------------------------------------------- risks


def test_closed_tender_scores_zero_on_deadline_and_is_a_high_risk():
    outcome = qualify(make_tender(closing_date=NOW - timedelta(days=1)), make_profile(), NOW)
    assert outcome.factors["deadline"].score == 0
    assert outcome.risks[0].severity is RiskSeverity.HIGH
    assert any(r.risk == "Bid submission has closed" for r in outcome.risks)


def test_clause_risks_carry_their_evidence_and_are_sorted_by_severity():
    penalty = RequirementFact(
        RequirementCategory.SLA, "SLA penalty",
        {}, _citation(50, "A penalty of 1% per day of delay shall be levied as liquidated damages.", 4),
    )
    outcome = qualify(
        make_tender(requirements=RFP_REQUIREMENTS + [penalty], closing_date=NOW + timedelta(days=10)),
        make_profile(employee_count=4),
        NOW,
    )
    by_name = {r.risk: r for r in outcome.risks}
    assert by_name["Penalty or liquidated-damages clause"].citation.page_number == 4
    assert by_name["Manpower exceeds company size"].severity is RiskSeverity.HIGH
    assert by_name["Short preparation time"].severity is RiskSeverity.MEDIUM
    assert by_name["Senior resource required"].citation.quote.startswith("Project Manager")
    assert by_name["Long contract commitment"].severity is RiskSeverity.LOW
    order = [r.severity for r in outcome.risks]
    assert order == sorted(order, key=[RiskSeverity.HIGH, RiskSeverity.MEDIUM, RiskSeverity.LOW].index)


def test_engine_is_deterministic():
    first = qualify(make_tender(), make_profile(), NOW)
    second = qualify(make_tender(), make_profile(), NOW)
    assert [c.as_dict() for c in first.checks] == [c.as_dict() for c in second.checks]
    assert {k: f.as_dict() for k, f in first.factors.items()} == {k: f.as_dict() for k, f in second.factors.items()}
    assert [r.as_dict() for r in first.risks] == [r.as_dict() for r in second.risks]
