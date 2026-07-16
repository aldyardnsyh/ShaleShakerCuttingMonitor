"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { api, SessionOut, Measurement } from "@/lib/api";
import SessionTable from "@/components/SessionTable";
import ConfirmModal from "@/components/ConfirmModal";
import { useToast } from "@/components/Toast";

export default function HistoryPage() {
  const [sessions, setSessions] = useState<SessionOut[]>([]);
  const [selectedId, setSelectedId] = useState<number>();
  const [detail, setDetail] = useState<SessionOut | null>(null);
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const toast = useToast();

  useEffect(() => {
    api.listSessions().then((s) => { setSessions(s); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setDetail(null); setMeasurements([]);
    Promise.all([api.getSession(selectedId), api.listMeasurements(selectedId)]).then(([s, m]) => {
      setDetail(s); setMeasurements(m);
    });
  }, [selectedId]);

  const refresh = () => api.listSessions().then(setSessions).catch(() => {});

  const confirmDelete = async () => {
    if (pendingDelete == null) return;
    const id = pendingDelete;
    setDeleting(true);
    try {
      await api.deleteSession(id);
      if (selectedId === id) { setSelectedId(undefined); setDetail(null); setMeasurements([]); }
      await refresh();
      setPendingDelete(null);
      toast.show("Sesi berhasil dihapus.", "success");
    } catch (e) {
      toast.show("Gagal menghapus: " + String(e), "error");
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <div className="h-full overflow-y-auto p-4 md:p-6"><p className="text-slate-500">Memuat...</p></div>;

  if (sessions.length === 0) {
    return (
      <div className="h-full overflow-y-auto p-4 md:p-6">
        <div className="card text-center text-slate-500 max-w-2xl mx-auto">
          <p className="mb-2">Belum ada sesi rekaman.</p>
           <Link href="/" className="text-brand-dark hover:underline">Mulai di Dashboard →</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4 md:p-6">
      <div className="space-y-5 max-w-6xl mx-auto">
      <div className="card">
        <div className="card-title">Riwayat Sesi</div>
        <SessionTable sessions={sessions} selectedId={selectedId} onSelect={setSelectedId} onDelete={(id) => { setPendingDelete(id); }} />
      </div>

      {detail && (
        <>
          <div className="card">
            <div className="flex items-center justify-between">
              <div className="card-title mb-0">Ringkasan: {detail.name}</div>
              <div className="flex gap-2">
                <a href={api.exportCsvUrl(detail.id)} download className="btn-muted">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4 M7 10l5 5 5-5 M12 15V3" /></svg>
                  CSV
                </a>
                <a href={api.exportPdfUrl(detail.id)} download className="btn-primary">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z M14 2v6h6 M9 13h6 M9 17h4" /></svg>
                  PDF
                </a>
              </div>
            </div>
            {detail.summary ? (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-4">
                <Stat label="Total Frame" value={detail.summary.frames} />
                <Stat label="Avg Coverage %" value={(detail.summary.avg_coverage_pct ?? 0).toFixed(2)} accent />
                <Stat label="Avg FG Area %" value={detail.summary.avg_fg_area_pct.toFixed(2)} />
                <Stat label="Max Stone" value={detail.summary.max_stone_count} />
                <Stat label="Avg FPS" value={detail.summary.avg_fps.toFixed(1)} />
              </div>
            ) : <p className="text-slate-500 text-sm mt-2">Tidak ada ringkasan.</p>}
          </div>

          {measurements.length > 0 && (
            <div className="card">
              <div className="card-title flex items-center gap-3">
                Tren Coverage % &amp; Stone Count
                <span className="flex items-center gap-1 text-[11px] font-normal text-slate-500"><span className="inline-block w-3 h-3 rounded-sm" style={{ background: "#F47A20" }} /> Coverage %</span>
                <span className="flex items-center gap-1 text-[11px] font-normal text-slate-500"><span className="inline-block w-3 h-3 rounded-sm" style={{ background: "#0ea5e9" }} /> Stone</span>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={measurements} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="covFillH" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#F47A20" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#F47A20" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="frame_idx" tick={{ fontSize: 11, fill: "#94a3b8" }} />
                  <YAxis yAxisId="left" tick={{ fontSize: 11, fill: "#94a3b8" }} unit="%" />
                  <YAxis yAxisId="right" orientation="right" allowDecimals={false} tick={{ fontSize: 11, fill: "#94a3b8" }} />
                  <Tooltip content={<HistChartTip />} />
                  <Area yAxisId="left" type="monotone" dataKey="coverage_pct" stroke="#F47A20" strokeWidth={2} fill="url(#covFillH)" name="Coverage %" />
                  <Line yAxisId="right" type="monotone" dataKey="stone_count" stroke="#0ea5e9" strokeWidth={2} dot={false} name="Stone" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
      </div>

      <ConfirmModal
        open={pendingDelete != null}
        title="Hapus Sesi?"
        message="Sesi ini beserta seluruh data pengukuran, file video, dan CSV akan dihapus permanen. Tindakan ini tidak dapat dibatalkan."
        confirmLabel="Ya, Hapus"
        cancelLabel="Batal"
        danger
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => { if (!deleting) { setPendingDelete(null); } }}
      />
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-lg font-semibold ${accent ? "text-brand-dark" : "text-slate-800 dark:text-slate-100"}`}>{String(value)}</p>
    </div>
  );
}

interface TipPayload { dataKey: string; value: number; payload: Measurement }
function HistChartTip({ active, label, payload }: { active?: boolean; label?: number | string; payload?: TipPayload[] }) {
  if (!active || !payload?.length) return null;
  const m = payload[0].payload;
  const cov = m.coverage_pct ?? m.fg_area_pct ?? 0;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-card dark:bg-slate-800 dark:border-slate-700">
      <div className="text-slate-500 mb-1">Frame <span className="font-semibold text-slate-700 dark:text-slate-200">#{label}</span></div>
      <div className="flex items-center gap-1.5">
        <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: "#F47A20" }} />
        <span className="text-slate-500">Coverage</span>
        <span className="font-semibold text-brand-dark ml-auto">{cov.toFixed(2)}%</span>
      </div>
      <div className="flex items-center gap-1.5 mt-0.5">
        <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: "#0ea5e9" }} />
        <span className="text-slate-500">Jumlah stone</span>
        <span className="font-semibold text-sky-600 ml-auto">{m.stone_count}</span>
      </div>
    </div>
  );
}
