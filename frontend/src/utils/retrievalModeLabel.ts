/** Human-readable label for the hybrid retrieval router mode shown in chat. */
export function formatRetrievalModeLabel(
  mode: string,
  page?: number | null,
  section?: string | null,
): string {
  switch (mode) {
    case "semantic":
      return "Semantic search";
    case "page_lookup":
      return page != null ? `Page lookup · p.${page}` : "Page lookup";
    case "section_lookup":
      return section ? `Section lookup · ${section}` : "Section lookup";
    case "whole_document_summary":
      return "Summary";
    case "document_beginning":
      return "Document beginning";
    case "document_ending":
      return "Document ending";
    default:
      return mode.replace(/_/g, " ");
  }
}
