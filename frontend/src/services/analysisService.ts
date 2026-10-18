import { api } from "./api";
import type { TenderAnalysisResponse } from "@/types/analysis";

export const analysisService = {
  async get(tenderId: string): Promise<TenderAnalysisResponse> {
    const { data } = await api.get<TenderAnalysisResponse>(`/tenders/${tenderId}/analysis`);
    return data;
  },

  /** Runs synchronously on the server — reads every document, so this can take minutes. */
  async run(tenderId: string): Promise<TenderAnalysisResponse> {
    const { data } = await api.post<TenderAnalysisResponse>(`/tenders/${tenderId}/analysis`);
    return data;
  },
};
