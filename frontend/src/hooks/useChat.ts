/**
 * Chat state for one document at a time (single-doc MVP).
 *
 * Loads history on mount, sends questions via SSE streaming, and falls back
 * to the one-shot /ask endpoint if streaming breaks. Assistant messages can
 * carry source chunks for the Sources panel.
 *
 * Only one active request at a time per hook instance — send() no-ops while
 * busy. Pass onBusyChange so the parent can block document switches globally.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { chatApi } from "../api/chatApi";
import { ApiError } from "../api/client";
import type { ChatMessage, Source } from "../types/chat";

export interface UseChatOptions {
  /** Called when a send/stream starts or finishes — use to lock the whole page. */
  onBusyChange?: (busy: boolean) => void;
}

export interface UseChatResult {
  messages: ChatMessage[];
  busy: boolean;
  error: string | null;
  rateLimitWarning: string | null;
  loadingHistory: boolean;
  clearingHistory: boolean;
  send: (question: string) => Promise<void>;
  clearHistory: () => Promise<boolean>;
}

/** Chat hook for one document — history, streaming send, and error state. */
export function useChat(documentId: string, options: UseChatOptions = {}): UseChatResult {
  const { onBusyChange } = options;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rateLimitWarning, setRateLimitWarning] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [clearingHistory, setClearingHistory] = useState(false);
  const busyRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);

  const setBusyState = useCallback(
    (next: boolean) => {
      busyRef.current = next;
      setBusy(next);
      onBusyChange?.(next);
    },
    [onBusyChange],
  );

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

  // Abort any in-flight stream when this document's chat unmounts.
  useEffect(() => {
    return () => {
      if (busyRef.current) {
        abortRef.current?.abort();
        busyRef.current = false;
        onBusyChange?.(false);
      }
    };
  }, [onBusyChange]);

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

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setBusyState(true);
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
        await chatApi.askStream(
          documentId,
          question,
          {
            onToken: (token) =>
              updateLastAssistant((m) => ({
                ...m,
                content: m.content + token,
              })),
            onSources: (sources: Source[]) =>
              updateLastAssistant((m) => ({ ...m, sources })),
            onError: (message) => setError(message),
          },
          controller.signal,
        );
        updateLastAssistant((m) => ({ ...m, streaming: false }));
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }
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
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
        if (!controller.signal.aborted) {
          setBusyState(false);
        }
      }
    },
    [documentId, setBusyState, updateLastAssistant],
  );

  /** Delete all saved messages for this document and reset local state. */
  const clearHistory = useCallback(async (): Promise<boolean> => {
    if (busyRef.current || clearingHistory) return false;

    setClearingHistory(true);
    setError(null);
    try {
      await chatApi.clearHistory(documentId);
      setMessages([]);
      setRateLimitWarning(null);
      return true;
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to clear history",
      );
      return false;
    } finally {
      setClearingHistory(false);
    }
  }, [clearingHistory, documentId]);

  return {
    messages,
    busy,
    error,
    rateLimitWarning,
    loadingHistory,
    clearingHistory,
    send,
    clearHistory,
  };
}
