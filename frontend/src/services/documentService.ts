import axios from "axios";

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

  /** Rejects with the server's reason (e.g. the portal couldn't be reached). */
  async download(tenderId: string, documentId: string, fileName: string): Promise<void> {
    let response;
    try {
      response = await api.get(`/tenders/${tenderId}/documents/${documentId}/download`, { responseType: "blob" });
    } catch (err) {
      // With responseType "blob" the error body is a Blob too; read its JSON detail.
      const body = axios.isAxiosError(err) ? err.response?.data : undefined;
      let detail = "The download failed.";
      if (body instanceof Blob) {
        try {
          detail = JSON.parse(await body.text()).detail ?? detail;
        } catch {
          /* not JSON — keep the generic message */
        }
      }
      throw new Error(detail);
    }
    const url = URL.createObjectURL(response.data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.click();
    URL.revokeObjectURL(url);
  },
};
