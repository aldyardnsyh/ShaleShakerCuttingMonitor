"use client";

import { createContext, useCallback, useContext, useState } from "react";

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastCtx {
  show: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastCtx | null>(null);

let nextId = 0;

export function useToast(): ToastCtx {
  const c = useContext(ToastContext);
  if (!c) throw new Error("useToast must be used within ToastProvider");
  return c;
}

const ICONS: Record<ToastType, string> = {
  success: "M22 11.08V12a10 10 0 11-5.93-9.14 M22 4L12 14.01l-3-3",
  error: "M18 6L6 18M6 6l12 12",
  info: "M12 22a10 10 0 100-20 10 10 0 000 20z M12 16v-4 M12 8h.01",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const show = useCallback((message: string, type: ToastType = "info") => {
    const id = ++nextId;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[200] flex flex-col-reverse gap-2 pointer-events-none" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="alert"
            className={`pointer-events-auto flex items-start gap-3 px-4 py-3 pr-10 rounded-xl shadow-lg text-sm font-medium animate-toast-in bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 min-w-[300px] max-w-[400px]`}
          >
            <span className={`shrink-0 grid h-6 w-6 place-items-center rounded-full text-white ${
              t.type === "success" ? "bg-emerald-500" : t.type === "error" ? "bg-rose-500" : "bg-sky-500"
            }`}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d={ICONS[t.type]} />
              </svg>
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-0.5">
                {t.type === "success" ? "Berhasil" : t.type === "error" ? "Gagal" : "Info"}
              </p>
              <p className="text-sm text-slate-700 dark:text-slate-200 leading-snug">{t.message}</p>
            </div>
            <button
              onClick={() => remove(t.id)}
              className="absolute top-2.5 right-2.5 shrink-0 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
              aria-label="Tutup"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6L6 18M6 6l12 12" /></svg>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
