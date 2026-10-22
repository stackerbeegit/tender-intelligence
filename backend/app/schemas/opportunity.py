import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ChecklistItemStatus,
    EligibilityStatus,
    NotificationStatus,
    OpportunityOrigin,
    OpportunityStatus,
    OpportunityTeam,
    SubmissionDocumentKind,
)


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str


class DirectoryUser(UserBrief):
    role: str


class TenderBrief(BaseModel):
    id: uuid.UUID
    title: str
    tender_number: str | None
    organisation: str | None
    closing_date: datetime | None


class OpportunityCreate(BaseModel):
    tender_id: uuid.UUID
    comment: str | None = Field(default=None, max_length=2000)


class OpportunityListItem(BaseModel):
    id: uuid.UUID
    status: OpportunityStatus
    created_from: OpportunityOrigin
    tender: TenderBrief
    owner: UserBrief | None
    assignees: list[UserBrief]
    relevance_score: int | None
    eligibility_status: EligibilityStatus | None
    created_at: datetime
    updated_at: datetime


class OpportunityListResponse(BaseModel):
    items: list[OpportunityListItem]
    total: int
    page: int
    page_size: int


class AssignmentRead(BaseModel):
    id: uuid.UUID
    user: UserBrief
    team: OpportunityTeam
    assigned_at: datetime


class NoteRead(BaseModel):
    id: uuid.UUID
    author: UserBrief
    note_text: str
    created_at: datetime


class StatusHistoryRead(BaseModel):
    id: uuid.UUID
    from_status: OpportunityStatus | None
    to_status: OpportunityStatus
    changed_by: UserBrief | None
    changed_at: datetime
    comment: str | None


class OpportunityDetail(OpportunityListItem):
    assignments: list[AssignmentRead]
    notes: list[NoteRead]
    history: list[StatusHistoryRead]
    allowed_transitions: list[OpportunityStatus]
    can_edit: bool
    can_decide: bool


class TransitionRequest(BaseModel):
    to_status: OpportunityStatus
    comment: str | None = Field(default=None, max_length=2000)
    override: bool = False


class AssignmentCreate(BaseModel):
    user_id: uuid.UUID
    team: OpportunityTeam


class OwnerUpdate(BaseModel):
    owner_id: uuid.UUID | None


class NoteCreate(BaseModel):
    note_text: str = Field(min_length=1, max_length=5000)


class TenderOpportunityRef(BaseModel):
    opportunity: OpportunityListItem | None


# ----------------------------------------------------------- bid prep


class ChecklistItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    title: str
    kind: SubmissionDocumentKind
    mandatory: bool | None
    format_instructions: str | None
    form_reference: str | None
    source_clause: str | None
    source_document_id: uuid.UUID | None
    source_file_name: str | None
    source_page: int | None
    is_manual: bool
    status: ChecklistItemStatus
    status_set_by_user: bool
    prefill_reason: str | None
    owner: UserBrief | None
    note: str | None


class ChecklistItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)


class ChecklistItemUpdate(BaseModel):
    status: ChecklistItemStatus | None = None
    owner_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=5000)


class BidDraftRead(BaseModel):
    """AI DRAFT — `content` was checked to contain no amount, certification
    or project absent from its inputs; `placeholders` must be completed."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    content: dict[str, Any]
    placeholders: list[dict[str, Any]]
    generated_by_model: str
    created_by: UserBrief | None
    created_at: datetime


class BidDraftVersion(BaseModel):
    id: uuid.UUID
    version: int
    created_at: datetime
    created_by: UserBrief | None
    placeholder_count: int


class BidPreparationRead(BaseModel):
    opportunity_id: uuid.UUID
    tender_id: uuid.UUID
    tender_analysed: bool
    profile_configured: bool
    checklist: list[ChecklistItemRead]
    latest_draft: BidDraftRead | None
    draft_versions: list[BidDraftVersion]
    can_prepare: bool
    can_edit_checklist: bool


class BidPreparationStartResponse(BidPreparationRead):
    opportunity_created: bool
    draft_error: str | None
    draft_problems: list[str]


# ------------------------------------------------------- notifications


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    subject: str
    body_text: str
    status: NotificationStatus
    error: str | None
    created_at: datetime
    entity_type: str | None
    entity_id: str | None


class DigestPreview(BaseModel):
    subject: str
    text: str
    html: str
    is_empty: bool
