import { api } from "./api";
import { downloadFile } from "./download";
import type {
  BidDraft,
  BidPreparation,
  BidPreparationStart,
  ChecklistItem,
  ChecklistStatus,
  DirectoryUser,
  OpportunityDetail,
  OpportunityListItem,
  OpportunityListResponse,
  OpportunityStatus,
  OpportunityTeam,
} from "@/types/opportunity";

export interface OpportunityFilters {
  status?: OpportunityStatus;
  mine?: boolean;
  open_only?: boolean;
  page?: number;
  page_size?: number;
}

export const opportunityService = {
  async list(filters: OpportunityFilters): Promise<OpportunityListResponse> {
    const { data } = await api.get<OpportunityListResponse>("/opportunities", { params: filters });
    return data;
  },

  async get(id: string): Promise<OpportunityDetail> {
    const { data } = await api.get<OpportunityDetail>(`/opportunities/${id}`);
    return data;
  },

  async forTender(tenderId: string): Promise<OpportunityListItem | null> {
    const { data } = await api.get<{ opportunity: OpportunityListItem | null }>(`/tenders/${tenderId}/opportunity`);
    return data.opportunity;
  },

  async create(tenderId: string): Promise<OpportunityDetail> {
    const { data } = await api.post<OpportunityDetail>("/opportunities", { tender_id: tenderId });
    return data;
  },

  async transition(id: string, toStatus: OpportunityStatus, comment?: string): Promise<OpportunityDetail> {
    const { data } = await api.post<OpportunityDetail>(`/opportunities/${id}/transitions`, {
      to_status: toStatus,
      comment: comment || null,
    });
    return data;
  },

  async setOwner(id: string, ownerId: string | null): Promise<OpportunityDetail> {
    const { data } = await api.patch<OpportunityDetail>(`/opportunities/${id}`, { owner_id: ownerId });
    return data;
  },

  async assign(id: string, userId: string, team: OpportunityTeam): Promise<OpportunityDetail> {
    const { data } = await api.post<OpportunityDetail>(`/opportunities/${id}/assignments`, { user_id: userId, team });
    return data;
  },

  async unassign(id: string, assignmentId: string): Promise<void> {
    await api.delete(`/opportunities/${id}/assignments/${assignmentId}`);
  },

  async addNote(id: string, text: string): Promise<void> {
    await api.post(`/opportunities/${id}/notes`, { note_text: text });
  },

  async directory(): Promise<DirectoryUser[]> {
    const { data } = await api.get<DirectoryUser[]>("/users/directory");
    return data;
  },
};

export const bidService = {
  /** "Interested — prepare bid". Can take a minute: it writes a draft with the AI model. */
  async start(tenderId: string): Promise<BidPreparationStart> {
    const { data } = await api.post<BidPreparationStart>(`/tenders/${tenderId}/bid-preparation`);
    return data;
  },

  async get(opportunityId: string): Promise<BidPreparation> {
    const { data } = await api.get<BidPreparation>(`/opportunities/${opportunityId}/bid-preparation`);
    return data;
  },

  async generateDraft(opportunityId: string): Promise<BidDraft> {
    const { data } = await api.post<BidDraft>(`/opportunities/${opportunityId}/bid-drafts`);
    return data;
  },

  async syncChecklist(opportunityId: string): Promise<BidPreparation> {
    const { data } = await api.post<BidPreparation>(`/opportunities/${opportunityId}/checklist/sync`);
    return data;
  },

  async addItem(opportunityId: string, title: string): Promise<ChecklistItem> {
    const { data } = await api.post<ChecklistItem>(`/opportunities/${opportunityId}/checklist`, { title });
    return data;
  },

  async updateItem(
    opportunityId: string,
    itemId: string,
    changes: { status?: ChecklistStatus; owner_id?: string | null; note?: string | null },
  ): Promise<ChecklistItem> {
    const { data } = await api.patch<ChecklistItem>(`/opportunities/${opportunityId}/checklist/${itemId}`, changes);
    return data;
  },

  async deleteItem(opportunityId: string, itemId: string): Promise<void> {
    await api.delete(`/opportunities/${opportunityId}/checklist/${itemId}`);
  },

  downloadDraft: (opportunityId: string, version?: number) =>
    downloadFile(
      `/opportunities/${opportunityId}/bid-pack/draft.docx${version ? `?version=${version}` : ""}`,
      "draft-bid.docx",
    ),
  downloadChecklist: (opportunityId: string) =>
    downloadFile(`/opportunities/${opportunityId}/bid-pack/checklist.xlsx`, "checklist.xlsx"),
  downloadPack: (opportunityId: string) => downloadFile(`/opportunities/${opportunityId}/bid-pack.zip`, "bid-pack.zip"),
};
