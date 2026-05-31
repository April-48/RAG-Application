/**
 * Chat page — three-column layout (Documents | messages | Sources).
 * Single-document MVP: pick one ready doc, ask questions, view cited chunks.
 * Supports ?doc=uuid deep link from Dashboard "Chat" button.
 */

import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { documentApi } from "../api/documentApi";
import { ApiError } from "../api/client";

import ChatBox from "../components/ChatBox";
import DocumentSearchInput from "../components/DocumentSearchInput";
import SourcePanel from "../components/SourcePanel";
import { useChat } from "../hooks/useChat";
import { useDocuments } from "../hooks/useDocuments";
import type { Document } from "../types/document";
import type { Source } from "../types/chat";
import { documentLabel } from "../utils/documentLabel";
import { matchesDocumentSearch } from "../utils/documentSearch";

/** Small checkbox-style dot for the selected document. */
function SelectionIndicator({ selected }: { selected: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition ${
        selected
          ? "border-indigo-600 bg-indigo-600 text-white"
          : "border-slate-300/80 bg-white/50"
      }`}
    >
      {selected && (
        <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="none">
          <path
            d="M2.5 6l2.5 2.5 4.5-5"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </span>
  );
}

/** Button to reopen the documents sidebar when it's hidden. */
function OpenDocumentsButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Open documents sidebar"
      className="inline-flex items-center gap-1.5 rounded-lg border border-white/60 bg-white/40 px-2.5 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-white/60"
    >
      <MenuIcon />
      <span>Documents</span>
    </button>
  );
}

/** Left sidebar listing ready documents with search. */
function DocumentSidebar({
  documents,
  loading,
  selectedId,
  onSelect,
  onClose,
}: {
  documents: Document[];
  loading: boolean;
  selectedId: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const [search, setSearch] = useState("");
  const ready = useMemo(
    () => documents.filter((d) => d.status === "ready"),
    [documents],
  );
  const filteredReady = useMemo(
    () => ready.filter((doc) => matchesDocumentSearch(doc, search)),
    [ready, search],
  );

  return (
    <aside
      className="flex h-full w-64 shrink-0 flex-col overflow-hidden border-r border-white/50 bg-white/20"
      aria-label="Documents sidebar"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-white/40 px-3 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Documents
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close documents sidebar"
          className="inline-flex shrink-0 items-center justify-center rounded-lg p-1.5 text-slate-500 transition hover:bg-white/50 hover:text-slate-700"
          title="Close documents sidebar"
        >
          <PanelCloseIcon />
        </button>
      </div>
      <div className="shrink-0 border-b border-white/40 px-2 py-2">
        <DocumentSearchInput
          value={search}
          onChange={setSearch}
          ariaLabel="Search ready documents"
          placeholder="Search…"
          className="text-xs"
        />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {loading ? (
          <p className="px-2 py-4 text-xs text-slate-400">Loading…</p>
        ) : ready.length === 0 ? (
          <p className="px-2 py-4 text-xs leading-relaxed text-slate-400">
            No ready documents yet.{" "}
            <Link to="/dashboard" className="text-indigo-600 hover:underline">
              Upload from Dashboard
            </Link>
            .
          </p>
        ) : filteredReady.length === 0 ? (
          <p className="px-2 py-4 text-xs leading-relaxed text-slate-400">
            No ready documents match your search.
          </p>
        ) : (
          <ul className="space-y-0.5" aria-label="Ready documents">
            {filteredReady.map((doc) => {
              const selected = doc.id === selectedId;
              const label = documentLabel(doc);
              return (
                <li key={doc.id}>
                  <button
                    type="button"
                    aria-current={selected ? "true" : undefined}
                    onClick={() => onSelect(doc.id)}
                    className={`flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2.5 text-left text-sm transition ${
                      selected
                        ? "bg-white/60 font-medium text-indigo-700 shadow-sm backdrop-blur-sm"
                        : "text-slate-700 hover:bg-white/40"
                    }`}
                    title={label}
                  >
                    <SelectionIndicator selected={selected} />
                    <span className="min-w-0 truncate">{label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}

/** Active chat area for one document — wires up ChatBox and SourcePanel. */
function ChatSession({
  documentId,
  selectedDoc,
  showDocuments,
  onOpenDocuments,
  showSources,
  onOpenSources,
  onCloseSources,
}: {
  documentId: string;
  selectedDoc: Document;
  showDocuments: boolean;
  onOpenDocuments: () => void;
  showSources: boolean;
  onOpenSources: () => void;
  onCloseSources: () => void;
}) {
  const { messages, busy, error, rateLimitWarning, loadingHistory, send } =
    useChat(documentId);
  const [pinnedSources, setPinnedSources] = useState<Source[] | null>(null);
  const [openingFile, setOpeningFile] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

  const latestSources = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "assistant" && m.sources && m.sources.length > 0) {
        return m.sources;
      }
    }
    return [];
  }, [messages]);

  const activeSources = pinnedSources ?? latestSources;

  /** Clear pinned sources when the user sends a new question. */
  const handleSend = (question: string) => {
    setPinnedSources(null);
    void send(question);
  };

  /** Open the original file for the selected document. */
  const handleOpenOriginalFile = async () => {
    setOpeningFile(true);
    setFileError(null);
    try {
      await documentApi.openOriginalFile(
        selectedDoc.id,
        selectedDoc.filename,
        selectedDoc.file_type ?? "",
      );
    } catch (err) {
      setFileError(
        err instanceof ApiError ? err.message : "Failed to open original file",
      );
    } finally {
      setOpeningFile(false);
    }
  };

  return (
    <div className="flex min-h-0 min-w-0 flex-1">
      <ChatBox
        messages={messages}
        busy={busy}
        error={error}
        rateLimitWarning={rateLimitWarning}
        loadingHistory={loadingHistory}
        onSend={handleSend}
        documentTitle={documentLabel(selectedDoc)}
        onOpenOriginalFile={() => void handleOpenOriginalFile()}
        openingFile={openingFile}
        fileError={fileError}
        showDocumentsSidebar={showDocuments}
        onOpenDocumentsSidebar={onOpenDocuments}
        showSourcesPanel={showSources}
        onOpenSourcesPanel={onOpenSources}
        onSelectSources={(sources) => {
          setPinnedSources(sources);
          if (!showSources) onOpenSources();
        }}
      />
      {showSources && (
        <SourcePanel sources={activeSources} onClose={onCloseSources} />
      )}
    </div>
  );
}

/** Placeholder when no document is selected yet. */
function CenterEmptyState({
  loading,
  hasReadyDocuments,
  invalidDocParam,
  showDocuments,
  onOpenDocuments,
}: {
  loading: boolean;
  hasReadyDocuments: boolean;
  invalidDocParam: boolean;
  showDocuments: boolean;
  onOpenDocuments: () => void;
}) {
  let message = "Select a document to start asking questions.";

  if (loading) {
    message = "Loading documents…";
  } else if (!hasReadyDocuments) {
    message = "No ready documents yet. Upload a document from the Dashboard.";
  } else if (invalidDocParam) {
    message =
      "That document isn't available for chat. Select one from the sidebar or upload on the Dashboard.";
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-white/15">
      {!showDocuments && (
        <div className="shrink-0 border-b border-white/50 bg-white/30 px-3 py-2.5 backdrop-blur-md">
          <OpenDocumentsButton onClick={onOpenDocuments} />
        </div>
      )}
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="max-w-md text-center">
          <p className="text-sm leading-relaxed text-slate-500">{message}</p>
          {!loading && !hasReadyDocuments && (
            <Link
              to="/dashboard"
              className="mt-4 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-700"
            >
              Go to Dashboard
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

/** Three-column chat page — pick a doc, ask questions, view sources. */
export default function ChatPage() {
  const { documents, loading, error: documentsError } = useDocuments();
  const [searchParams, setSearchParams] = useSearchParams();
  const docParam = searchParams.get("doc") ?? "";
  const [selectedId, setSelectedId] = useState("");
  const [showDocuments, setShowDocuments] = useState(true);
  const [showSources, setShowSources] = useState(true);

  const readyDocuments = useMemo(
    () => documents.filter((d) => d.status === "ready"),
    [documents],
  );

  const readyIds = useMemo(
    () => new Set(readyDocuments.map((d) => d.id)),
    [readyDocuments],
  );

  useEffect(() => {
    if (loading) return;
    if (docParam && readyIds.has(docParam)) {
      setSelectedId(docParam);
      return;
    }
    if (docParam && !readyIds.has(docParam)) {
      setSelectedId("");
      return;
    }
    if (!docParam && readyDocuments.length > 0) {
      const firstId = readyDocuments[0].id;
      setSelectedId(firstId);
      setSearchParams({ doc: firstId }, { replace: true });
    }
  }, [docParam, loading, readyDocuments, readyIds, setSearchParams]);

  /** Update selection and sync the ?doc= URL param. */
  const handleSelectDocument = (id: string) => {
    setSelectedId(id);
    setSearchParams({ doc: id }, { replace: true });
  };

  const selectedDoc = documents.find((d) => d.id === selectedId);
  const invalidDocParam = !loading && !!docParam && !readyIds.has(docParam);
  const canChat = !!selectedId && !!selectedDoc;

  return (
    <div className="flex h-[calc(100vh-4rem)] animate-fade-in flex-col">
      <header className="shrink-0 border-b border-white/40 bg-white/20 px-4 py-3 backdrop-blur-md">
        <h1 className="page-title">Chat</h1>
        <p className="page-subtitle">
          Ask questions grounded in your uploaded documents.
        </p>
        {documentsError && (
          <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
            Could not load your documents. Please refresh or try again.
          </p>
        )}
      </header>

      <div className="flex min-h-0 flex-1">
        {showDocuments && (
          <DocumentSidebar
            documents={documents}
            loading={loading}
            selectedId={selectedId}
            onSelect={handleSelectDocument}
            onClose={() => setShowDocuments(false)}
          />
        )}

        {canChat ? (
          <ChatSession
            key={selectedId}
            documentId={selectedId}
            selectedDoc={selectedDoc}
            showDocuments={showDocuments}
            onOpenDocuments={() => setShowDocuments(true)}
            showSources={showSources}
            onOpenSources={() => setShowSources(true)}
            onCloseSources={() => setShowSources(false)}
          />
        ) : (
          <CenterEmptyState
            loading={loading}
            hasReadyDocuments={readyDocuments.length > 0}
            invalidDocParam={invalidDocParam}
            showDocuments={showDocuments}
            onOpenDocuments={() => setShowDocuments(true)}
          />
        )}
      </div>
    </div>
  );
}

/** Hamburger icon for the documents sidebar toggle. */
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

/** Chevron icon for closing a sidebar panel. */
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
