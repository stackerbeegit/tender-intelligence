"""
Shared enums used by both ORM models (as sa.Enum columns, stored as their
string .value — portable across Postgres/SQLite) and Pydantic schemas. One
definition, two consumers, so API payloads and DB rows can never disagree
on allowed values.
"""
from enum import Enum


class SourceType(str, Enum):
    GEM = "gem"
    CPPP = "cppp"
    STATE = "state"
    PSU = "psu"
    DEPARTMENT = "department"
    MANUAL = "manual"  # no automated connector — staff-entered, per Rule 12
    OTHER = "other"


class SourceStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    DISABLED = "disabled"


class CrawlerRunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class OrganisationType(str, Enum):
    CENTRAL_GOVT = "central_govt"
    STATE_GOVT = "state_govt"
    PSU = "psu"
    PRIVATE = "private"
    OTHER = "other"


class TenderStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    CORRIGENDUM = "corrigendum"


class TenderCategory(str, Enum):
    SOFTWARE_DEVELOPMENT = "software_development"
    IT_MANPOWER = "it_manpower"
    CYBERSECURITY = "cybersecurity"
    NETWORKING_INFRASTRUCTURE = "networking_infrastructure"
    ERP_FRAPPE = "erp_frappe"
    CLOUD_DEVOPS = "cloud_devops"
    IOT_SMART_CITY = "iot_smart_city"
    DATA_AI_ML = "data_ai_ml"
    WEB_MOBILE_DEVELOPMENT = "web_mobile_development"
    OTHER = "other"


class DeadlineType(str, Enum):
    BID_SUBMISSION = "bid_submission"
    PRE_BID_MEETING = "pre_bid_meeting"
    CLARIFICATION = "clarification"
    EXTENDED = "extended"


class DocumentType(str, Enum):
    NIT = "nit"
    RFP = "rfp"
    BOQ = "boq"
    ANNEXURE = "annexure"
    CORRIGENDUM = "corrigendum"
    OTHER = "other"


class OcrStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class RequirementCategory(str, Enum):
    """Brief §8 'Technical' and 'Manpower' groups."""

    TECHNOLOGY = "technology"  # required technologies / software / platforms
    INFRASTRUCTURE = "infrastructure"
    INTEGRATION = "integration"
    SUPPORT = "support"
    SLA = "sla"
    SECURITY = "security"
    CERTIFICATION = "certification"
    MANPOWER = "manpower"
    CONTRACT = "contract"  # contract duration, delivery timelines
    OTHER = "other"


class EligibilityCriterionType(str, Enum):
    """Brief §8 'Financial', 'Experience' and 'MSME / Startup' groups."""

    TURNOVER = "turnover"
    NET_WORTH = "net_worth"
    EMD = "emd"
    TENDER_FEE = "tender_fee"
    PERFORMANCE_SECURITY = "performance_security"
    SIMILAR_PROJECTS = "similar_projects"
    YEARS_OF_EXPERIENCE = "years_of_experience"
    GOVERNMENT_EXPERIENCE = "government_experience"
    CERTIFICATION = "certification"
    MSME_STARTUP = "msme_startup"
    OTHER = "other"


class AnalysisStatus(str, Enum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class CustomerType(str, Enum):
    GOVERNMENT = "government"
    PSU = "psu"
    PRIVATE = "private"


class EligibilityStatus(str, Enum):
    """Overall verdict on `qualification_results` (docs/architecture.md §7).
    Upper-case values, as the architecture doc and UI spell them."""

    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    UNCERTAIN = "UNCERTAIN"


class CriterionOutcome(str, Enum):
    """Result of checking one eligibility fact against the company profile.
    UNKNOWN means the data needed to decide is missing or ambiguous — it is
    never treated as a pass. INFO marks clauses that are not pass/fail gates
    (EMD, tender fee, MSME benefits)."""

    MET = "MET"
    NOT_MET = "NOT_MET"
    UNKNOWN = "UNKNOWN"
    INFO = "INFO"


class RiskSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
