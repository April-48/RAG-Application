/**
 * Hook for loading the user's document list from GET /documents.
 *
 * We poll every 5 seconds while any doc is still "uploaded" or "processing"
 * so the Dashboard can show status badges updating without a manual refresh.
 * Once everything is ready or failed, polling stops to save requests.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { documentApi } from "../api/documentApi";
import type { Document } from "../types/document";

const POLL_INTERVAL_MS = 5000;

/** True while the backend worker is still ingesting the file. */
function isInProgress(document: Document): boolean {
  return document.status === "uploaded" || document.status === "processing";
}

export interface UseDocumentsResult {
  documents: Document[];
  loading: boolean;
  error: string | null;
  refreshDocuments: () => Promise<void>;
}

/** Load the user's documents and poll while any are still processing. */
export function useDocuments(): UseDocumentsResult {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  /** Fetch documents from the API, optionally without the loading spinner. */
  const load = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) setLoading(true);
    try {
      const docs = await documentApi.list();
      if (!mountedRef.current) return;
      setDocuments(docs);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(
        err instanceof ApiError ? err.message : "Failed to load documents",
      );
    } finally {
      if (mountedRef.current && !options?.silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Only spin up the interval while something is still processing.
  const shouldPoll = documents.some(isInProgress);
  useEffect(() => {
    if (!shouldPoll) return;
    const intervalId = window.setInterval(() => {
      void load({ silent: true });
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(intervalId);
  }, [shouldPoll, load]);

  /** Re-fetch without flashing the full-page loading state (handy after upload). */
  const refreshDocuments = useCallback(() => load({ silent: true }), [load]);

  return { documents, loading, error, refreshDocuments };
}
