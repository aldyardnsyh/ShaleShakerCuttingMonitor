"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useDashboard } from "@/components/DashboardContext";
import RoiEditor from "@/components/RoiEditor";
import TrackedView from "@/components/TrackedView";
import TrendChart from "@/components/TrendChart";
import DetectionPreviewModal from "@/components/DetectionPreviewModal";

export default function DashboardPage() {
  const d = useDashboard();
  const [preview, setPreview] = useState(false);
  const lastDetectFps = useRef(0);

  useEffect(() => { d.refreshConfig(); d.loadSourceVideos(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    d.subscribeLive();
    return () => d.unsubscribeLive();
  }, [d]);

  const canStart = !!d.fileName && !!d.frame && d.roi.length === 4 && d.phase === "setup" && !d.busy;

  // All live metrics are driven by the VIDEO PLAYHEAD (d.stats), so they freeze
  // automatically when the video is paused or ended — no more ghost updates from
  // the background detection stream.
  const playing = d.phase === "live" && d.stats.playing;
  const cov = d.phase === "live" ? d.stats.coverage_pct : 0;
  const stones = d.phase === "live" ? d.stats.stone_count : 0;
  const playFps = d.phase === "live" ? d.stats.playbackFps : 0;
  // Detect FPS comes from the backend stream; freeze its last value when not playing.
  if (playing) lastDetectFps.current = d.progress.detectFps;
  const detectFps = playing ? d.progress.detectFps : lastDetectFps.current;

  // Trend only shows detections up to the current playhead → grows with playback
  // and freezes when paused/ended (stays in sync with what is on screen).
  const headT = d.phase === "live" ? d.stats.t : 0;
  const trend = d.liveFrames
    .filter((f) => f.t <= headT + 0.05)
    .slice(-150)
    .map((f) => ({
      idx: f.frame_idx, pct: f.coverage_pct ?? f.fg_area_pct, stone: f.stone_count, ts: f.ts, t: f.t,
    }));
  const shownFrames = d.liveFrames.filter((f) => f.t <= headT + 0.05).length;

  return (
    <div className="h-full flex flex-col overflow-hidden bg-[#f4f5f7] dark:bg-slate-900">
      {/* ===================== SETUP ===================== */}
      {d.phase === "setup" && (
        <div className="flex-1 overflow-auto p-4 md:p-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <div className="lg:col-span-2 card">
              <div className="card-title">1 · Unggah Video &amp; Tentukan Area ROI</div>
              {!d.frame ? (
                <>
                  <label className="min-h-[240px] flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-600 cursor-pointer hover:border-brand transition-colors">
                    <div className="grid h-14 w-14 place-items-center rounded-full bg-brand-light text-brand">
                      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4 M17 8l-5-5-5 5 M12 3v12" /></svg>
                    </div>
                    <div className="text-slate-600 dark:text-slate-300 font-medium">Unggah video terlebih dahulu</div>
                    <div className="text-xs text-slate-500">Klik untuk memilih file video (mp4)</div>
                    <input type="file" accept="video/*" className="hidden" onChange={(e) => d.pickFile(e.target.files?.[0] ?? null)} />
                    {d.fileName && !d.frame && <div className="text-xs text-brand-dark">Membaca frame awal...</div>}
                  </label>
                  {d.sourceVideos.length > 0 && (
                    <div className="mt-3">
                      <div className="text-xs font-medium text-slate-500 mb-2">Atau gunakan video sumber (uji coba):</div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {d.sourceVideos.map((v) => (
                          <button
                            key={v.name}
                            onClick={() => d.pickSourceVideo(v.name)}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm text-slate-700 dark:text-slate-300 hover:border-brand hover:bg-brand-light/50 transition-colors text-left"
                          >
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="23 7 16 12 23 17 23 7" /><rect x="1" y="5" width="15" height="14" rx="2" ry="2" /></svg>
                            <div className="truncate flex-1 min-w-0">
                              <div className="font-medium truncate">{v.name}</div>
                              <div className="text-[11px] text-slate-500">{v.size_mb} MB</div>
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div>
                  <RoiEditor imageUrl={d.frame.dataUrl} roi={d.roi} onChange={d.setRoi} naturalWidth={d.frame.width} naturalHeight={d.frame.height} />
                  <div className="flex items-center justify-between mt-3">
                    <p className="text-xs text-slate-500">Frame awal terbaca ({d.frame.width}×{d.frame.height}). Geser 4 titik (TL, TR, BR, BL).</p>
                    <button onClick={() => d.pickFile(null)} className="text-xs text-brand-dark hover:underline">Ganti video</button>
                  </div>
                </div>
              )}
            </div>

            <div className="card flex flex-col gap-5">
              <div>
                <div className="card-title">2 · Nama Sesi</div>
                <input type="text" className="input" value={d.name} onChange={(e) => d.setName(e.target.value)} />
              </div>
              <div>
                <div className="card-title">Konfigurasi</div>
                <dl className="text-sm space-y-1.5">
                  <div className="flex justify-between"><dt className="text-slate-500">Model</dt><dd className="font-medium">{d.config.model}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-500">Threshold</dt><dd className="font-medium">{d.config.threshold}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-500">Stride</dt><dd className="font-medium">{d.config.stride}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-500">Edge refine</dt><dd className="font-medium">{d.config.refine_edges ? "on" : "off"}</dd></div>
                </dl>
                <Link href="/settings/" className="text-xs text-brand-dark hover:underline">Ubah di Settings →</Link>
              </div>
              <div className="mt-auto">
                <div className="card-title">3 · Jalankan</div>
                <button onClick={d.start} disabled={!canStart} className="btn-primary w-full">
                  {d.busy ? "Menyiapkan…" : "Start Deteksi Live"}
                </button>
                {!canStart && !d.busy && <p className="text-[11px] text-slate-500 mt-2">Lengkapi video + 4 titik ROI untuk mengaktifkan.</p>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ===================== LIVE ===================== */}
      {d.phase === "live" && d.objUrl && d.frame && (
        <div className="flex-1 flex flex-col overflow-hidden p-3 md:p-4 gap-3">
          {/* Top row: video (left) + trend (right) — fills available height */}
          <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-3 gap-3">
            <div className="lg:col-span-2 card p-2 relative flex min-h-0">
              <TrackedView videoUrl={d.objUrl} frames={d.liveFrames}
                naturalWidth={d.frame.width} naturalHeight={d.frame.height} roi={d.roi}
                initialTime={0} paused={d.paused} done={d.detectionDone}
                onStats={d.setStats} onEnded={() => {}} />
            </div>

            <div className="card flex flex-col min-h-0">
              <div className="card-title">Tren Coverage %</div>
              <div className="flex-1 min-h-0">
                <TrendChart data={trend} height="100%" />
              </div>
              <p className="text-[11px] text-slate-500 mt-2">
                {shownFrames} frame · stride {d.config.stride}. Waktu menurun; hover untuk detail.
              </p>
            </div>
          </div>

          {/* Bottom row: session info + controls (left) + Last Value (right) — fixed height */}
          <div className="flex-shrink-0 grid grid-cols-1 lg:grid-cols-3 gap-3">
            <div className="lg:col-span-2 card flex flex-col">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100 truncate">{d.name}</h2>
                  <p className="text-xs text-slate-500">
                    Persentase cutting menutupi area shale shaker
                    {d.stopped
                      ? <span className="text-rose-500 font-medium"> · dihentikan</span>
                      : d.detectionDone
                        ? <span className="text-emerald-600 font-medium"> · selesai &amp; tersimpan</span>
                        : d.paused
                          ? <span className="text-amber-500 font-medium"> · dijeda</span>
                          : null}
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center shrink-0">
                  <div className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5">
                    <div className="text-[10px] text-slate-500">Stone</div>
                    <div className="text-lg font-bold text-slate-800 dark:text-slate-100">{stones}</div>
                  </div>
                  <div className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5">
                    <div className="text-[10px] text-slate-500">Playback FPS</div>
                    <div className="text-lg font-bold text-brand">{playFps.toFixed(0)}</div>
                  </div>
                  <div className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5">
                    <div className="text-[10px] text-slate-500">Detect FPS</div>
                    <div className="text-lg font-bold text-slate-800 dark:text-slate-100">{detectFps.toFixed(1)}</div>
                  </div>
                </div>
              </div>
              <div className="mt-auto pt-3 flex flex-wrap gap-2">
                <button onClick={d.togglePause} disabled={d.stopped || d.detectionDone} className="btn-muted">
                  {d.paused
                    ? (<><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg> Lanjut</>)
                    : (<><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z" /></svg> Jeda</>)}
                </button>
                <button onClick={d.stop} disabled={d.stopped || d.detectionDone} className="btn-danger">■ Stop</button>
                <button onClick={d.reset} className="btn-muted">+ Sesi baru</button>
                <button onClick={() => setPreview(true)} className="btn-outline">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" /><circle cx="12" cy="12" r="3" /></svg>
                  Preview Area Deteksi
                </button>
              </div>
            </div>

            <div className="last-value">
              <div className="text-sm font-medium text-white/90">Last Value</div>
              <div className="text-4xl font-extrabold leading-tight mt-1">{cov.toFixed(0)}%</div>
              <div className="text-xs text-white/80 mt-1">coverage cutting</div>
            </div>
          </div>
        </div>
      )}

      <DetectionPreviewModal
        open={preview && d.phase === "live" && !!d.objUrl && !!d.frame}
        onClose={() => setPreview(false)}
        videoUrl={d.objUrl ?? ""}
        frames={d.liveFrames}
        roi={d.roi}
        naturalWidth={d.frame?.width ?? 1920}
        naturalHeight={d.frame?.height ?? 1080}
        currentTime={d.stats.t}
      />
    </div>
  );
}
