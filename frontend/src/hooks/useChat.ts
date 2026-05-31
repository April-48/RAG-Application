/**
 * Chat state for one document at a time (single-doc MVP).
 *
 * Loads history on mount, sends questions via SSE streaming, and falls back
 * to the one-shot /ask endpoint if streaming breaks. Assistant messages can
 * carry source chunks for the Sources panel.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { chatApi } from "../api/chatApi";
import { ApiError } from "../api/client";
import type { ChatMessage, Source } from "../types/chat";

export interface UseChatResult {
  messages: ChatMessage[];
  busy: boolean;
  error: string | null;
  rateLimitWarning: string | null;
  loadingHistory: boolean;
  send: (question: string) => Promise<void>;
}

/** Chat hook for one document — history, streaming send, and error state. */
export function useChat(documentId: string): UseChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rateLimitWarning, setRateLimitWarning] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const busyRef = useRef(false);

  // Switching documents = new history fetch. cancelled flag avoids race updates.
  useEffect(() => {
    let cancelled = false;
    setLoadingHistory(true);
    setMessages([]);
    setError(null);
    setRateLimitWarning(null);
    chatApi
      .history(documentId)
      .then((records) => {
        if (cancelled) return;
        setMessages(
          records
            .filter((r) => r.role === "user" || r.role === "assistant")
            .map((r) => ({
              id: r.id,
              role: r.role as "user" | "assistant",
              content: r.content,
              sources: r.sources,
            })),
        );
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError ? err.message : "Failed to load history",
        );
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  /** Patch the last assistant bubble (used while tokens stream in). */
  const updateLastAssistant = useCallback(
    (patch: (msg: ChatMessage) => ChatMessage) => {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.role === "assistant") {
          next[next.length - 1] = patch(last);
        }
        return next;
      });
    },
    [],
  );

  /** Send a question — streams tokens, falls back to /ask if SSE fails. */
  const send = useCallback(
    async (raw: string) => {
      const question = raw.trim();
      if (!question || busyRef.current) return;

      busyRef.current = true;
      setBusy(true);
      setError(null);
      setRateLimitWarning(null);
      // Optimistic UI: show user msg + empty assistant placeholder immediately.
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "user", content: question },
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "",
          streaming: true,
        },
      ]);

      try {
        await chatApi.askStream(documentId, question, {
          onToken: (token) =>
            updateLastAssistant((m) => ({
              ...m,
              content: m.content + token,
            })),
          onSources: (sources: Source[]) =>
            updateLastAssistant((m) => ({ ...m, sources })),
          onError: (message) => setError(message),
        });
        updateLastAssistant((m) => ({ ...m, streaming: false }));
      } catch (err) {
        if (err instanceof ApiError && err.status === 429) {
          setRateLimitWarning(err.message);
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === "assistant" && last.content === "") {
              next.pop();
            }
            return next;
          });
          return;
        }
        // Stream failed — try the regular JSON endpoint as backup.
        try {
          const result = await chatApi.ask(documentId, question);
          updateLastAssistant(() => ({
            role: "assistant",
            content: result.answer,
            sources: result.sources,
            streaming: false,
          }));
        } catch (fallbackErr) {
          if (fallbackErr instanceof ApiError && fallbackErr.status === 429) {
            setRateLimitWarning(fallbackErr.message);
          } else {
            setError(
              fallbackErr instanceof ApiError
                ? fallbackErr.message
                : "Something went wrong",
            );
          }
          // Remove the empty assistant bubble we added optimistically.
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === "assistant" && last.content === "") {
              next.pop();
            }
            return next;
          });
        }
      } finally {
        busyRef.current = false;
        setBusy(false);
      }
    },
    [documentId, updateLastAssistant],
  );

  return { messages, busy, error, rateLimitWarning, loadingHistory, send };
}
