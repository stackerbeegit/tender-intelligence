import type { TenderCategoryValue } from "./tender";

export type CustomerType = "government" | "psu" | "private";

export const CUSTOMER_TYPE_LABELS: Record<CustomerType, string> = {
  government: "Government",
  psu: "PSU",
  private: "Private",
};

export interface TurnoverYear {
  financial_year: string;
  amount_inr: number;
}

/** null on a field means "not recorded" — matching reports UNKNOWN rather than guessing. */
export interface CompanyProfile {
  id: string;
  company_name: string;
  msme_registered: boolean | null;
  msme_certificate_ref: string | null;
  startup_registered: boolean | null;
  startup_certificate_ref: string | null;
  turnover_by_year: TurnoverYear[];
  net_worth_inr: string | null;
  years_in_business: number | null;
  employee_count: number | null;
  locations: string[];
  certifications: string[];
  updated_at: string;
}

export type ProfileUpsert = Omit<CompanyProfile, "id" | "updated_at">;

export interface Capability {
  id: string;
  capability: TenderCategoryValue;
  technologies: string[];
  certifications: string[];
  description: string | null;
}

export type CapabilityPayload = Omit<Capability, "id">;

export interface ExperienceRecord {
  id: string;
  project_name: string;
  client_name: string | null;
  customer_type: CustomerType;
  capability: TenderCategoryValue | null;
  industry: string | null;
  technologies: string[];
  project_value_inr: string | null;
  year: number | null;
  description: string | null;
}

export type ExperiencePayload = Omit<ExperienceRecord, "id">;

export interface CompanyProfileResponse {
  profile: CompanyProfile | null;
  capabilities: Capability[];
  experience: ExperienceRecord[];
}
