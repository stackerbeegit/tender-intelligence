export interface DashboardSummary {
  new_tenders: number;
  relevant_tenders: number;
  highly_relevant: number;
  expiring_soon: number;
  under_review: number;
  bidding: number;
  submitted: number;
  won: number;
  lost: number;
  note: string;
}
