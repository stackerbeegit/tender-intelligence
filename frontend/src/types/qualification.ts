import type { EligibilityCriterionType } from "./analysis";

export type EligibilityStatus = "ELIGIBLE" | "NOT_ELIGIBLE" | "UNCERTAIN";
export type CriterionOutcome = "MET" | "NOT_MET" | "UNKNOWN" | "INFO";
export type RiskSeverity = "high" | "medium" | "low";

export type FactorName =
  | "technical"
  | "eligibility"
  | "experience"
  | "manpower"
  | "commercial"
  | "location"
  | "msme"
  | "deadline";

export const FACTOR_LABELS: Record<FactorName, string> = {
  technical: "Technical fit",
  eligibility: "Eligibility confidence",
  experience: "Experience fit",
  manpower: "Manpower fit",
  commercial: "Commercial fit",
  location: "Location fit",
  msme: "MSME relevance",
  deadline: "Time to deadline",
};

export interface FactEvidence {
  fact_id: string;
  document_id: string;
  file_name: string;
  page_number: number;
  quote: string;
}

export interface QualificationReason {
  criterion_type: EligibilityCriterionType | null;
  outcome: CriterionOutcome;
  polarity: "support" | "concern" | "neutral";
  text: string;
  evidence: FactEvidence | null;
  profile_evidence: Record<string, unknown>;
}

export interface RelevanceFactor {
  score: number;
  weight: number;
  known: boolean;
  explanation: string;
  evidence: Record<string, unknown>[];
}

export interface QualificationRisk {
  risk: string;
  severity: RiskSeverity;
  explanation: string;
  evidence: string | null;
  fact_id: string | null;
  document_id: string | null;
  file_name: string | null;
  page: number | null;
}

export interface Qualification {
  eligibility_status: EligibilityStatus;
  reasons: QualificationReason[];
  relevance_score: number;
  relevance_factors: Record<FactorName, RelevanceFactor>;
  risks: QualificationRisk[];
  engine_version: string;
  computed_at: string;
}

export interface QualificationResponse {
  tender_id: string;
  profile_configured: boolean;
  is_stale: boolean;
  qualification: Qualification | null;
}
