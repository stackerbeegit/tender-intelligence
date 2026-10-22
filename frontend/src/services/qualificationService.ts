import { api } from "./api";
import type { QualificationResponse } from "@/types/qualification";

export const qualificationService = {
  async get(tenderId: string): Promise<QualificationResponse> {
    const { data } = await api.get<QualificationResponse>(`/tenders/${tenderId}/qualification`);
    return data;
  },

  /** Deterministic rules, no model call — returns in well under a second. */
  async compute(tenderId: string): Promise<QualificationResponse> {
    const { data } = await api.post<QualificationResponse>(`/tenders/${tenderId}/qualification`);
    return data;
  },
};
