"use client";

import { useEffect, useRef } from "react";
import { TrackFrame, Roi } from "@/lib/api";

interface Props {
  videoUrl: string;
  frames: TrackFrame[];      // sorted by t; grows live during detection
  naturalWidth: number;
  naturalHeight: number;
  roi?: Roi;
  initialTime?: number;      // resume playback clock here on (re)mount
  paused?: boolean;          // controlled pause (persists across tab switches)
  done?: boolean;            // detection finished → replay mode (advance own clock)
  onStats?: (s: { t: number; coverage_pct: number; fg_area_pct: number; stone_count: number; playbackFps: number; playing: boolean }) => void;
  onEnded?: () => void;
}

/**
 * FRAME-ACCURATE live view. Instead of playing the video smoothly and letting
 * the mask trail behind, we drive the <video> to the EXACT time of each
 * analysed frame and draw that frame's mask with NO motion extrapolation. The
 * frame shown therefore always matches its mask (it may look choppy/stepwise,
 * but it is faithful to what was actually analysed — no "lag/fake" feel).
 *
 * - Live (detection ongoing): snap to the newest analysed frame (frontier).
 * - Replay (done): advance an internal clock in real time and snap to the
 *   analysed frame at/just before that clock.
 * Native controls are hidden; play/pause is controlled via `paused`.
 */
export default function TrackedView({
  videoUrl, frames, naturalWidth, naturalHeight, roi = [],
  initialTime = 0, paused = false, done = false, onStats, onEnded,
}: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const framesRef = useRef<TrackFrame[]>(frames);
  const pausedRef = useRef(paused);
  const doneRef = useRef(done);
  const clockRef = useRef<number>(initialTime);     // virtual playback time (s)
  const lastWallRef = useRef<number>(performance.now());
  const fpsRef = useRef<number>(0);
  const endedFiredRef = useRef(false);
  const lastEmitRef = useRef<string>("");

  framesRef.current = frames;
  pausedRef.current = paused;
  doneRef.current = done;

  function findIdx(arr: TrackFrame[], cur: number): number {
    let lo = 0, hi = arr.length - 1, ans = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (arr[mid].t <= cur) { ans = mid; lo = mid + 1; } else { hi = mid - 1; }
    }
    return ans;
  }

  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    // If detection is already finished when (re)mounting (e.g. returning to the
    // Dashboard tab), sit on the FINAL analysed frame (frozen) instead of
    // replaying from 0. Otherwise start at the requested time.
    clockRef.current = doneRef.current ? Number.MAX_SAFE_INTEGER : initialTime;
    lastWallRef.current = performance.now();
    endedFiredRef.current = false;

    const draw = () => {
      const nowW = performance.now();
      const dtWall = (nowW - lastWallRef.current) / 1000;
      lastWallRef.current = nowW;
      if (dtWall > 0) fpsRef.current = 0.85 * fpsRef.current + 0.15 * (1 / dtWall);

      const arr = framesRef.current;
      const frontier = arr.length ? arr[arr.length - 1].t : 0;
      const lastT = frontier;
      const isPaused = pausedRef.current;
      const isDone = doneRef.current;

      // --- Determine the virtual playback clock ---
      let playing: boolean;
      if (!isDone) {
        // Live: always sit on the newest analysed frame.
        clockRef.current = frontier;
        playing = !isPaused;
      } else {
        // Replay: advance in real time, clamp to the last analysed frame.
        if (!isPaused && clockRef.current < lastT) {
          clockRef.current = Math.min(lastT, clockRef.current + dtWall);
        }
        playing = !isPaused && clockRef.current < lastT;
        if (clockRef.current >= lastT - 1e-3 && !endedFiredRef.current && arr.length > 0) {
          endedFiredRef.current = true;
          onEnded?.();
        }
      }

      // Snap to the analysed frame at/just before the clock.
      const di = findIdx(arr, clockRef.current);
      const targetT = di >= 0 ? arr[di].t : 0;
      // Seek the underlying <video> to that exact frame time (frame-accurate).
      if (video.readyState >= 1 && Math.abs(video.currentTime - targetT) > 0.033) {
        try { video.currentTime = targetT; } catch { /* ignore */ }
      }

      // --- Canvas / overlay ---
      const dispW = canvas.clientWidth || video.clientWidth;
      const dispH = canvas.clientHeight || video.clientHeight;
      if (canvas.width !== dispW || canvas.height !== dispH) { canvas.width = dispW; canvas.height = dispH; }
      const ctx = canvas.getContext("2d");
      if (!ctx) { rafRef.current = requestAnimationFrame(draw); return; }
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Letterboxed (object-contain) video rect inside the canvas.
      const vw = video.videoWidth || naturalWidth;
      const vh = video.videoHeight || naturalHeight;
      const va = vw / vh;
      const ca = canvas.width / canvas.height;
      let rW: number, rH: number, offX: number, offY: number;
      if (va > ca) { rW = canvas.width; rH = canvas.width / va; offX = 0; offY = (canvas.height - rH) / 2; }
      else { rH = canvas.height; rW = canvas.height * va; offY = 0; offX = (canvas.width - rW) / 2; }
      const sx = rW / naturalWidth;
      const sy = rH / naturalHeight;

      const hasRoi = roi.length >= 3;
      const roiPath = () => {
        ctx.beginPath();
        roi.forEach((p, i) => { const X = offX + p[0] * sx, Y = offY + p[1] * sy; i === 0 ? ctx.moveTo(X, Y) : ctx.lineTo(X, Y); });
        ctx.closePath();
      };
      if (hasRoi) { ctx.strokeStyle = "rgba(56,189,248,0.9)"; ctx.lineWidth = 2; roiPath(); ctx.stroke(); }

      let curCov = 0, curPct = 0, curStones = 0;
      if (di >= 0) {
        const det = arr[di];
        curCov = det.coverage_pct ?? det.fg_area_pct;
        curPct = det.fg_area_pct;
        curStones = det.stone_count;
        // EXACT mask for this analysed frame — no velocity extrapolation.
        ctx.save();
        if (hasRoi) { roiPath(); ctx.clip(); }
        ctx.fillStyle = "rgba(248,113,113,0.40)";
        ctx.strokeStyle = "rgba(248,113,113,0.95)";
        ctx.lineWidth = 1.5;
        for (const b of det.blobs || []) {
          if (b.poly.length < 3) continue;
          ctx.beginPath();
          for (let i = 0; i < b.poly.length; i++) {
            const X = offX + b.poly[i][0] * sx, Y = offY + b.poly[i][1] * sy;
            i === 0 ? ctx.moveTo(X, Y) : ctx.lineTo(X, Y);
          }
          ctx.closePath(); ctx.fill(); ctx.stroke();
        }
        ctx.restore();
      }

      const payload = {
        t: targetT,
        coverage_pct: curCov,
        fg_area_pct: curPct,
        stone_count: curStones,
        playbackFps: playing ? fpsRef.current : 0,
        playing,
      };
      if (playing) {
        onStats?.(payload);
      } else {
        const sig = `${payload.coverage_pct}|${payload.stone_count}|${payload.t}|0`;
        if (sig !== lastEmitRef.current) { lastEmitRef.current = sig; onStats?.(payload); }
      }
      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoUrl, naturalWidth, naturalHeight]);

  return (
    <div className="relative w-full h-full bg-black rounded-lg overflow-hidden">
      <video
        ref={videoRef}
        src={videoUrl}
        muted
        playsInline
        preload="auto"
        disablePictureInPicture
        controlsList="nodownload noplaybackrate nofullscreen"
        onContextMenu={(e) => e.preventDefault()}
        className="w-full h-full object-contain"
      />
      <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 w-full h-full" />
    </div>
  );
}
