import { api } from "./api";
import type { TenderDocument } from "@/types/tender";

export const documentService = {
  async upload(tenderId: string, file: File, documentType: string): Promise<TenderDocument> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", documentType);
    const { data } = await api.post<TenderDocument>(`/tenders/${tenderId}/documents`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },

  async process(tenderId: string, documentId: string): Promise<TenderDocument> {
    const { data } = await api.post<TenderDocument>(`/tenders/${tenderId}/documents/${documentId}/process`);
    return data;
  },

  async get(tenderId: string, documentId: string): Promise<TenderDocument> {
    const { data } = await api.get<TenderDocument>(`/tenders/${tenderId}/documents/${documentId}`);
    return data;
  },

  async download(tenderId: string, documentId: string, fileName: string): Promise<void> {
    const response = await api.get(`/tenders/${tenderId}/documents/${documentId}/download`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(response.data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.click();
    URL.revokeObjectURL(url);
  },
};
