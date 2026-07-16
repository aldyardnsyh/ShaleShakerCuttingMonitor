"use client";

import { ModelInfo } from "@/lib/api";
import InfoTip from "@/components/InfoTip";

interface ControlsPanelProps {
  models: ModelInfo[];
  model: string;
  threshold: number;
  stride: number;
  onChange: (p: { model?: string; threshold?: number; stride?: number }) => void;
}

export default function ControlsPanel({ models, model, threshold, stride, onChange }: ControlsPanelProps) {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-xs font-medium text-slate-500 mb-1 flex items-center gap-1.5">
          Model
          <InfoTip text={
            <>Arsitektur segmentasi yang dipakai. <b>MobileViT</b> = paling akurat tapi lebih berat di CPU; <b>BiSeNet v2</b> = lebih ringan & cepat. Mengganti model otomatis menyetel threshold default-nya.</>
          } />
        </label>
        <select className="input" value={model} onChange={(e) => onChange({ model: e.target.value })}>
          {models.map((m) => (
            <option key={m.name} value={m.name}>{m.display_name}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-xs font-medium text-slate-500 mb-1 flex items-center gap-1.5">
          Threshold: <span className="text-brand-dark font-semibold">{threshold.toFixed(2)}</span>
          <InfoTip text={
            <>Ambang keyakinan model untuk menandai sebuah piksel sebagai <b>cutting</b>. <b>Lebih rendah</b> → mask lebih luas (lebih sensitif, bisa lebih berisik). <b>Lebih tinggi</b> → mask lebih ketat (hanya area yang sangat yakin). Lihat efeknya langsung pada pratinjau mask di bawah.</>
          } />
        </label>
        <input type="range" min={0} max={1} step={0.01} value={threshold}
          onChange={(e) => onChange({ threshold: parseFloat(e.target.value) })}
          className="w-full accent-brand" />
        <div className="flex justify-between text-[10px] text-slate-500 mt-0.5">
          <span>0 · sensitif</span><span>1 · ketat</span>
        </div>
      </div>

      <div>
        <label className="text-xs font-medium text-slate-500 mb-1 flex items-center gap-1.5">
          Stride
          <InfoTip text={
            <>Inferensi berat dijalankan tiap <b>N frame</b> (frame di antaranya dilewati, tampilan tetap mulus). <b>Stride besar</b> = jauh lebih cepat di CPU, tapi gerakan antar-deteksi lebih jauh sehingga tracking kurang presisi. <b>Stride kecil (1–3)</b> = paling akurat. Ini pengungkit kecepatan paling efektif.</>
          } />
        </label>
        <input type="number" min={1} max={30} value={stride}
          onChange={(e) => onChange({ stride: Math.max(1, Math.min(30, parseInt(e.target.value) || 1)) })}
          className="input w-28" />
      </div>
    </div>
  );
}
