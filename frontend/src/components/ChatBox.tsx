/**
 * Center chat column: document header, scrollable messages, sticky input.
 * Messages are max-width centered like ChatGPT. Sidebar open buttons show
 * when the left/right panels are collapsed.
 */

import { useEffect, useRef, useState } from "react";

import type { ChatMessage, Source } from "../types/chat";

interface ChatBoxProps {
  messages: ChatMessage[];
  busy: boolean;
  error: string | null;
  loadingHistory: boolean;
  onSend: (question: string) => void;
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

/** Center chat column with messages and a sticky input bar. */
export default function ChatBox({
  messages,
  busy,
  error,
  loadingHistory,
  onSend,
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
  }, [messages]);

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
            <ul className="space-y-6">
              {messages.map((m, i) => {
                const hasSources = !!m.sources && m.sources.length > 0;
                const isUser = m.role === "user";
                return (
                  <li
                    key={i}
                    className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      role={hasSources ? "button" : undefined}
                      tabIndex={hasSources ? 0 : undefined}
                      onClick={() =>
                        hasSources && onSelectSources?.(m.sources as Source[])
                      }
                      onKeyDown={(e) => {
                        if (
                          hasSources &&
                          (e.key === "Enter" || e.key === " ")
                        ) {
                          e.preventDefault();
                          onSelectSources?.(m.sources as Source[]);
                        }
                      }}
                      className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                        isUser
                          ? "bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-indigo-500/20"
                          : "border border-white/60 bg-white/60 text-slate-800 backdrop-blur-md"
                      } ${hasSources ? "cursor-pointer transition hover:ring-2 hover:ring-indigo-300/50" : ""}`}
                    >
                      {m.content}
                      {m.streaming && (
                        <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse align-middle rounded-sm bg-indigo-300/80" />
                      )}
                      {hasSources && (
                        <span
                          className={`mt-2 block text-[10px] ${isUser ? "text-indigo-100/90" : "text-slate-400"}`}
                        >
                          {m.sources!.length} source
                          {m.sources!.length > 1 ? "s" : ""} · click to view
                        </span>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
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
        <div className="mx-auto flex w-full max-w-4xl gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Message…"
            aria-label="Message input"
            className="glass-input min-h-[44px] flex-1 resize-none"
          />
          <button
            type="button"
            onClick={submit}
            disabled={busy || !input.trim()}
            aria-label="Send message"
            className="btn-primary shrink-0 self-end"
          >
            Send
          </button>
        </div>
      </div>
    </div>
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
