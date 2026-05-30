/**
 * Document model as returned by GET /documents.
 * status tracks ingestion: uploaded → processing → ready | failed.
 */

export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";

export interface Document {
  id: string;
  owner_id: string;
  /** Original uploaded filename — never changes, used for downloads. */
  filename: string;
  /** Optional friendly name the user can edit in the Dashboard. */
  display_name: string | null;
  file_type: string | null;
  visibility: string;
  status: DocumentStatus;
  created_at: string;
  updated_at: string;
}
