/**
 * Chat API — ask a question, load history, stream answers over SSE.
 *
 * Streaming uses fetch + ReadableStream instead of EventSource because we need
 * to send Authorization headers (EventSource can't do custom headers easily).
 */

import type { AnswerResponse, MessageRecord, Source } from "../types/chat";
import { API_BASE_URL, ApiError, apiRequest, tokenStorage } from "./client";

export interface StreamHandlers {
  onToken: (token: string) => void;
  onSources: (sources: Source[]) => void;
  onError?: (message: string) => void;
}

export const chatApi = {
  /** Send a question and get the full answer in one JSON response. */
  ask: (documentId: string, question: string): Promise<AnswerResponse> =>
    apiRequest<AnswerResponse>(`/chat/${documentId}/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  /** Load past messages for a document. */
  history: (documentId: string): Promise<MessageRecord[]> =>
    apiRequest<MessageRecord[]>(`/chat/${documentId}/history`),

  /** Delete all saved messages for a document. */
  clearHistory: (documentId: string): Promise<{ deleted: number; cache_cleared: number }> =>
    apiRequest<{ deleted: number; cache_cleared: number }>(`/chat/${documentId}/history`, {
      method: "DELETE",
    }),

  /** Stream answer tokens over SSE and fire handlers as chunks arrive. */
  askStream: async (
    documentId: string,
    question: string,
    handlers: StreamHandlers,
    signal?: AbortSignal,
  ): Promise<void> => {
    const token = tokenStorage.get();
    const response = await fetch(`${API_BASE_URL}/chat/${documentId}/ask/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ question }),
      signal,
    });

    if (!response.ok || !response.body) {
      const data = await response.json().catch(() => null);
      const detail = (data && (data.detail || data.message)) || "Request failed";
      throw new ApiError(
        typeof detail === "string" ? detail : "Request failed",
        response.status,
      );
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    /** Parse one SSE frame and route it to the right handler. */
    const handleEvent = (raw: string) => {
      const line = raw.split("\n").find((l) => l.startsWith("data:"));
      if (!line) return;
      const json = line.slice(5).trim();
      if (!json) return;
      const event = JSON.parse(json) as { type: string; data?: unknown };
      if (event.type === "token") handlers.onToken(String(event.data ?? ""));
      else if (event.type === "sources")
        handlers.onSources((event.data as Source[]) ?? []);
      else if (event.type === "error")
        handlers.onError?.(String(event.data ?? "Stream error"));
    };

    // SSE frames are separated by blank lines — buffer until we have a full frame.
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        handleEvent(rawEvent);
      }
    }
  },
};
