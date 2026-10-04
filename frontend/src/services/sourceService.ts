import { api } from "./api";
import type { Source, SourceType } from "@/types/tender";

export interface SourceCreatePayload {
  name: string;
  source_type: SourceType;
  url?: string;
  organisation?: string;
  terms_access_notes?: string;
}

export const sourceService = {
  async list(): Promise<Source[]> {
    const { data } = await api.get<Source[]>("/sources");
    return data;
  },

  async create(payload: SourceCreatePayload): Promise<Source> {
    const { data } = await api.post<Source>("/sources", payload);
    return data;
  },

  async update(id: string, payload: Partial<Pick<Source, "crawler_enabled" | "terms_access_notes">>): Promise<Source> {
    const { data } = await api.patch<Source>(`/sources/${id}`, payload);
    return data;
  },
};
