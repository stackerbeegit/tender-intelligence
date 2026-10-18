import type { TenderCategoryValue } from "./tender";

/** `null` means "not computable yet" (reason in `pending_metrics`), not a real 0. */
export interface DashboardSummary {
  active_tenders: number;
  new_tenders: number;
  relevant_tenders: number;
  expiring_soon: number;
  analysed_tenders: number;
  highly_relevant: number | null;
  under_review: number | null;
  bidding: number | null;
  submitted: number | null;
  won: number | null;
  lost: number | null;
  by_category: { category: TenderCategoryValue; count: number }[];
  by_state: { state: string; count: number }[];
  /** One entry per day (IST) for the next two weeks, zero-filled. */
  closing_timeline: { date: string; count: number }[];
  last_crawl_at: string | null;
  pending_metrics: Record<string, string>;
  new_window_days: number;
  expiring_window_days: number;
}
