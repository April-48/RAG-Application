/**
 * Dashboard document table — status badges, rename, view file, chat link, delete.
 * Parent passes a filtered list when the user is searching.
 */

import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import { documentApi } from "../api/documentApi";
import type { Document, DocumentStatus } from "../types/document";
import { documentLabel } from "../utils/documentLabel";

const STATUS_CONFIG: Record<
  DocumentStatus,
  { label: string; className: string; spinner: boolean }
> = {
  uploaded: {
    label: "Queued",
    className: "border-slate-200/80 bg-slate-100/70 text-slate-600",
    spinner: true,
  },
  processing: {
    label: "Processing",
    className: "border-amber-200/80 bg-amber-100/70 text-amber-800",
    spinner: true,
  },
  ready: {
    label: "Ready",
    className: "border-emerald-200/80 bg-emerald-100/70 text-emerald-800",
    spinner: false,
  },
  failed: {
    label: "Failed",
    className: "border-red-200/80 bg-red-100/70 text-red-700",
    spinner: false,
  },
};

/** Small spinning icon for in-progress status badges. */
function Spinner() {
  return (
    <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}

/** Pencil icon for the rename button. */
function RenameIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

/** Colored pill showing uploaded / processing / ready / failed. */
function StatusBadge({ status }: { status: DocumentStatus }) {
  const { label, className, spinner } = STATUS_CONFIG[status];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium backdrop-blur-sm ${className}`}
    >
      {spinner && <Spinner />}
      {label}
    </span>
  );
}

interface DocumentListProps {
  documents: Document[];
  searchActive?: boolean;
  onDelete: (id: string) => void;
  onRenamed: () => void;
}

/** Table of documents with rename, view, chat, and delete actions. */
export default function DocumentList({
  documents,
  searchActive = false,
  onDelete,
  onRenamed,
}: DocumentListProps) {
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [viewError, setViewError] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);
  const [renameBusy, setRenameBusy] = useState(false);

  /** Open the original file in a new tab or download it. */
  const handleView = async (doc: Document) => {
    setOpeningId(doc.id);
    setViewError(null);
    try {
      await documentApi.openOriginalFile(
        doc.id,
        doc.filename,
        doc.file_type ?? "",
      );
    } catch (err) {
      setViewError(
        err instanceof ApiError ? err.message : "Failed to open file",
      );
    } finally {
      setOpeningId(null);
    }
  };

  /** Switch a row into inline rename mode. */
  const startRename = (doc: Document) => {
    setRenamingId(doc.id);
    setRenameValue(documentLabel(doc));
    setRenameError(null);
  };

  /** Exit rename mode without saving. */
  const cancelRename = () => {
    setRenamingId(null);
    setRenameValue("");
    setRenameError(null);
  };

  /** Validate and save the new display name. */
  const submitRename = async (doc: Document) => {
    const trimmed = renameValue.trim();
    if (!trimmed) {
      setRenameError("Name must not be empty");
      return;
    }
    if (trimmed.length > 120) {
      setRenameError("Name must be 120 characters or fewer");
      return;
    }

    setRenameBusy(true);
    setRenameError(null);
    try {
      await documentApi.rename(doc.id, trimmed);
      cancelRename();
      onRenamed();
    } catch (err) {
      setRenameError(
        err instanceof ApiError ? err.message : "Failed to rename document",
      );
    } finally {
      setRenameBusy(false);
    }
  };

  if (documents.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-slate-500">
        {searchActive
          ? "No documents match your search."
          : "No documents yet. Upload one above to get started."}
      </p>
    );
  }

  return (
    <>
      {viewError && (
        <p className="mb-3 rounded-xl border border-red-200/80 bg-red-50/70 px-3 py-2 text-sm text-red-700 backdrop-blur-sm">
          {viewError}
        </p>
      )}
      <ul className="divide-y divide-white/50">
        {documents.map((doc) => (
          <li
            key={doc.id}
            className="flex items-center justify-between gap-3 py-4 transition hover:bg-white/20"
          >
            <div className="min-w-0 flex-1">
              {renamingId === doc.id ? (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    maxLength={120}
                    disabled={renameBusy}
                    className="glass-input w-full max-w-md text-sm"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void submitRename(doc);
                      if (e.key === "Escape") cancelRename();
                    }}
                  />
                  {renameError && (
                    <p className="text-xs text-red-600">{renameError}</p>
                  )}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => void submitRename(doc)}
                      disabled={renameBusy}
                      className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
                    >
                      {renameBusy ? "Saving…" : "Save"}
                    </button>
                    <button
                      type="button"
                      onClick={cancelRename}
                      disabled={renameBusy}
                      className="rounded-lg px-3 py-1 text-xs font-medium text-slate-600 transition hover:bg-white/40 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex min-w-0 items-center gap-2">
                    <p className="truncate text-sm font-semibold text-slate-800">
                      {documentLabel(doc)}
                    </p>
                    <button
                      type="button"
                      onClick={() => startRename(doc)}
                      className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-violet-200/80 bg-violet-50/70 px-2 py-0.5 text-[11px] font-medium text-violet-700 backdrop-blur-sm transition hover:border-violet-300 hover:bg-violet-100/80"
                      title="Rename document"
                    >
                      <RenameIcon className="h-3 w-3" />
                      Rename
                    </button>
                  </div>
                  <p className="text-xs text-slate-400">
                    {doc.file_type?.toUpperCase() ?? "—"} ·{" "}
                    {new Date(doc.created_at).toLocaleString()}
                    {doc.display_name && (
                      <span className="ml-1 text-slate-300">· {doc.filename}</span>
                    )}
                  </p>
                </>
              )}
            </div>
            {renamingId !== doc.id && (
              <div className="flex shrink-0 items-center gap-2">
                <StatusBadge status={doc.status} />
                {doc.status === "ready" && (
                  <>
                    <button
                      type="button"
                      onClick={() => void handleView(doc)}
                      disabled={openingId === doc.id}
                      className="rounded-lg border border-indigo-200/80 bg-white/50 px-3 py-1 text-xs font-medium text-indigo-700 backdrop-blur-sm transition hover:bg-white/70 disabled:opacity-50"
                    >
                      {openingId === doc.id ? "Opening…" : "View"}
                    </button>
                    <Link
                      to={`/chat?doc=${encodeURIComponent(doc.id)}`}
                      className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-medium text-white shadow-sm transition hover:bg-indigo-700"
                    >
                      Chat
                    </Link>
                  </>
                )}
                <button
                  type="button"
                  onClick={() => onDelete(doc.id)}
                  className="rounded-lg px-2 py-1 text-xs font-medium text-red-600 transition hover:bg-red-50/80"
                >
                  Delete
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
