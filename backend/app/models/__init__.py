"""
Import every model module here so `Base.metadata` is fully populated for
Alembic autogenerate and for `Base.metadata.create_all()` in tests. As new
sprints add tables (tenders, sources, opportunities, ...), import them here
too.
"""
from app.models.base import Base  # noqa: F401
from app.models.role import Role  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.source import Source  # noqa: F401
from app.models.crawler_run import CrawlerRun  # noqa: F401
from app.models.tender_organisation import TenderOrganisation  # noqa: F401
from app.models.tender import Tender  # noqa: F401
from app.models.tender_document import TenderDocument  # noqa: F401
from app.models.tender_deadline import TenderDeadline  # noqa: F401
from app.models.tender_location import TenderLocation  # noqa: F401
from app.models.tender_category import TenderCategory  # noqa: F401
from app.models.tender_requirement import TenderRequirement  # noqa: F401
from app.models.tender_eligibility import TenderEligibility  # noqa: F401
from app.models.tender_analysis import TenderAnalysis  # noqa: F401
from app.models.tender_submission_document import TenderSubmissionDocument  # noqa: F401
from app.models.stackerbee_profile import StackerbeeProfile  # noqa: F401
from app.models.stackerbee_capability import StackerbeeCapability  # noqa: F401
from app.models.stackerbee_experience import StackerbeeExperience  # noqa: F401
from app.models.qualification_result import QualificationResult  # noqa: F401
from app.models.opportunity import Opportunity  # noqa: F401
from app.models.opportunity_assignment import OpportunityAssignment  # noqa: F401
from app.models.opportunity_note import OpportunityNote  # noqa: F401
from app.models.opportunity_status_history import OpportunityStatusHistory  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.bid_checklist_item import BidChecklistItem  # noqa: F401
from app.models.bid_draft import BidDraft  # noqa: F401

__all__ = [
    "Base",
    "Role",
    "User",
    "AuditLog",
    "Source",
    "CrawlerRun",
    "TenderOrganisation",
    "Tender",
    "TenderDocument",
    "TenderDeadline",
    "TenderLocation",
    "TenderCategory",
    "TenderRequirement",
    "TenderEligibility",
    "TenderAnalysis",
    "TenderSubmissionDocument",
    "StackerbeeProfile",
    "StackerbeeCapability",
    "StackerbeeExperience",
    "QualificationResult",
    "Opportunity",
    "OpportunityAssignment",
    "OpportunityNote",
    "OpportunityStatusHistory",
    "Notification",
    "BidChecklistItem",
    "BidDraft",
]
