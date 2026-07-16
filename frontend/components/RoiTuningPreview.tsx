"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  imageUrl: string | null;   // rectified ROI image (data URL), 640x224
  maskUrl: string | null;    // binary mask PNG (data URL), grayscale 0/255
  nativeWidth: number;       // 640
  nativeHeight: number;      // 224
  cellPx: number;            // grid cell size
  occFraction: number;       // occupancy threshold (tau)
  showMask?: boolean;
  showGrid?: boolean;
  onResult?: (r: { coveragePct: number; occupied: number; total: number; cols: number; rows: number }) => void;
}

/**
 * Interactive grid-quadrat visualiser. Draws the rectified ROI, the detection
 * mask (red), the grid, and highlights "occupied" cells — recomputing coverage%
 * CLIENT-SIDE (same formula as the backend) as the user drags the cell-size and
 * occupancy sliders. This makes it obvious what each slider does and why the
 * percentage depends on stone size relative to the cell.
 */
export default function RoiTuningPreview({
  imageUrl, maskUrl, nativeWidth, nativeHeight, cellPx, occFraction,
  showMask = true, showGrid = true, onResult,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const fgRef = useRef<Uint8Array | null>(null);   // native-res foreground (1/0)
  const tintRef = useRef<HTMLCanvasElement | null>(null); // red-tinted mask overlay
  const [ready, setReady] = useState(0);           // bump to trigger redraw
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;

  // Load rectified image.
  useEffect(() => {
    if (!imageUrl) { imgRef.current = null; setReady((r) => r + 1); return; }
    const img = new Image();
    img.onload = () => { imgRef.current = img; setReady((r) => r + 1); };
    img.src = imageUrl;
  }, [imageUrl]);

  // Load mask → extract foreground array + build red-tinted overlay canvas.
  useEffect(() => {
    if (!maskUrl) { fgRef.current = null; tintRef.current = null; setReady((r) => r + 1); return; }
    const img = new Image();
    img.onload = () => {
      const off = document.createElement("canvas");
      off.width = nativeWidth; off.height = nativeHeight;
      const octx = off.getContext("2d");
      if (!octx) return;
      octx.drawImage(img, 0, 0, nativeWidth, nativeHeight);
      const data = octx.getImageData(0, 0, nativeWidth, nativeHeight).data;
      const fg = new Uint8Array(nativeWidth * nativeHeight);
      // Build a red-tinted overlay at the same time.
      const tint = document.createElement("canvas");
      tint.width = nativeWidth; tint.height = nativeHeight;
      const tctx = tint.getContext("2d");
      const tImg = tctx!.createImageData(nativeWidth, nativeHeight);
      for (let i = 0; i < fg.length; i++) {
        const on = data[i * 4] > 127 ? 1 : 0;
        fg[i] = on;
        if (on) {
          tImg.data[i * 4] = 248; tImg.data[i * 4 + 1] = 113; tImg.data[i * 4 + 2] = 113; tImg.data[i * 4 + 3] = 150;
        }
      }
      tctx!.putImageData(tImg, 0, 0);
      fgRef.current = fg;
      tintRef.current = tint;
      setReady((r) => r + 1);
    };
    img.src = maskUrl;
  }, [maskUrl, nativeWidth, nativeHeight]);

  // Draw whenever inputs change (and on resize).
  useEffect(() => {
    const draw = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const cw = canvas.clientWidth || nativeWidth;
      const ch = Math.round(cw * (nativeHeight / nativeWidth));
      if (canvas.width !== cw || canvas.height !== ch) { canvas.width = cw; canvas.height = ch; }
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, cw, ch);

      // Base rectified image (or neutral background).
      if (imgRef.current) ctx.drawImage(imgRef.current, 0, 0, cw, ch);
      else { ctx.fillStyle = "#0f172a"; ctx.fillRect(0, 0, cw, ch); }

      const sx = cw / nativeWidth, sy = ch / nativeHeight;

      // Mask overlay (red).
      if (showMask && tintRef.current) {
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(tintRef.current, 0, 0, cw, ch);
      }

      const cell = Math.max(1, Math.floor(cellPx));
      const cols = Math.floor(nativeWidth / cell);
      const rows = Math.floor(nativeHeight / cell);
      let occupied = 0;
      const total = cols * rows;

      // Compute & highlight occupied cells from the native foreground array.
      const fg = fgRef.current;
      if (fg && total > 0) {
        const minPx = Math.max(1, Math.floor(occFraction * cell * cell));
        for (let r = 0; r < rows; r++) {
          for (let c = 0; c < cols; c++) {
            let count = 0;
            const x0 = c * cell, y0 = r * cell;
            for (let yy = 0; yy < cell; yy++) {
              const base = (y0 + yy) * nativeWidth + x0;
              for (let xx = 0; xx < cell; xx++) count += fg[base + xx];
            }
            if (count >= minPx) {
              occupied++;
              ctx.fillStyle = "rgba(244,122,32,0.45)";
              ctx.fillRect(x0 * sx, y0 * sy, cell * sx, cell * sy);
            }
          }
        }
      }

      // Grid lines.
      if (showGrid && total > 0) {
        ctx.strokeStyle = "rgba(255,255,255,0.35)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let c = 0; c <= cols; c++) { const X = Math.round(c * cell * sx) + 0.5; ctx.moveTo(X, 0); ctx.lineTo(X, rows * cell * sy); }
        for (let r = 0; r <= rows; r++) { const Y = Math.round(r * cell * sy) + 0.5; ctx.moveTo(0, Y); ctx.lineTo(cols * cell * sx, Y); }
        ctx.stroke();
      }

      const coveragePct = total > 0 ? (occupied / total) * 100 : 0;
      onResultRef.current?.({ coveragePct, occupied, total, cols, rows });
    };

    draw();
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, [ready, cellPx, occFraction, showMask, showGrid, nativeWidth, nativeHeight]);

  return (
    <div className="w-full rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700 bg-slate-900">
      <canvas ref={canvasRef} className="block w-full" style={{ aspectRatio: `${nativeWidth} / ${nativeHeight}` }} />
    </div>
  );
}
