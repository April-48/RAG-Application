/**
 * TypeScript shapes for chat-related API responses and UI state.
 * Sources are the retrieved chunks the LLM cited in an answer.
 */

export interface Source {
  chunk_index: number;
  page_number: number | null;
  chunk_text: string;
}

export interface AnswerResponse {
  answer: string;
  sources: Source[];
}

/** One bubble in the Chat UI (not exactly the same as a DB Message row). */
export interface ChatMessage {
  id?: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  /** True while tokens are still streaming into this assistant message. */
  streaming?: boolean;
}

/** Row from GET /chat/:documentId/history — includes DB id + timestamp. */
export interface MessageRecord {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  sources: Source[];
  created_at: string;
}
