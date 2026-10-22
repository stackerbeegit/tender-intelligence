import { api } from "./api";

/** Authenticated download: a plain <a href> can't carry the bearer token, so
 * fetch as a blob and save it under the server's file name. */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const response = await api.get(path, { responseType: "blob" });
  const disposition = String(response.headers["content-disposition"] ?? "");
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(response.data as Blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
