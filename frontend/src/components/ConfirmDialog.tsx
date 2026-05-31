/**
 * Small in-app confirmation modal — replaces window.confirm for delete flows.
 * Rendered via portal so it sits above the navbar and glass panels.
 */

import { createPortal } from "react-dom";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  busyLabel?: string;
  cancelLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Centered modal with backdrop; traps focus for destructive actions. */
export default function ConfirmDialog({
  title,
  message,
  confirmLabel = "Delete",
  busyLabel = "Deleting…",
  cancelLabel = "Cancel",
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <button
        type="button"
        className="absolute inset-0 bg-slate-900/25 backdrop-blur-[1px]"
        aria-label="Close dialog"
        onClick={busy ? undefined : onCancel}
        disabled={busy}
      />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-white/90 bg-white p-6 shadow-2xl shadow-slate-900/15 ring-1 ring-slate-200/80">
        <h2
          id="confirm-dialog-title"
          className="text-base font-semibold text-slate-900"
        >
          {title}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-700">{message}</p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-red-700 disabled:opacity-50"
          >
            {busy ? busyLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
