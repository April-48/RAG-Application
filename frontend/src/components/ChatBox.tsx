/**
 * Center chat column: document header, scrollable messages, sticky input.
 * Messages are max-width centered like ChatGPT. Sidebar open buttons show
 * when the left/right panels are collapsed.
 */

import { useEffect, useRef, useState } from "react";

import type { ChatMessage, Source } from "../types/chat";
import TypingIndicator from "./chat/TypingIndicator";

interface ChatBoxProps {
  messages: ChatMessage[];
  busy: boolean;
  error: string | null;
  rateLimitWarning?: string | null;
  loadingHistory: boolean;
  clearingHistory?: boolean;
  onSend: (question: string) => void;
  onClearHistory?: () => void;
  onSelectSources?: (sources: Source[]) => void;
  documentTitle: string;
  onOpenOriginalFile?: () => void;
  openingFile?: boolean;
  fileError?: string | null;
  showDocumentsSidebar?: boolean;
  onOpenDocumentsSidebar?: () => void;
  showSourcesPanel?: boolean;
  onOpenSourcesPanel?: () => void;
  className?: string;
}

/** True while waiting for the first assistant token (streaming / busy, no text yet). */
function isPendingAssistantMessage(
  message: ChatMessage,
  index: number,
  messages: ChatMessage[],
  isLoading: boolean,
): boolean {
  if (index !== messages.length - 1) return false;
  if (message.role !== "assistant") return false;
  if (message.content.length > 0) return false;
  return isLoading || !!message.streaming;
}

/** Center chat column with messages and a sticky input bar. */
export default function ChatBox({
  messages,
  busy,
  error,
  rateLimitWarning = null,
  loadingHistory,
  clearingHistory = false,
  onSend,
  onClearHistory,
  onSelectSources,
  documentTitle,
  onOpenOriginalFile,
  openingFile = false,
  fileError = null,
  showDocumentsSidebar = true,
  onOpenDocumentsSidebar,
  showSourcesPanel = true,
  onOpenSourcesPanel,
  className = "",
}: ChatBoxProps) {
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  /** Send the trimmed input if we're not already waiting on a reply. */
  const submit = () => {
    const question = input.trim();
    if (!question || busy) return;
    onSend(question);
    setInput("");
  };

  /** Enter sends; Shift+Enter adds a newline. */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className={`flex min-h-0 min-w-0 flex-1 flex-col bg-white/20 ${className}`}>
      <header className="flex shrink-0 items-center gap-2 border-b border-white/50 bg-white/30 px-3 py-2.5 backdrop-blur-md">
        {!showDocumentsSidebar && onOpenDocumentsSidebar && (
          <button
            type="button"
            onClick={onOpenDocumentsSidebar}
            aria-label="Open documents sidebar"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-white/60 bg-white/40 px-2.5 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-white/60"
          >
            <MenuIcon />
            <span>Documents</span>
          </button>
        )}
        <h2 className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-800">
          {documentTitle}
        </h2>
        <div className="flex shrink-0 items-center gap-2">
          {onClearHistory && messages.length > 0 && (
            <button
              type="button"
              onClick={onClearHistory}
              disabled={busy || clearingHistory || loadingHistory}
              className="rounded-lg border border-white/60 bg-white/50 px-3 py-1.5 text-xs font-medium text-slate-600 backdrop-blur-sm transition hover:bg-white/70 hover:text-slate-800 disabled:opacity-50"
            >
              {clearingHistory ? "Clearing…" : "Clear history"}
            </button>
          )}
          {!showSourcesPanel && onOpenSourcesPanel && (
            <button
              type="button"
              onClick={onOpenSourcesPanel}
              aria-label="Open sources panel"
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/60 bg-white/40 px-2.5 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-white/60"
            >
              <SourcesIcon />
              <span>Sources</span>
            </button>
          )}
          {onOpenOriginalFile && (
            <button
              type="button"
              onClick={onOpenOriginalFile}
              disabled={openingFile}
              className="rounded-lg border border-white/60 bg-white/50 px-3 py-1.5 text-xs font-medium text-indigo-700 backdrop-blur-sm transition hover:bg-white/70 disabled:opacity-50"
            >
              {openingFile ? "Opening…" : "Open original file"}
            </button>
          )}
        </div>
      </header>

      {fileError && (
        <p className="shrink-0 border-b border-red-100 bg-red-50/80 px-4 py-2 text-xs text-red-700">
          {fileError}
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-4xl px-4 py-6">
          {loadingHistory ? (
            <p className="py-12 text-center text-sm text-slate-400">
              Loading conversation…
            </p>
          ) : messages.length === 0 ? (
            <p className="py-12 text-center text-sm text-slate-400">
              Ask a question about this document.
            </p>
          ) : (
            <div className="space-y-6" role="log" aria-label="Chat messages">
              {messages.map((m, i) => {
                if (isPendingAssistantMessage(m, i, messages, busy)) {
                  return (
                    <div
                      key={m.id ?? `assistant-pending-${i}`}
                      className="flex justify-start"
                    >
                      <TypingIndicator />
                    </div>
                  );
                }

                const hasSources = !!m.sources && m.sources.length > 0;
                const isUser = m.role === "user";
                const bubbleClassName = `max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                  isUser
                    ? "bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-indigo-500/20"
                    : "border border-white/60 bg-white/60 text-slate-800 backdrop-blur-md"
                } ${hasSources ? "cursor-pointer text-left transition hover:ring-2 hover:ring-indigo-300/50" : ""}`;
                const bubbleContent = (
                  <>
                    {m.content}
                    {hasSources && (
                      <span
                        className={`mt-2 block text-[10px] ${isUser ? "text-indigo-100/90" : "text-slate-400"}`}
                      >
                        {m.sources!.length} source
                        {m.sources!.length > 1 ? "s" : ""} · click to view
                      </span>
                    )}
                  </>
                );
                return (
                  <div
                    key={m.id ?? `${m.role}-${m.content.slice(0, 32)}-${i}`}
                    className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                  >
                    {hasSources ? (
                      <button
                        type="button"
                        onClick={() =>
                          onSelectSources?.(m.sources as Source[])
                        }
                        className={bubbleClassName}
                      >
                        {bubbleContent}
                      </button>
                    ) : (
                      <div className={bubbleClassName}>{bubbleContent}</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          <div ref={endRef} className="h-px" />
        </div>
      </div>

      {error && (
        <p className="shrink-0 border-t border-red-100 bg-red-50/80 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="sticky bottom-0 shrink-0 border-t border-white/50 bg-white/40 px-4 py-3 backdrop-blur-md">
        {busy && (
          <p
            role="status"
            aria-live="polite"
            className="mx-auto mb-2 flex w-full max-w-4xl items-center gap-2 rounded-lg border border-indigo-200/80 bg-indigo-50/90 px-3 py-2 text-sm text-indigo-900"
          >
            <TypingIndicatorDots />
            AI is answering. Please wait…
          </p>
        )}
        {rateLimitWarning && (
          <p
            role="alert"
            className="mx-auto mb-2 w-full max-w-4xl rounded-lg border border-amber-200/80 bg-amber-50/90 px-3 py-2 text-sm text-amber-900"
          >
            {rateLimitWarning}
          </p>
        )}
        <div className="mx-auto flex w-full max-w-4xl gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder={busy ? "AI is answering…" : "Message…"}
            aria-label="Message input"
            disabled={busy || loadingHistory || clearingHistory}
            className="glass-input min-h-[44px] flex-1 resize-none disabled:cursor-not-allowed disabled:opacity-60"
          />
          <button
            type="button"
            onClick={submit}
            disabled={busy || !input.trim() || loadingHistory || clearingHistory}
            aria-label={busy ? "Send message (disabled while AI is answering)" : "Send message"}
            className="btn-primary shrink-0 self-end"
          >
            {busy ? "Answering…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Three bouncing dots — inline compact version for the input status bar. */
function TypingIndicatorDots() {
  return (
    <span className="inline-flex shrink-0 items-center gap-0.5" aria-hidden="true">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-500 [animation-delay:-0.2s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-500 [animation-delay:-0.1s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-500" />
    </span>
  );
}

/** Hamburger icon for opening the documents sidebar. */
function MenuIcon() {
  return (
    <svg
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M4 6h16" />
      <path d="M4 12h16" />
      <path d="M4 18h16" />
    </svg>
  );
}

/** Document icon for opening the sources panel. */
function SourcesIcon() {
  return (
    <svg
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M8 13h8" />
      <path d="M8 17h8" />
    </svg>
  );
}
