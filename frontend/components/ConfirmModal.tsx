"use client";

import { useEffect } from "react";

interface Props {
  open: boolean;
  title: string;
  message: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Styled confirmation modal (replaces window.confirm / alert). Backdrop blur,
 * keyboard ESC to cancel, focus-friendly. Used e.g. for deleting a history row.
 */
export default function ConfirmModal({
  open, title, message, confirmLabel = "Konfirmasi", cancelLabel = "Batal",
  danger = false, busy = false, onConfirm, onCancel,
}: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-md" onClick={busy ? undefined : onCancel} />
      <div className="relative z-10 w-full max-w-md rounded-2xl bg-white dark:bg-slate-800 shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="p-5">
          <div className="flex items-start gap-3">
            <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-full ${danger ? "bg-rose-100 text-rose-600 dark:bg-rose-500/15" : "bg-brand-light text-brand-dark"}`}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                <path d="M12 9v4 M12 17h.01" />
              </svg>
            </div>
            <div className="min-w-0">
              <h3 className="font-semibold text-slate-800 dark:text-slate-100">{title}</h3>
              <div className="text-sm text-slate-600 dark:text-slate-300 mt-1">{message}</div>
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-5 py-3 bg-slate-50 dark:bg-slate-900/40 border-t border-slate-200 dark:border-slate-700">
          <button onClick={onCancel} disabled={busy} className="btn-muted">{cancelLabel}</button>
          <button onClick={onConfirm} disabled={busy} className={danger ? "btn-danger" : "btn-primary"}>
            {busy ? "Memproses…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
