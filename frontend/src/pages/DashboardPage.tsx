/**
 * Dashboard — upload files and manage your document list.
 * Search + rename + view/chat/delete all live in DocumentList below.
 */

import { useMemo, useState } from "react";

import { documentApi } from "../api/documentApi";
import { ApiError } from "../api/client";
import DocumentList from "../components/DocumentList";
import DocumentSearchInput from "../components/DocumentSearchInput";
import UploadBox from "../components/UploadBox";
import { useDocuments } from "../hooks/useDocuments";
import { matchesDocumentSearch } from "../utils/documentSearch";

/** Upload and manage documents — search, rename, delete, chat. */
export default function DashboardPage() {
  const { documents, loading, error, refreshDocuments } = useDocuments();
  const [search, setSearch] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const filteredDocuments = useMemo(
    () => documents.filter((doc) => matchesDocumentSearch(doc, search)),
    [documents, search],
  );

  const searchActive = search.trim().length > 0;

  /** Refresh the list after a successful upload. */
  const handleUploaded = () => {
    void refreshDocuments();
  };

  /** Delete a document and refresh the list. */
  const handleDelete = async (id: string) => {
    setDeleteError(null);
    try {
      await documentApi.remove(id);
    } catch (err) {
      setDeleteError(
        err instanceof ApiError ? err.message : "Failed to delete document",
      );
    } finally {
      void refreshDocuments();
    }
  };

  return (
    <div className="mx-auto max-w-5xl animate-fade-in space-y-6 px-4 py-8">
      <header className="space-y-1">
        <h1 className="page-title">Your documents</h1>
        <p className="page-subtitle">
          Upload PDF, TXT, or DOCX files — we&apos;ll parse and index them for Q&amp;A.
        </p>
      </header>

      <UploadBox onUploaded={handleUploaded} />

      {deleteError && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {deleteError}
        </p>
      )}

      <div className="glass-panel p-5">
        {loading ? (
          <p className="py-10 text-center text-sm text-slate-500">Loading…</p>
        ) : error ? (
          <p className="py-10 text-center text-sm text-red-600">{error}</p>
        ) : (
          <>
            <div className="mb-4">
              <DocumentSearchInput
                value={search}
                onChange={setSearch}
                ariaLabel="Search documents"
                placeholder="Search documents…"
              />
            </div>
            <DocumentList
              documents={filteredDocuments}
              searchActive={searchActive}
              onDelete={handleDelete}
              onRenamed={() => void refreshDocuments()}
            />
          </>
        )}
      </div>
    </div>
  );
}
