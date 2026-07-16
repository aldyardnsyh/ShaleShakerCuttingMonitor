"use client";

import { useEffect, useRef, useCallback } from "react";
import { TrackFrame, Roi } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  videoUrl: string;
  frames: TrackFrame[];
  roi: Roi;
  naturalWidth: number;
  naturalHeight: number;
  currentTime: number;   // playhead time of the main live video (for real-time sync)
}

/** Zoomed-in view of the ROI crop with live detection mask, over a blurred backdrop. */
export default function DetectionPreviewModal({ open, onClose, videoUrl, frames, roi, naturalWidth, naturalHeight, currentTime }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const framesRef = useRef<TrackFrame[]>(frames);
  const timeRef = useRef<number>(currentTime);
  framesRef.current = frames;
  timeRef.current = currentTime;

  // ROI bounding box (+padding) in natural coords.
  const xs = roi.map((p) => p[0]);
  const ys = roi.map((p) => p[1]);
  const pad = 12;
  const bx = Math.max(0, Math.min(...xs) - pad);
  const by = Math.max(0, Math.min(...ys) - pad);
  const bw = Math.min(naturalWidth, Math.max(...xs) + pad) - bx;
  const bh = Math.min(naturalHeight, Math.max(...ys) + pad) - by;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    const findIdx = (arr: TrackFrame[], cur: number) => {
      let lo = 0, hi = arr.length - 1, ans = -1;
      while (lo <= hi) { const m = (lo + hi) >> 1; if (arr[m].t <= cur) { ans = m; lo = m + 1; } else hi = m - 1; }
      return ans;
    };

    const draw = () => {
      // Keep the hidden video seeked to the MAIN live playhead so the preview
      // reflects the exact frame being detected in real time (not an independent loop).
      const head = timeRef.current;
      if (video.readyState >= 1 && Math.abs(video.currentTime - head) > 0.08) {
        try { video.currentTime = head; } catch { /* ignore seek errors */ }
      }

      const cw = canvas.clientWidth, ch = canvas.clientHeight;
      if (cw && ch && (canvas.width !== cw || canvas.height !== ch)) { canvas.width = cw; canvas.height = ch; }
      const ctx = canvas.getContext("2d");
      if (ctx && video.videoWidth) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        // Draw current video frame cropped to ROI region, scaled up to fill canvas
        ctx.drawImage(video, bx, by, bw, bh, 0, 0, canvas.width, canvas.height);
        const sx = canvas.width / bw, sy = canvas.height / bh;
        const arr = framesRef.current;
        const di = findIdx(arr, head);
        if (di >= 0) {
          const det = arr[di];
          ctx.fillStyle = "rgba(244,122,32,0.40)";
          ctx.strokeStyle = "rgba(244,122,32,0.95)";
          ctx.lineWidth = 1.5;
          for (const b of det.blobs || []) {
            if (b.poly.length < 3) continue;
            ctx.beginPath();
            b.poly.forEach((pt, i) => {
              const X = (pt[0] - bx) * sx, Y = (pt[1] - by) * sy;
              i === 0 ? ctx.moveTo(X, Y) : ctx.lineTo(X, Y);
            });
            ctx.closePath(); ctx.fill(); ctx.stroke();
          }
        }
      }
      rafRef.current = requestAnimationFrame(draw);
    };
    rafRef.current = requestAnimationFrame(draw);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [open, bx, by, bw, bh]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-md" onClick={onClose} />
      <div className="relative z-10 w-full max-w-3xl rounded-2xl bg-white dark:bg-slate-800 shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200 dark:border-slate-700">
          <div>
            <h3 className="font-semibold text-slate-800 dark:text-slate-100">Preview Area Deteksi (ROI zoom)</h3>
            <p className="text-xs text-slate-500">Area cropping ROI ter-zoom dengan deteksi berjalan</p>
          </div>
          <button onClick={onClose} className="grid h-11 w-11 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700" aria-label="Tutup">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </div>
        <div className="p-4">
          <div className="relative w-full bg-black rounded-lg overflow-hidden" style={{ aspectRatio: `${bw} / ${bh}` }}>
            <video ref={videoRef} src={videoUrl} muted playsInline preload="auto" className="hidden" />
            <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
          </div>
          <p className="text-[11px] text-slate-500 mt-2">Tekan area gelap di luar kartu atau tombol X untuk menutup.</p>
        </div>
      </div>
    </div>
  );
}
