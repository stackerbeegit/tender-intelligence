export type SourceType = "gem" | "cppp" | "state" | "psu" | "department" | "manual" | "other";
export type SourceStatus = "healthy" | "degraded" | "down" | "disabled";

export interface Source {
  id: string;
  name: string;
  organisation: string | null;
  url: string | null;
  source_type: SourceType;
  country: string;
  state: string | null;
  auth_required: boolean;
  api_available: boolean;
  crawler_enabled: boolean;
  frequency: string | null;
  last_successful_crawl_at: string | null;
  last_failure_at: string | null;
  status: SourceStatus;
  terms_access_notes: string | null;
  created_at: string;
}

export type TenderStatus = "open" | "closed" | "cancelled" | "corrigendum";

export type TenderCategoryValue =
  | "software_development"
  | "it_manpower"
  | "cybersecurity"
  | "networking_infrastructure"
  | "erp_frappe"
  | "cloud_devops"
  | "iot_smart_city"
  | "data_ai_ml"
  | "web_mobile_development"
  | "other";

export const TENDER_CATEGORY_LABELS: Record<TenderCategoryValue, string> = {
  software_development: "Software Development",
  it_manpower: "IT Manpower",
  cybersecurity: "Cybersecurity",
  networking_infrastructure: "Networking & Infrastructure",
  erp_frappe: "ERP / Frappe",
  cloud_devops: "Cloud / DevOps",
  iot_smart_city: "IoT / Smart City",
  data_ai_ml: "Data / AI-ML",
  web_mobile_development: "Web / Mobile Development",
  other: "Other",
};

export interface Organisation {
  id: string;
  name: string;
  type: string;
  state: string | null;
  city: string | null;
}

export interface Location {
  id: string;
  state: string | null;
  city: string | null;
  pincode: string | null;
}

export interface Category {
  id: string;
  category: TenderCategoryValue;
  confidence: string | null;
}

export type DeadlineType = "bid_submission" | "pre_bid_meeting" | "clarification" | "extended";

export interface Deadline {
  id: string;
  deadline_type: DeadlineType;
  deadline_at: string;
}

export type OcrStatus = "not_required" | "pending" | "done" | "failed";
export type ExtractionStatus = "pending" | "done" | "failed";

export interface TenderDocument {
  id: string;
  file_name: string;
  document_type: string;
  source_url: string | null;
  storage_path: string | null;
  checksum_sha256: string | null;
  file_size_bytes: number | null;
  page_count: number | null;
  ocr_status: OcrStatus;
  extraction_status: ExtractionStatus;
  extracted_text: string | null;
  last_processing_error: string | null;
}

export interface TenderListItem {
  id: string;
  title: string;
  tender_number: string | null;
  organisation: Organisation | null;
  tender_value: string | null;
  published_date: string | null;
  closing_date: string | null;
  status: TenderStatus;
  source_id: string;
}

export interface TenderDetail extends TenderListItem {
  url: string | null;
  emd_amount: string | null;
  tender_fee: string | null;
  source_tender_id: string | null;
  raw_metadata: Record<string, unknown>;
  locations: Location[];
  categories: Category[];
  deadlines: Deadline[];
  documents: TenderDocument[];
  created_at: string;
  updated_at: string;
}

export interface TenderListResponse {
  items: TenderListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface TenderFilters {
  keyword?: string;
  source_id?: string;
  state?: string;
  city?: string;
  category?: TenderCategoryValue;
  min_value?: string;
  max_value?: string;
  status?: TenderStatus;
  page?: number;
  page_size?: number;
}

export interface ManualTenderCreate {
  title: string;
  tender_number?: string | null;
  organisation_name?: string | null;
  organisation_state?: string | null;
  organisation_city?: string | null;
  url?: string | null;
  published_date?: string | null;
  closing_date?: string | null;
  tender_value?: string | null;
  emd_amount?: string | null;
  tender_fee?: string | null;
  locations: { state?: string; city?: string; pincode?: string }[];
  categories: TenderCategoryValue[];
  documents: { file_name: string; source_url?: string }[];
}
