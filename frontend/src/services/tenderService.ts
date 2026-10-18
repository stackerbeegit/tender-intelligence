import { api } from "./api";
import type { ManualTenderCreate, TenderDetail, TenderFilters, TenderListResponse } from "@/types/tender";

export const tenderService = {
  async list(filters: TenderFilters): Promise<TenderListResponse> {
    const { data } = await api.get<TenderListResponse>("/tenders", { params: filters });
    return data;
  },

  async states(): Promise<string[]> {
    const { data } = await api.get<string[]>("/tenders/states");
    return data;
  },

  async get(id: string): Promise<TenderDetail> {
    const { data } = await api.get<TenderDetail>(`/tenders/${id}`);
    return data;
  },

  async createManual(payload: ManualTenderCreate): Promise<TenderDetail> {
    const { data } = await api.post<TenderDetail>("/tenders/manual", payload);
    return data;
  },
};
