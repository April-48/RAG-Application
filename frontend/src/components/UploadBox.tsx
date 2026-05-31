/**
 * Drag-and-drop upload area on the Dashboard.
 * Only accepts PDF / TXT / DOCX; shows progress bar via XMLHttpRequest.
 */

import { useRef, useState } from "react";

import { ApiError } from "../api/client";
import { documentApi } from "../api/documentApi";
import type { Document } from "../types/document";

interface UploadBoxProps {
  onUploaded: (document: Document) => void;
}

const ACCEPTED = [".pdf", ".txt", ".docx"];

/** Check if the file extension is one we accept. */
function isAccepted(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED.some((ext) => name.endsWith(ext));
}

/** Drag-and-drop upload area with progress bar. */
export default function UploadBox({ onUploaded }: UploadBoxProps) {
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  /** Send the file to the API and notify the parent when done. */
  const upload = async (file: File) => {
    if (!isAccepted(file)) {
      setError("Unsupported file type. Allowed: PDF, TXT, or DOCX");
      return;
    }
    setBusy(true);
    setError(null);
    setSuccessMessage(null);
    setProgress(0);
    try {
      const document = await documentApi.upload(file, setProgress);
      setSuccessMessage(
        document.status === "ready"
          ? "Ready to chat."
          : "Document uploaded. It may take a few seconds to process. Once it shows Ready, you can start asking questions.",
      );
      onUploaded(document);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setBusy(false);
      setProgress(0);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  /** Handle a file dropped onto the upload zone. */
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (busy) return;
    const file = e.dataTransfer.files?.[0];
    if (file) void upload(file);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!busy) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={`glass-panel border-2 border-dashed p-8 transition-all ${
        dragOver
          ? "border-indigo-400/80 bg-indigo-50/40 shadow-indigo-500/10"
          : "border-white/70"
      }`}
    >
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/60 bg-white/50 text-2xl shadow-inner backdrop-blur-sm">
          📄
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-800">Upload a document</h2>
          <p className="mt-1 text-sm text-slate-500">Drag &amp; drop a file here, or browse below</p>
        </div>

        <label htmlFor="document-upload" className="sr-only">
          Choose a document to upload
        </label>
        <input
          id="document-upload"
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,.docx"
          disabled={busy}
          aria-label="Choose a document to upload"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void upload(file);
          }}
          className="text-sm text-slate-600 file:mr-3 file:cursor-pointer file:rounded-xl file:border-0 file:bg-white/70 file:px-4 file:py-2 file:font-medium file:text-indigo-700 file:shadow-sm file:backdrop-blur-sm hover:file:bg-white/90 disabled:opacity-50"
        />
        <p className="text-xs text-slate-400">PDF, TXT, or DOCX</p>
      </div>

      {busy && (
        <div className="mt-6">
          <progress
            value={progress}
            max={100}
            className="h-2 w-full overflow-hidden rounded-full accent-indigo-600 [&::-webkit-progress-bar]:rounded-full [&::-webkit-progress-bar]:bg-white/60 [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:bg-gradient-to-r [&::-webkit-progress-value]:from-indigo-500 [&::-webkit-progress-value]:to-violet-500"
          >
            {progress}%
          </progress>
          <p className="mt-2 text-center text-xs text-slate-500">
            {progress < 100 ? `Uploading… ${progress}%` : "Processing on the server…"}
          </p>
        </div>
      )}

      {error && (
        <p className="mt-4 rounded-xl border border-red-200/80 bg-red-50/70 px-3 py-2 text-center text-sm text-red-700 backdrop-blur-sm">
          {error}
        </p>
      )}

      {successMessage && !busy && (
        <p className="mt-4 rounded-xl border border-emerald-200/80 bg-emerald-50/70 px-3 py-2 text-center text-sm text-emerald-800 backdrop-blur-sm">
          {successMessage}
        </p>
      )}
    </div>
  );
}
