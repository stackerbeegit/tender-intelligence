"""
Risk analysis (docs/architecture.md §7): a list of named risks with a
severity, an explanation and — where a clause raised it — the verbatim
evidence and its document/page. Computed independently of the verdict,
so an ELIGIBLE tender can still carry high risks.
"""
import re
from datetime import datetime

from app.matching.text import format_inr, number
from app.matching.types import CompanyProfile, CriterionCheck, Risk, TenderFacts
from app.models.enums import (
    CriterionOutcome,
    EligibilityCriterionType,
    RequirementCategory,
    RiskSeverity,
    TenderStatus,
)

HIGH, MEDIUM, LOW = RiskSeverity.HIGH, RiskSeverity.MEDIUM, RiskSeverity.LOW
_PENALTY_PATTERN = re.compile(r"penalt|liquidated damages|\bLDs?\b|forfeit|blacklist|debar", re.IGNORECASE)
_SEVERITY_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2}
SENIOR_EXPERIENCE_YEARS = 10
LONG_CONTRACT_MONTHS = 36
LARGE_CONTRACT_RATIO = 5


def _eligibility_risks(checks: list[CriterionCheck]) -> list[Risk]:
    risks = []
    for check in checks:
        if check.criterion_type is None or not check.is_gate:
            continue
        if check.outcome is CriterionOutcome.NOT_MET:
            risks.append(Risk("Eligibility criterion not met", HIGH, check.text, check.citation))
        elif check.outcome is CriterionOutcome.UNKNOWN:
            risks.append(Risk("Eligibility criterion unconfirmed", MEDIUM, check.text, check.citation))
    return risks


def _deadline_risks(tender: TenderFacts, now: datetime) -> list[Risk]:
    if tender.closing_date is None:
        return [Risk("No closing date recorded", LOW, "Confirm the bid submission deadline on the portal.")]
    days = (tender.closing_date - now).total_seconds() / 86400
    if days < 0:
        return [Risk("Bid submission has closed", HIGH, "The closing date has passed.")]
    if days < 7:
        return [Risk("Very short preparation time", HIGH, f"Only {days:.0f} day(s) left before bid submission closes.")]
    if days < 14:
        return [Risk("Short preparation time", MEDIUM, f"{days:.0f} days left before bid submission closes.")]
    return []


def _requirement_risks(tender: TenderFacts, profile: CompanyProfile) -> list[Risk]:
    risks = []
    manpower_total = 0
    for req in tender.requirements:
        if _PENALTY_PATTERN.search(req.text):
            risks.append(
                Risk(
                    "Penalty or liquidated-damages clause",
                    MEDIUM,
                    "Non-performance carries a financial or debarment penalty — price it into the bid.",
                    req.citation,
                )
            )
        if req.category is RequirementCategory.MANPOWER:
            manpower_total += int(number(req.details.get("resource_count")) or 1)
            years = number(req.details.get("min_experience_years"))
            if years is not None and years >= SENIOR_EXPERIENCE_YEARS:
                risks.append(
                    Risk(
                        "Senior resource required",
                        LOW,
                        f"{req.details.get('role') or 'A role'} needs {years:g}+ years of experience — "
                        "confirm a named resource is available.",
                        req.citation,
                    )
                )
        if req.category is RequirementCategory.CONTRACT:
            months = number(req.details.get("duration_months"))
            if months is not None and months >= LONG_CONTRACT_MONTHS:
                risks.append(
                    Risk(
                        "Long contract commitment",
                        LOW,
                        f"The contract runs {months:g} months; team and pricing must hold for that long.",
                        req.citation,
                    )
                )

    if manpower_total and profile.employee_count:
        share = manpower_total / profile.employee_count
        if share > 1:
            risks.append(
                Risk(
                    "Manpower exceeds company size",
                    HIGH,
                    f"{manpower_total} resources required against {profile.employee_count} employees — "
                    "hiring or subcontracting would be needed.",
                )
            )
        elif share > 0.5:
            risks.append(
                Risk(
                    "Large share of workforce required",
                    MEDIUM,
                    f"{manpower_total} resources is {share:.0%} of the company's {profile.employee_count} employees.",
                )
            )
    return risks


def _financial_risks(tender: TenderFacts, profile: CompanyProfile, checks: list[CriterionCheck]) -> list[Risk]:
    risks = []
    for check in checks:
        if check.criterion_type is EligibilityCriterionType.PERFORMANCE_SECURITY:
            risks.append(
                Risk(
                    "Performance security required",
                    LOW,
                    f"{check.text} Working capital stays blocked for the contract period.",
                    check.citation,
                )
            )
        if check.criterion_type is EligibilityCriterionType.EMD and not check.profile_evidence.get("exempt"):
            risks.append(
                Risk("EMD to be deposited", LOW, f"{check.text} It is blocked until the bid is decided.", check.citation)
            )

    project_values = [e.value_inr for e in profile.experience if e.value_inr]
    if tender.tender_value_inr and project_values and tender.tender_value_inr > LARGE_CONTRACT_RATIO * max(project_values):
        risks.append(
            Risk(
                "Contract far larger than past projects",
                MEDIUM,
                f"Tender value {format_inr(tender.tender_value_inr)} is over {LARGE_CONTRACT_RATIO}× the largest past "
                f"project ({format_inr(max(project_values))}).",
            )
        )
    return risks


def assess_risks(
    tender: TenderFacts, profile: CompanyProfile, checks: list[CriterionCheck], now: datetime
) -> list[Risk]:
    risks: list[Risk] = []
    if not tender.analysed:
        risks.append(
            Risk(
                "Tender documents not analysed",
                HIGH,
                "Eligibility, requirements and clause-level risks are unknown until the documents are analysed.",
            )
        )
    if tender.status is TenderStatus.CORRIGENDUM:
        risks.append(
            Risk("Tender amended by corrigendum", LOW, "Re-check the latest documents; terms may have changed.")
        )
    risks += _eligibility_risks(checks)
    risks += _deadline_risks(tender, now)
    risks += _requirement_risks(tender, profile)
    risks += _financial_risks(tender, profile, checks)
    return sorted(risks, key=lambda r: _SEVERITY_ORDER[r.severity])
