/**
 * Document API — list, upload, rename, delete, and open the original file.
 *
 * openOriginalFile is special: we fetch with auth, turn the response into a
 * blob URL, then open in a new tab (PDF/TXT) or trigger download (DOCX).
 * We can't just window.open the API URL because the JWT lives in a header.
 */

import type { Document } from "../types/document";
import { API_BASE_URL, ApiError, apiRequest, tokenStorage, uploadWithProgress } from "./client";

const FILE_MEDIA_TYPES: Record<string, string> = {
  pdf: "application/pdf",
  txt: "text/plain",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};

/** Fetch the original file with auth and open or download it in the browser. */
export async function openOriginalFile(
  documentId: string,
  filename: string,
  fileType: string,
): Promise<void> {
  const headers: Record<string, string> = {};
  const token = tokenStorage.get();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/file`, {
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      tokenStorage.clear();
      const path = window.location.pathname;
      if (path !== "/login" && path !== "/signup") {
        window.location.assign("/login");
      }
    }
    const data = await response.json().catch(() => null);
    const detail =
      (data && (data.detail || data.message)) || response.statusText;
    throw new ApiError(
      typeof detail === "string" ? detail : "Failed to open file",
      response.status,
    );
  }

  const ext = fileType.toLowerCase();
  const blobType = FILE_MEDIA_TYPES[ext] ?? response.headers.get("Content-Type") ?? undefined;
  const blob = await response.blob();
  const typedBlob = blobType ? new Blob([blob], { type: blobType }) : blob;
  const url = URL.createObjectURL(typedBlob);

  try {
    if (ext === "docx") {
      // Browsers can't preview DOCX inline — download with the real filename.
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
    } else {
      window.open(url, "_blank", "noopener,noreferrer");
    }
  } finally {
    // Revoke later so the new tab has time to load the blob.
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }
}

export const documentApi = {
  /** Get all documents for the logged-in user. */
  list: (): Promise<Document[]> => apiRequest<Document[]>("/documents"),

  /** Fetch one document by id. */
  get: (id: string): Promise<Document> =>
    apiRequest<Document>(`/documents/${id}`),

  /** Upload a file and optionally track upload progress. */
  upload: (
    file: File,
    onProgress?: (percent: number) => void,
  ): Promise<Document> => {
    const form = new FormData();
    form.append("file", file);
    return uploadWithProgress<Document>("/documents/upload", form, onProgress);
  },

  /** Delete a document by id. */
  remove: (id: string): Promise<void> =>
    apiRequest<void>(`/documents/${id}`, { method: "DELETE" }),

  /** Change the display name shown in the UI. */
  rename: (id: string, displayName: string): Promise<Document> =>
    apiRequest<Document>(`/documents/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ display_name: displayName }),
    }),

  openOriginalFile,
};
