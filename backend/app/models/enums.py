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
