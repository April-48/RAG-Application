/**
 * What name to show in the UI: custom display_name if set, else filename.
 */

import type { Document } from "../types/document";

/** Pick display_name if set, otherwise fall back to the filename. */
export function documentLabel(doc: Pick<Document, "display_name" | "filename">): string {
  const name = doc.display_name?.trim();
  return name || doc.filename;
}
