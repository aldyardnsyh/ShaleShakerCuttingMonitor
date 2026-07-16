"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ModelInfo } from "@/lib/api";
import { ActiveConfig, loadConfig, saveConfig, getLastFrame } from "@/lib/config";
import { dataUrlToFile } from "@/lib/frame";
import ControlsPanel from "@/components/ControlsPanel";
import InfoTip from "@/components/InfoTip";
import RoiTuningPreview from "@/components/RoiTuningPreview";
import { useToast } from "@/components/Toast";

const SPEED_PRESETS = [
  { label: "Akurat", v: 1 },
  { label: "Seimbang", v: 3 },
  { label: "Cepat", v: 6 },
  { label: "Turbo", v: 10 },
];

interface Analyze { image: string; mask: string; fgPct: number; width: number; height: number }

export default function SettingsPage() {
  const [config, setConfig] = useState<ActiveConfig | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  // Live tuning preview state.
  const [analyze, setAnalyze] = useState<Analyze | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [hasFrame, setHasFrame] = useState(false);
  const [cov, setCov] = useState<{ coveragePct: number; occupied: number; total: number; cols: number; rows: number } | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setConfig(loadConfig());
    setHasFrame(!!getLastFrame());
    api.listModels().then((r) => setModels(r.models)).catch(() => setModels([]));
  }, []);

  const update = (patch: Partial<ActiveConfig>) => setConfig((c) => (c ? { ...c, ...patch } : c));

  const onControls = (p: { model?: string; threshold?: number; stride?: number }) => {
    if (p.model) {
      const m = models.find((x) => x.name === p.model);
      update({ model: p.model, ...(m ? { threshold: m.fg_threshold } : {}) });
    } else update(p);
  };

  const save = () => {
    if (!config) return;
    saveConfig(config);
    toast.show("Konfigurasi tersimpan.", "success");
  };

  // Best-known configuration per model (from troubleshooting). Each preset sets
  // model + threshold + grid + occupancy + stride together.
  const PRESETS: Record<string, { threshold: number; grid_cell_px: number; grid_occ_fraction: number; stride: number; label: string }> = {
    mobilevit: { threshold: 0.15, grid_cell_px: 23, grid_occ_fraction: 0.01, stride: 3, label: "MobileViT (akurat)" },
    bisenetv2: { threshold: 0.20, grid_cell_px: 20, grid_occ_fraction: 0.03, stride: 3, label: "BiSeNet v2 (cepat)" },
  };

  const applyPreset = (modelName: string) => {
    const p = PRESETS[modelName];
    if (!p) return;
    setConfig((c) => (c ? {
      ...c,
      model: modelName,
      threshold: p.threshold,
      grid_cell_px: p.grid_cell_px,
      grid_occ_fraction: p.grid_occ_fraction,
      stride: p.stride,
      refine_edges: true,
    } : c));
    toast.show(`Setelan terbaik ${p.label} diterapkan, tekan Simpan untuk menyimpan.`, "success");
  };

  // Run backend analyze (rectified image + mask). Re-run when model/threshold/
  // refine/roi change (debounced); cell/occupancy are recomputed client-side.
  const runAnalyze = useCallback(async (cfg: ActiveConfig) => {
    const frame = getLastFrame();
    if (!frame) { setHasFrame(false); return; }
    setHasFrame(true);
    setError(null);
    setAnalyzing(true);
    try {
      const file = await dataUrlToFile(frame.dataUrl, "ref.jpg");
      const res = await api.roiAnalyze(file, cfg.roi, {
        model: cfg.model, threshold: cfg.threshold, refine_edges: cfg.refine_edges,
      });
      setAnalyze({ image: res.image_b64, mask: res.mask_b64, fgPct: res.fg_area_pct, width: res.width, height: res.height });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  }, []);

  // Debounced auto-analyze on model/threshold/refine/roi change.
  useEffect(() => {
    if (!config) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runAnalyze(config), 450);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config?.model, config?.threshold, config?.refine_edges, JSON.stringify(config?.roi)]);

  if (!config) return null;

  return (
    <div className="h-full overflow-y-auto p-4 md:p-6">
      <div className="space-y-5 max-w-6xl mx-auto">
        {/* ===== Controls + Coverage params ===== */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="card">
            <div className="card-title">Model &amp; Deteksi</div>
            <ControlsPanel models={models} model={config.model} threshold={config.threshold}
              stride={config.stride} onChange={onControls} />
          </div>

          <div className="card space-y-4">
            <div className="card-title flex items-center gap-1.5">
              Parameter Coverage (Grid-Kuadrat)
              <InfoTip text={<>Coverage% mengukur <b>sebaran</b> cutting di permukaan: ROI dibagi sel kotak, sel dihitung &quot;terisi&quot; bila cukup banyak piksel cutting di dalamnya. Coverage = sel terisi / total sel × 100.</>} />
            </div>
            <label className="block text-sm">
              <span className="text-slate-500 flex items-center gap-1.5">
                Ukuran sel grid (px): <span className="text-brand-dark font-semibold">{config.grid_cell_px}</span>
                <InfoTip text={<>Besar tiap kotak grid pada ROI ter-rektifikasi (640×224). Idealnya ≈ <b>rata-rata ukuran satu batuan</b>, sehingga 1 batuan ≈ 1 sel. Sel kecil → grid halus; sel besar → 1 batuan kecil bisa mengisi penuh satu sel.</>} />
              </span>
              <input type="range" min={4} max={64} step={1} value={config.grid_cell_px}
                onChange={(e) => update({ grid_cell_px: Number(e.target.value) })} className="mt-1 w-full accent-brand" />
              <div className="flex justify-between text-[10px] text-slate-500"><span>4 · halus</span><span>64 · kasar</span></div>
            </label>
            <label className="block text-sm">
              <span className="text-slate-500 flex items-center gap-1.5">
                Ambang okupansi sel (τ): <span className="text-brand-dark font-semibold">{config.grid_occ_fraction}</span>
                <InfoTip text={<>Seberapa penuh sebuah sel harus terisi cutting agar dihitung &quot;terisi&quot;. <b>τ rendah</b> → mudah terisi → coverage naik (sensitif). <b>τ tinggi</b> → hanya sel padat dihitung → coverage turun (konservatif).</>} />
              </span>
              <input type="range" min={0.01} max={0.5} step={0.01} value={config.grid_occ_fraction}
                onChange={(e) => update({ grid_occ_fraction: Number(e.target.value) })} className="mt-1 w-full accent-brand" />
              <div className="flex justify-between text-[10px] text-slate-500"><span>0.01 · sensitif</span><span>0.5 · ketat</span></div>
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={config.refine_edges}
                onChange={(e) => update({ refine_edges: e.target.checked })} className="w-4 h-4 accent-brand" />
              <span className="text-slate-700 dark:text-slate-200 flex items-center gap-1.5">
                Penghalusan tepi mask (morfologi + Canny)
                <InfoTip text={<>Membersihkan mask dengan operasi morfologi + deteksi tepi Canny, membuang blob kecil tanpa tepi nyata. Aktifkan untuk mask yang lebih rapi.</>} />
              </span>
            </label>
          </div>
        </div>

        {/* ===== Interactive tuning preview ===== */}
        <div className="card">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="card-title mb-0 flex items-center gap-1.5">
              Pratinjau &amp; Penyetelan Langsung
              <InfoTip text={<>Visualisasi memakai frame referensi dari video terakhir. Mask merah = hasil deteksi (dipengaruhi model &amp; threshold). Kotak oranye = sel yang dihitung &quot;terisi&quot; (dipengaruhi ukuran sel &amp; τ). Geser slider dan lihat perubahannya seketika.</>} />
            </div>
            <button onClick={() => runAnalyze(config)} disabled={analyzing || !hasFrame} className="btn-muted text-sm">
              {analyzing ? "Menganalisis…" : "↻ Analisis ulang"}
            </button>
          </div>

          {!hasFrame ? (
            <div className="mt-4 rounded-lg border-2 border-dashed border-slate-300 dark:border-slate-600 p-8 text-center text-slate-500 text-sm">
              Belum ada frame referensi. Unggah video di{" "}
              <Link href="/" className="text-brand hover:underline">Dashboard</Link>{" "}terlebih dahulu, lalu kembali ke sini.
            </div>
          ) : (
            <div className="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2">
                <RoiTuningPreview
                  imageUrl={analyze?.image ?? null}
                  maskUrl={analyze?.mask ?? null}
                  nativeWidth={analyze?.width ?? 640}
                  nativeHeight={analyze?.height ?? 224}
                  cellPx={config.grid_cell_px}
                  occFraction={config.grid_occ_fraction}
                  onResult={setCov}
                />
                <div className="flex items-center gap-4 mt-2 text-[11px] text-slate-500 flex-wrap">
                  <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm" style={{ background: "rgba(248,113,113,0.6)" }} /> mask deteksi</span>
                  <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm" style={{ background: "rgba(244,122,32,0.55)" }} /> sel terisi</span>
                  <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 border border-white/60" /> grid sel</span>
                </div>
              </div>

              {/* Live readout */}
              <div className="space-y-3">
                <div className="last-value !p-4">
                  <div className="text-xs font-medium text-white/90">Coverage (grid) &middot; live</div>
                  <div className="text-4xl font-extrabold leading-tight mt-1">{(cov?.coveragePct ?? 0).toFixed(1)}%</div>
                  <div className="text-[11px] text-white/80 mt-1">{cov?.occupied ?? 0} / {cov?.total ?? 0} sel terisi</div>
                </div>
                <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-3 text-sm space-y-1.5">
                  <div className="flex justify-between"><span className="text-slate-500">Piksel mentah (fg)</span><span className="font-semibold">{(analyze?.fgPct ?? 0).toFixed(2)}%</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Grid</span><span className="font-medium">{cov?.cols ?? 0} × {cov?.rows ?? 0} = {cov?.total ?? 0} sel</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Sel terisi</span><span className="font-medium">{cov?.occupied ?? 0}</span></div>
                </div>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  <b>Kenapa persentasenya kecil?</b> Karena luas batuan (mask merah) memang kecil dibanding seluruh ROI.
                  Coverage <b>tergantung ukuran batuan relatif terhadap sel</b>: perkecil ukuran sel atau turunkan τ untuk
                  angka yang lebih sensitif, atau samakan ukuran sel dengan footprint batuan agar 1 batuan ≈ 1 sel.
                </p>
              </div>
            </div>
          )}
          {error && <p className="text-rose-600 text-sm mt-2">{error}</p>}
          <div className="font-mono text-[11px] text-slate-500 mt-3">
            ROI: {config.roi.map((p, i) => `${["TL", "TR", "BR", "BL"][i]}(${Math.round(p[0])},${Math.round(p[1])})`).join("  ")}
            <span className="ml-1">· atur 4 titik di <Link href="/" className="text-brand hover:underline">Dashboard</Link></span>
          </div>
        </div>

        {/* ===== Speed / stride ===== */}
        <div className="card">
          <div className="card-title flex items-center gap-1.5">
            Kecepatan Deteksi &amp; Performa
            <InfoTip text={<>Stride = inferensi berat dijalankan tiap N frame. Naikkan untuk near-real-time di CPU; turunkan untuk akurasi tracking maksimal.</>} />
          </div>
          <p className="text-xs text-slate-500 mb-3">
            Aktif: <span className="text-brand-dark font-semibold">{config.stride}</span> (deteksi tiap {config.stride} frame).
          </p>
          <div className="flex flex-wrap gap-2">
            {SPEED_PRESETS.map((o) => (
              <button key={o.v} onClick={() => update({ stride: o.v })}
                className={config.stride === o.v ? "btn-primary" : "btn-muted"}>
                {o.label} ({o.v})
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-500 mt-3">
            Thread ONNX mengikuti jumlah core (env <code>ORT_INTRA_OP_THREADS</code>; VPS 2 vCPU = 2).
          </p>
        </div>

        <div className="card">
          <div className="card-title flex items-center gap-1.5">
            Setelan Terbaik (rekomendasi per model)
            <InfoTip text={<>Nilai hasil troubleshooting yang paling cocok untuk tiap model (threshold, ukuran sel, ambang okupansi), semuanya pada stride 3. Klik salah satu lalu tekan <b>Simpan</b>.</>} />
          </div>
          <div className="flex flex-wrap gap-2 mt-1">
            <button onClick={() => applyPreset("mobilevit")} className="btn-outline inline-flex items-center gap-1.5">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l1.9 5.8H20l-4.9 3.6 1.9 5.8L12 14.6 7 18.2l1.9-5.8L4 8.8h6.1z" /></svg>
              MobileViT &middot; akurat
            </button>
            <button onClick={() => applyPreset("bisenetv2")} className="btn-outline inline-flex items-center gap-1.5">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2L3 14h7l-1 8 10-12h-7z" /></svg>
              BiSeNet v2 &middot; cepat
            </button>
          </div>
          <p className="text-[11px] text-slate-500 mt-2">
            MobileViT: threshold 0.15 · sel 23 px · τ 0.01 · stride 3.&nbsp;&nbsp;
            BiSeNet v2: threshold 0.20 · sel 20 px · τ 0.03 · stride 3.
          </p>
        </div>

        <div className="flex items-center gap-3 pb-2 flex-wrap">
          <button onClick={save} disabled={!config} className="btn-primary disabled:opacity-40">Simpan Konfigurasi</button>
        </div>
      </div>
    </div>
  );
}
