import type { EligibilityStatus } from "./qualification";

export type OpportunityStatus =
  | "new"
  | "screening"
  | "qualified"
  | "management_review"
  | "bid_no_bid"
  | "proposal_in_progress"
  | "submitted"
  | "technical_evaluation"
  | "commercial_evaluation"
  | "won"
  | "lost"
  | "no_bid";

export const OPPORTUNITY_STATUS_LABELS: Record<OpportunityStatus, string> = {
  new: "New",
  screening: "Screening",
  qualified: "Qualified",
  management_review: "Management review",
  bid_no_bid: "Bid / no-bid decision",
  proposal_in_progress: "Proposal in progress",
  submitted: "Submitted",
  technical_evaluation: "Technical evaluation",
  commercial_evaluation: "Commercial evaluation",
  won: "Won",
  lost: "Lost",
  no_bid: "No bid",
};

/** Workflow order, for the stepper. won / lost / no_bid are outcomes. */
export const OPPORTUNITY_PIPELINE: OpportunityStatus[] = [
  "new",
  "screening",
  "qualified",
  "management_review",
  "bid_no_bid",
  "proposal_in_progress",
  "submitted",
  "technical_evaluation",
  "commercial_evaluation",
];

export const STATUS_CHIP_COLOR: Record<OpportunityStatus, "default" | "primary" | "success" | "error" | "warning" | "info"> = {
  new: "info",
  screening: "info",
  qualified: "primary",
  management_review: "primary",
  bid_no_bid: "warning",
  proposal_in_progress: "primary",
  submitted: "primary",
  technical_evaluation: "primary",
  commercial_evaluation: "primary",
  won: "success",
  lost: "error",
  no_bid: "default",
};

export const FINAL_STATUSES: OpportunityStatus[] = ["won", "lost", "no_bid"];
/** Statuses the API refuses without a comment. */
export const REASON_REQUIRED: OpportunityStatus[] = ["no_bid", "lost"];

export type OpportunityTeam = "sales" | "bd" | "technical" | "cybersecurity" | "management" | "proposal";
export const TEAM_LABELS: Record<OpportunityTeam, string> = {
  sales: "Sales",
  bd: "BD",
  technical: "Technical",
  cybersecurity: "Cybersecurity",
  management: "Management",
  proposal: "Proposal",
};

export interface UserBrief {
  id: string;
  full_name: string;
  email: string;
}

export interface DirectoryUser extends UserBrief {
  role: string;
}

export interface OpportunityListItem {
  id: string;
  status: OpportunityStatus;
  created_from: "auto_relevance" | "manual";
  tender: { id: string; title: string; tender_number: string | null; organisation: string | null; closing_date: string | null };
  owner: UserBrief | null;
  assignees: UserBrief[];
  relevance_score: number | null;
  eligibility_status: EligibilityStatus | null;
  created_at: string;
  updated_at: string;
}

export interface OpportunityListResponse {
  items: OpportunityListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface OpportunityDetail extends OpportunityListItem {
  assignments: { id: string; user: UserBrief; team: OpportunityTeam; assigned_at: string }[];
  notes: { id: string; author: UserBrief; note_text: string; created_at: string }[];
  history: {
    id: string;
    from_status: OpportunityStatus | null;
    to_status: OpportunityStatus;
    changed_by: UserBrief | null;
    changed_at: string;
    comment: string | null;
  }[];
  allowed_transitions: OpportunityStatus[];
  can_edit: boolean;
  can_decide: boolean;
}

// ---------------------------------------------------------- bid preparation

export type ChecklistStatus = "available" | "to_prepare" | "missing" | "not_applicable";
export const CHECKLIST_STATUS_LABELS: Record<ChecklistStatus, string> = {
  available: "Available",
  to_prepare: "To prepare",
  missing: "Missing",
  not_applicable: "Not applicable",
};

export interface ChecklistItem {
  id: string;
  position: number;
  title: string;
  kind: string;
  mandatory: boolean | null;
  format_instructions: string | null;
  form_reference: string | null;
  source_clause: string | null;
  source_document_id: string | null;
  source_file_name: string | null;
  source_page: number | null;
  is_manual: boolean;
  status: ChecklistStatus;
  status_set_by_user: boolean;
  prefill_reason: string | null;
  owner: UserBrief | null;
  note: string | null;
}

interface Citation {
  document_id: string;
  file_name: string;
  page_number: number;
}

export interface DraftContent {
  disclaimer: string;
  generated_at: string;
  generated_by_model: string;
  covering_letter: string;
  company_overview: string;
  eligibility_compliance: { ref: string; criterion: string; assessment: string | null; statement: string; citation: Citation }[];
  technical_compliance: { ref: string; requirement: string; response: string; citation: Citation }[];
  manpower_plan: {
    ref: string;
    role: string;
    count: number | null;
    min_experience_years: number | null;
    proposed_resource: string;
    citation: Citation;
  }[];
  relevant_projects: { project_name: string; client_name: string | null; customer_type: string; value_inr: number | null; year: number | null }[];
  assumptions: string[];
}

export interface BidDraft {
  id: string;
  version: number;
  content: DraftContent;
  placeholders: { section: string; text: string }[];
  generated_by_model: string;
  created_by: UserBrief | null;
  created_at: string;
}

export interface BidPreparation {
  opportunity_id: string;
  tender_id: string;
  tender_analysed: boolean;
  profile_configured: boolean;
  checklist: ChecklistItem[];
  latest_draft: BidDraft | null;
  draft_versions: { id: string; version: number; created_at: string; created_by: UserBrief | null; placeholder_count: number }[];
  can_prepare: boolean;
  can_edit_checklist: boolean;
}

export interface BidPreparationStart extends BidPreparation {
  opportunity_created: boolean;
  draft_error: string | null;
  draft_problems: string[];
}
