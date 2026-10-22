"""
Entry point of the matching engine: verified tender facts + company
profile -> eligibility verdict, evidence-linked reasons, relevance factors
and risks. Pure and deterministic — no database, no model call, and `now`
is passed in — so a result can always be re-derived from its inputs.
"""
from datetime import datetime

from app.matching.eligibility import check_criteria, overall_status
from app.matching.relevance import compute_factors, relevance_score
from app.matching.risk import assess_risks
from app.matching.types import CompanyProfile, QualificationOutcome, TenderFacts

# Bump when a rule changes, so stored results show which rules produced them.
ENGINE_VERSION = "1.0"


def qualify(tender: TenderFacts, profile: CompanyProfile, now: datetime) -> QualificationOutcome:
    checks = check_criteria(tender, profile)
    status, extra_reasons = overall_status(tender, checks)
    factors = compute_factors(tender, profile, status, checks, now)
    return QualificationOutcome(
        eligibility_status=status,
        checks=checks + extra_reasons,
        factors=factors,
        relevance_score=relevance_score(factors),
        risks=assess_risks(tender, profile, checks, now),
    )
