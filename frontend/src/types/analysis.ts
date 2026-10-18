import type { TenderCategoryValue } from "./tender";

export type AnalysisStatus = "running" | "done" | "failed";

export type RequirementCategory =
  | "technology"
  | "infrastructure"
  | "integration"
  | "support"
  | "sla"
  | "security"
  | "certification"
  | "manpower"
  | "contract"
  | "other";

export type EligibilityCriterionType =
  | "turnover"
  | "net_worth"
  | "emd"
  | "tender_fee"
  | "performance_security"
  | "similar_projects"
  | "years_of_experience"
  | "government_experience"
  | "certification"
  | "msme_startup"
  | "other";

export const REQUIREMENT_CATEGORY_LABELS: Record<RequirementCategory, string> = {
  technology: "Technology",
  infrastructure: "Infrastructure",
  integration: "Integration",
  support: "Support",
  sla: "SLA",
  security: "Security",
  certification: "Certification",
  manpower: "Manpower",
  contract: "Contract",
  other: "Other",
};

export const ELIGIBILITY_TYPE_LABELS: Record<EligibilityCriterionType, string> = {
  turnover: "Turnover",
  net_worth: "Net worth",
  emd: "EMD",
  tender_fee: "Tender fee",
  performance_security: "Performance security",
  similar_projects: "Similar projects",
  years_of_experience: "Years of experience",
  government_experience: "Govt / PSU experience",
  certification: "Certification",
  msme_startup: "MSME / Startup",
  other: "Other",
};

export interface Citation {
  document_id: string;
  file_name: string;
  page_number: number;
}

export interface Requirement {
  id: string;
  category: RequirementCategory;
  summary: string;
  requirement_text: string;
  details: Record<string, unknown>;
  citation: Citation;
  generated_by_model: string;
}

export interface EligibilityCriterion {
  id: string;
  criterion_type: EligibilityCriterionType;
  summary: string;
  criterion_text: string;
  extracted_value: Record<string, unknown>;
  citation: Citation;
  generated_by_model: string;
}

export interface TenderSummary {
  project: string;
  overview: string;
  contract_duration: string | null;
  core_requirements: string[];
  manpower: string[];
  eligibility_highlights: string[];
  msme_provisions: string[];
  points_to_review: string[];
  categories: { category: TenderCategoryValue; confidence: number }[];
  fact_refs: Record<string, string>;
}

export interface AnalysisRun {
  status: AnalysisStatus;
  summary: TenderSummary | null;
  run_stats: {
    llm_calls?: number;
    dropped_unverified?: number;
    skipped_documents?: string[];
  };
  documents_analysed: number;
  generated_by_model: string | null;
  started_at: string;
  finished_at: string | null;
  error: string | null;
}

export interface TenderAnalysisResponse {
  tender_id: string;
  analysis: AnalysisRun | null;
  requirements: Requirement[];
  eligibility: EligibilityCriterion[];
}
