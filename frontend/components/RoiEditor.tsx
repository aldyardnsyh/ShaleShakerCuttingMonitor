"use client";

import { useCallback, useRef, useState } from "react";
import { Roi } from "@/lib/api";

interface RoiEditorProps {
  imageUrl: string | null;
  roi: Roi;
  onChange: (roi: Roi) => void;
  naturalWidth?: number;
  naturalHeight?: number;
}

const LABELS = ["TL", "TR", "BR", "BL"];

export default function RoiEditor({ imageUrl, roi, onChange, naturalWidth, naturalHeight }: RoiEditorProps) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [dragging, setDragging] = useState<number | null>(null);
  const [dragPos, setDragPos] = useState<[number, number] | null>(null);

  const nw = naturalWidth || 1920;
  const nh = naturalHeight || 1080;

  // Convert a pointer position to NATURAL image coordinates using the image's
  // live bounding rect (always correct, even when the layout/size changes).
  const pointerToNatural = useCallback(
    (clientX: number, clientY: number): [number, number] => {
      const el = imgRef.current;
      if (!el) return [0, 0];
      const r = el.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (clientX - r.left) / r.width)) * nw;
      const y = Math.max(0, Math.min(1, (clientY - r.top) / r.height)) * nh;
      return [Math.round(x), Math.round(y)];
    },
    [nw, nh]
  );

  const onMove = useCallback(
    (e: React.PointerEvent) => {
      if (dragging === null) return;
      const next = [...roi] as Roi;
      const newPos = pointerToNatural(e.clientX, e.clientY);
      next[dragging] = newPos;
      onChange(next);
      setDragPos(newPos);
    },
    [dragging, roi, onChange, pointerToNatural]
  );

  if (!imageUrl) {
    return (
      <div className="border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-lg flex items-center justify-center h-56 text-slate-500 text-sm">
        Muat gambar referensi untuk mengedit ROI
      </div>
    );
  }

  // ABSOLUTE BOUNDARY: clamp every point to the image (0..nw, 0..nh) for
  // rendering, so handles and polygon lines can never appear outside the video
  // player area regardless of the stored coordinates or video resolution.
  const cx = (v: number) => Math.max(0, Math.min(nw, v));
  const cy = (v: number) => Math.max(0, Math.min(nh, v));
  const disp = roi.map((p) => [cx(p[0]), cy(p[1])] as [number, number]);
  const polyPts = disp.map((p) => `${p[0]},${p[1]}`).join(" ");

  return (
    <div
      className="relative inline-block select-none w-full touch-none"
      onPointerMove={onMove}
      onPointerUp={() => setDragging(null)}
      onPointerLeave={() => setDragging(null)}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img ref={imgRef} src={imageUrl} alt="Reference" className="block w-full rounded-lg" draggable={false} />

      {/* Polygon overlay in NATURAL coords; browser scales it to the image. */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        viewBox={`0 0 ${nw} ${nh}`}
        preserveAspectRatio="none"
      >
        <polygon points={polyPts} fill="rgba(244,122,32,0.18)" stroke="#F47A20" strokeWidth={2} vectorEffect="non-scaling-stroke" />
      </svg>

      {/* Draggable handles as HTML elements positioned by % (constant pixel size). */}
      {disp.map((p, i) => (
        <div
          key={i}
          onPointerDown={(e) => {
            e.preventDefault();
            (e.target as HTMLElement).setPointerCapture(e.pointerId);
            setDragging(i);
            setDragPos([p[0], p[1]]);
          }}
          className="absolute z-10 h-4 w-4 p-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-brand border-2 border-white shadow cursor-grab active:cursor-grabbing"
          style={{ left: `${(p[0] / nw) * 100}%`, top: `${(p[1] / nh) * 100}%` }}
          aria-label={`Handle ROI ${LABELS[i]}`}
        >
          <span className="absolute left-1/2 -top-5 -translate-x-1/2 text-[10px] font-semibold text-brand-dark bg-white/90 dark:bg-slate-800/90 px-1 rounded">
            {LABELS[i]}
          </span>
        </div>
      ))}

      {/* Drag preview zoom — appears NEAR the dragged point and follows it in
          BOTH axes (background-position), placed toward open space so it never
          covers the handle. */}
      {dragging !== null && dragPos && (() => {
        const Z = 2.6;                 // zoom factor
        const boxW = 188, boxH = 140;  // preview box size (px)
        const bgPosX = boxW / 2 - dragPos[0] * Z;
        const bgPosY = boxH / 2 - dragPos[1] * Z;
        const fx = dragPos[0] / nw;
        const fy = dragPos[1] / nh;
        // Offset toward whichever side has room (away from the point).
        const tx = fx < 0.5 ? "16px" : "calc(-100% - 16px)";
        const ty = fy < 0.5 ? "16px" : "calc(-100% - 16px)";
        return (
          <div
            className="absolute z-40 pointer-events-none"
            style={{ left: `${fx * 100}%`, top: `${fy * 100}%`, transform: `translate(${tx}, ${ty})` }}
          >
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow-2xl border border-slate-200 dark:border-slate-700 p-2">
              <div className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 mb-1 text-center">
                {LABELS[dragging]} · {dragPos[0]}, {dragPos[1]}
              </div>
              <div
                className="rounded overflow-hidden relative bg-slate-100 dark:bg-slate-900"
                style={{
                  width: boxW,
                  height: boxH,
                  backgroundImage: `url(${imageUrl})`,
                  backgroundRepeat: "no-repeat",
                  backgroundSize: `${nw * Z}px ${nh * Z}px`,
                  backgroundPosition: `${bgPosX}px ${bgPosY}px`,
                }}
              >
                <div className="absolute left-1/2 top-0 bottom-0 w-px bg-brand/70 -translate-x-1/2" />
                <div className="absolute top-1/2 left-0 right-0 h-px bg-brand/70 -translate-y-1/2" />
                <div className="absolute left-1/2 top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-brand bg-white/40" />
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
