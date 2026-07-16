"use client";

import { SessionOut } from "@/lib/api";

const statusBadge: Record<string, string> = {
  done: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300",
  running: "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300",
  error: "bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300",
  cancelled: "bg-slate-100 text-slate-600 dark:bg-slate-600/30 dark:text-slate-300",
  created: "bg-slate-100 text-slate-600 dark:bg-slate-600/30 dark:text-slate-300",
};

interface Props {
  sessions: SessionOut[];
  selectedId?: number;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
}

export default function SessionTable({ sessions, selectedId, onSelect, onDelete }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase text-slate-500 border-b border-slate-200 dark:border-slate-700">
          <tr>
            <th className="px-3 py-2 font-semibold">ID</th>
            <th className="px-3 py-2 font-semibold">Nama</th>
            <th className="px-3 py-2 font-semibold">Model</th>
            <th className="px-3 py-2 font-semibold">Status</th>
            <th className="px-3 py-2 font-semibold">Dibuat</th>
            <th className="px-3 py-2 font-semibold">Aksi</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr
              key={s.id}
              tabIndex={0}
              role="button"
              aria-pressed={selectedId === s.id}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(s.id); } }}
              onClick={() => onSelect(s.id)}
              className={`cursor-pointer border-b border-slate-100 dark:border-slate-700/50 hover:bg-brand-light/60 dark:hover:bg-slate-700/40 ${
                selectedId === s.id ? "bg-brand-light dark:bg-slate-700/60" : ""
              }`}
            >
              <td className="px-3 py-2 text-slate-500">{s.id}</td>
              <td className="px-3 py-2 font-medium text-slate-800 dark:text-slate-100">{s.name}</td>
              <td className="px-3 py-2">{s.model}</td>
              <td className="px-3 py-2">
                <span className={`badge ${statusBadge[s.status] ?? statusBadge.created}`}>{s.status}</span>
              </td>
              <td className="px-3 py-2 text-slate-500">
                {new Date(s.created_at).toLocaleDateString("id-ID", {
                  day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
                })}
              </td>
              <td className="px-3 py-2">
                {s.status === "running" ? (
                  <button
                    disabled
                    className="inline-flex items-center gap-1 text-slate-300 dark:text-slate-600 cursor-not-allowed"
                    title="Sesi sedang berjalan, hentikan (Stop) dulu sebelum menghapus"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0110 0v4" /></svg>
                    Terkunci
                  </button>
                ) : (
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(s.id); }}
                    className="inline-flex items-center gap-1 text-rose-600 hover:text-rose-700 font-medium"
                    title="Hapus sesi"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18 M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2 M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6 M10 11v6 M14 11v6" /></svg>
                    Hapus
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
