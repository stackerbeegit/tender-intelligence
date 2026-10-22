"""
Pre-filling a bid checklist item's status from the company profile. Only
what the profile can actually confirm becomes AVAILABLE; everything else
starts as TO_PREPARE, so the checklist never claims a document exists
because a rule guessed it does.
"""
import re

from app.bidding import grounding
from app.matching.text import normalise
from app.matching.types import CompanyProfile
from app.models.enums import ChecklistItemStatus, SubmissionDocumentKind

_MSE = re.compile(r"\b(udyam|nsic|msme|mse)\b", re.IGNORECASE)
_STARTUP = re.compile(r"\b(dpiit|start[\s-]?up)\b", re.IGNORECASE)


def match_key(clause: str | None) -> str:
    """How a checklist item is matched to a submission-document fact after
    a re-analysis replaced the fact rows."""
    return normalise(clause or "")


def prefill(
    kind: SubmissionDocumentKind, clause: str, profile: CompanyProfile | None, msme_ref: str | None, startup_ref: str | None
) -> tuple[ChecklistItemStatus, str | None]:
    if profile is None:
        return ChecklistItemStatus.TO_PREPARE, None

    if kind in (SubmissionDocumentKind.CERTIFICATE, SubmissionDocumentKind.EMD):
        named = grounding.certifications(clause)
        held = grounding.certifications(" ".join(profile.all_certifications))
        if named and named <= held:
            names = ", ".join(sorted(n.replace("iso:", "ISO ").replace("cmmi:", "CMMI Level ") for n in named))
            return ChecklistItemStatus.AVAILABLE, f"{names} recorded in the company profile"
        if _MSE.search(clause) and profile.msme_registered and msme_ref:
            return ChecklistItemStatus.AVAILABLE, f"MSME/Udyam registration recorded in the profile ({msme_ref})"
        if _STARTUP.search(clause) and profile.startup_registered and startup_ref:
            return ChecklistItemStatus.AVAILABLE, f"DPIIT startup recognition recorded in the profile ({startup_ref})"
    return ChecklistItemStatus.TO_PREPARE, None
