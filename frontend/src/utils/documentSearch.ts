/**
 * Client-side document search — matches against the visible label only.
 * We don't hit the server; just filter whatever GET /documents already returned.
 */

import type { Document } from "../types/document";
import { documentLabel } from "./documentLabel";

/** Check if a document's label matches the search query (client-side only). */
export function matchesDocumentSearch(
  doc: Pick<Document, "display_name" | "filename">,
  query: string,
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return documentLabel(doc).toLowerCase().includes(q);
}
