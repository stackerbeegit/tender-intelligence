import { api } from "./api";
import type {
  Capability,
  CapabilityPayload,
  CompanyProfile,
  CompanyProfileResponse,
  ExperiencePayload,
  ExperienceRecord,
  ProfileUpsert,
} from "@/types/profile";

export const profileService = {
  async get(): Promise<CompanyProfileResponse> {
    const { data } = await api.get<CompanyProfileResponse>("/profile");
    return data;
  },

  async save(payload: ProfileUpsert): Promise<CompanyProfile> {
    const { data } = await api.put<CompanyProfile>("/profile", payload);
    return data;
  },

  async addCapability(payload: CapabilityPayload): Promise<Capability> {
    const { data } = await api.post<Capability>("/profile/capabilities", payload);
    return data;
  },

  async updateCapability(id: string, payload: Partial<CapabilityPayload>): Promise<Capability> {
    const { data } = await api.patch<Capability>(`/profile/capabilities/${id}`, payload);
    return data;
  },

  async deleteCapability(id: string): Promise<void> {
    await api.delete(`/profile/capabilities/${id}`);
  },

  async addExperience(payload: ExperiencePayload): Promise<ExperienceRecord> {
    const { data } = await api.post<ExperienceRecord>("/profile/experience", payload);
    return data;
  },

  async updateExperience(id: string, payload: Partial<ExperiencePayload>): Promise<ExperienceRecord> {
    const { data } = await api.patch<ExperienceRecord>(`/profile/experience/${id}`, payload);
    return data;
  },

  async deleteExperience(id: string): Promise<void> {
    await api.delete(`/profile/experience/${id}`);
  },
};
