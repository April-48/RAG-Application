/**
 * Right-hand Sources drawer — shows chunk text for the selected assistant answer.
 * User clicks a message with citations to pin sources here.
 */

import type { Source } from "../types/chat";

interface SourcePanelProps {
  sources: Source[];
  onClose: () => void;
  className?: string;
}

/** Right drawer that shows cited chunk text for an answer. */
export default function SourcePanel({
  sources,
  onClose,
  className = "",
}: SourcePanelProps) {
  return (
    <aside
      className={`flex h-full w-72 shrink-0 flex-col overflow-hidden border-l border-white/50 bg-white/25 lg:w-80 ${className}`}
      aria-label="Sources panel"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-white/40 px-3 py-3">
        <h2 className="min-w-0 truncate text-sm font-semibold text-slate-700">
          Sources{sources.length > 0 ? ` (${sources.length})` : ""}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close sources panel"
          className="inline-flex shrink-0 items-center justify-center rounded-lg p-1.5 text-slate-500 transition hover:bg-white/50 hover:text-slate-700"
          title="Close sources panel"
        >
          <PanelCloseIcon />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {sources.length === 0 ? (
          <p className="text-sm leading-relaxed text-slate-400">
            Click an assistant message with sources to view cited chunks here.
          </p>
        ) : (
          <ul className="space-y-3">
            {sources.map((source) => (
              <li
                key={source.chunk_index}
                className="rounded-xl border border-white/60 bg-white/50 p-3 shadow-sm backdrop-blur-sm"
              >
                <p className="mb-1.5 text-xs font-semibold text-indigo-600/90">
                  Chunk #{source.chunk_index}
                  {source.page_number != null && ` · Page ${source.page_number}`}
                </p>
                <p className="line-clamp-6 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                  {source.chunk_text}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

/** Chevron icon for closing the panel. */
function PanelCloseIcon() {
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
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}
