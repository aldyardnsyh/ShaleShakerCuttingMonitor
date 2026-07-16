"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, Roi, TrackFrame, SourceVideo } from "@/lib/api";
import { ActiveConfig, loadConfig, saveConfig, setLastSession, setLastFrame, DEFAULT_ROI } from "@/lib/config";
import { extractFirstFrame, ExtractedFrame } from "@/lib/frame";
import { wsUrl, FramePayload } from "@/lib/ws";
import { useToast } from "@/components/Toast";

export type Phase = "setup" | "live";

interface Stats { t: number; coverage_pct: number; fg_area_pct: number; stone_count: number; playbackFps: number; playing: boolean }
interface Progress { frames: number; coverage: number; stones: number; detectFps: number }

interface Ctx {
  config: ActiveConfig;
  refreshConfig: () => void;
  fileName: string | null;
  objUrl: string | null;
  frame: ExtractedFrame | null;
  roi: Roi;
  setRoi: (r: Roi) => void;
  name: string;
  setName: (n: string) => void;
  phase: Phase;
  sessionId: number | null;
  liveFrames: TrackFrame[];
  stats: Stats;
  setStats: (s: Stats) => void;
  progress: Progress;
  busy: boolean;
  error: string | null;
  paused: boolean;
  stopped: boolean;
  detectionDone: boolean;
  sourceVideos: SourceVideo[];
  loadSourceVideos: () => Promise<void>;
  pickSourceVideo: (name: string) => Promise<void>;
  subscribeLive: () => void;
  unsubscribeLive: () => void;
  togglePause: () => void;
  replay: () => void;
  pickFile: (f: File | null) => Promise<void>;
  start: () => Promise<void>;
  stop: () => Promise<void>;
  reset: () => void;
}

const DashboardCtx = createContext<Ctx | null>(null);

export function useDashboard(): Ctx {
  const c = useContext(DashboardCtx);
  if (!c) throw new Error("useDashboard must be used within DashboardProvider");
  return c;
}

export function DashboardProvider({ children }: { children: React.ReactNode }) {
  const toast = useToast();
  const [config, setConfig] = useState<ActiveConfig>(() => loadConfig());
  const [fileName, setFileName] = useState<string | null>(null);
  const [objUrl, setObjUrl] = useState<string | null>(null);
  const [frame, setFrame] = useState<ExtractedFrame | null>(null);
  const [roi, setRoi] = useState<Roi>(() => loadConfig().roi);
  const [name, setName] = useState(() => `Sesi ${new Date().toLocaleString("id-ID")}`);
  const [phase, setPhase] = useState<Phase>("setup");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [liveFrames, setLiveFrames] = useState<TrackFrame[]>([]);
  const [stats, setStats] = useState<Stats>({ t: 0, coverage_pct: 0, fg_area_pct: 0, stone_count: 0, playbackFps: 0, playing: false });
  const [progress, setProgress] = useState<Progress>({ frames: 0, coverage: 0, stones: 0, detectFps: 0 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [detectionDone, setDetectionDone] = useState(false);
  const [sourceVideos, setSourceVideos] = useState<SourceVideo[]>([]);

  const fileRef = useRef<File | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const sessRef = useRef<number | null>(null);
  // Buffer incoming WS frames in refs and flush to React state on a timer.
  // This keeps per-frame work O(1) and limits re-renders to ~6/sec, so the UI
  // (and tab navigation) stays smooth even while detection streams rapidly.
  const framesBufRef = useRef<TrackFrame[]>([]);
  const progressBufRef = useRef<Progress>({ frames: 0, coverage: 0, stones: 0, detectFps: 0 });
  const flushTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const dirtyRef = useRef(false);
  const liveConsumerRef = useRef(0);

  const subscribeLive = () => { liveConsumerRef.current++; };
  const unsubscribeLive = () => { liveConsumerRef.current = Math.max(0, liveConsumerRef.current - 1); };

  const stopFlush = () => {
    if (flushTimerRef.current) { clearInterval(flushTimerRef.current); flushTimerRef.current = null; }
  };
  const flushNow = () => {
    if (!dirtyRef.current || liveConsumerRef.current === 0) return;
    dirtyRef.current = false;
    // Truncate buffer to last 300 frames to keep state updates cheap.
    const buf = framesBufRef.current;
    const slice = buf.length > 300 ? buf.slice(buf.length - 300) : buf.slice();
    setLiveFrames(slice);
    setProgress({ ...progressBufRef.current });
  };
  const startFlush = () => {
    stopFlush();
    flushTimerRef.current = setInterval(flushNow, 500);
  };

  useEffect(() => {
    return () => { wsRef.current?.close(); stopFlush(); };
  }, []);

  const refreshConfig = () => {
    const c = loadConfig();
    setConfig(c);
    // keep current drawn ROI if a frame is loaded, else adopt config ROI
    if (!frame) setRoi(c.roi);
  };

  const pickFile = async (f: File | null) => {
    setError(null);
    fileRef.current = f;
    setFileName(f?.name ?? null);
    setFrame(null);
    if (objUrl) { URL.revokeObjectURL(objUrl); }
    setObjUrl(f ? URL.createObjectURL(f) : null);
    if (!f) return;
    try {
      const fr = await extractFirstFrame(f);
      setFrame(fr);
      setLastFrame({ dataUrl: fr.dataUrl, width: fr.width, height: fr.height });
      // New video → reset ROI to default, CLAMPED to this video's real
      // resolution so no point/line can ever start outside the frame.
      const cx = (v: number) => Math.max(0, Math.min(fr.width, v));
      const cy = (v: number) => Math.max(0, Math.min(fr.height, v));
      const resetRoi = DEFAULT_ROI.map((p) => [cx(p[0]), cy(p[1])]) as Roi;
      setRoi(resetRoi);
      const resetCfg = { ...loadConfig(), roi: resetRoi };
      saveConfig(resetCfg);
      setConfig(resetCfg);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.show(msg, "error");
    }
  };

  const updateRoi = (r: Roi) => {
    setRoi(r);
    const updated = { ...loadConfig(), roi: r };
    saveConfig(updated);
    setConfig(updated);
  };

  const start = async () => {
    const f = fileRef.current;
    if (!f) return;
    const cfg = loadConfig();
    setError(null);
    setBusy(true);
    // Stop any previous running session first (cancel + discard).
    const prev = sessRef.current;
    if (prev != null) {
      try { await api.stopSession(prev); } catch { /* ignore */ }
    }
    wsRef.current?.close();
    stopFlush();
    framesBufRef.current = [];
    progressBufRef.current = { frames: 0, coverage: 0, stones: 0, detectFps: 0 };
    dirtyRef.current = false;
    setLiveFrames([]);
    setProgress({ frames: 0, coverage: 0, stones: 0, detectFps: 0 });
    setStats({ t: 0, coverage_pct: 0, fg_area_pct: 0, stone_count: 0, playbackFps: 0, playing: false });
    setPaused(false);
    setStopped(false);
    setDetectionDone(false);
    try {
      const session = await api.createSession({
        name,
        model: cfg.model,
        threshold: cfg.threshold,
        roi_json: roi,
        stride: cfg.stride,
        grid_cell_px: cfg.grid_cell_px,
        grid_occ_fraction: cfg.grid_occ_fraction,
        refine_edges: cfg.refine_edges,
      });
      sessRef.current = session.id;
      setSessionId(session.id);
      await api.uploadVideo(session.id, f);
      setLastSession(session.id);
      setPhase("live");      // video starts playing immediately (local objUrl)
      setBusy(false);
      startFlush();

      const ws = new WebSocket(wsUrl(`/ws/sessions/${session.id}`));
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        const msg: FramePayload = JSON.parse(ev.data);
        if (msg.done) {
          flushNow();
          stopFlush();
          setDetectionDone(true);
          ws.close();
          toast.show(`Deteksi selesai. ${progressBufRef.current.frames} frame dianalisis.`, "success");
          return;
        }
        const tf: TrackFrame = {
          frame_idx: msg.frame_idx,
          t: msg.t ?? 0,
          ts: msg.server_time,
          fg_area_pct: msg.fg_area_pct,
          coverage_pct: msg.coverage_pct,
          stone_count: msg.stone_count,
          blobs: msg.blobs ?? [],
        };
        // O(1) buffer push; flushed to state on the timer (no per-frame re-render).
        framesBufRef.current.push(tf);
        progressBufRef.current = {
          frames: progressBufRef.current.frames + 1,
          coverage: msg.coverage_pct ?? msg.fg_area_pct,
          stones: msg.stone_count,
          detectFps: msg.fps,
        };
        dirtyRef.current = true;
      };
      ws.onerror = () => { const msg = "Koneksi deteksi terputus."; setError(msg); toast.show(msg, "error"); };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.show(msg, "error");
      setBusy(false);
      setPhase("setup");
    }
  };

  // Pause/resume: pause the VIDEO and also tell the backend to pause detection
  // (paused video == paused detection, no background CPU/stream churn).
  const togglePause = () => {
    if (stopped) return;
    setPaused((p) => {
      const next = !p;
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        try { ws.send(JSON.stringify({ action: next ? "pause" : "resume" })); } catch { /* ignore */ }
      }
      return next;
    });
  };

  const stop = async () => {
    const id = sessRef.current;
    if (id != null) { try { await api.stopSession(id); } catch { /* ignore */ } }
    wsRef.current?.close();
    flushNow();
    stopFlush();
    // Halt detection but STAY on the live view (frozen). The Pause button
    // becomes disabled; use "Sesi baru" to return to setup.
    setStopped(true);
    setPaused(true);
    setDetectionDone(true);
  };

  // Replay the buffered frames from the start (frame-accurate). Detection is
  // already finished, so this just resets playback (no backend involved).
  const replay = () => {
    setPaused(false);
  };

  const reset = () => {
    wsRef.current?.close();
    stopFlush();
    framesBufRef.current = [];
    progressBufRef.current = { frames: 0, coverage: 0, stones: 0, detectFps: 0 };
    dirtyRef.current = false;
    setLiveFrames([]);
    setSessionId(null);
    sessRef.current = null;
    setPhase("setup");
    setProgress({ frames: 0, coverage: 0, stones: 0, detectFps: 0 });
    setStats({ t: 0, coverage_pct: 0, fg_area_pct: 0, stone_count: 0, playbackFps: 0, playing: false });
    setPaused(false);
    setStopped(false);
    setDetectionDone(false);
    setName(`Sesi ${new Date().toLocaleString("id-ID")}`);
  };

  const loadSourceVideos = async () => {
    try {
      const res = await api.listSourceVideos();
      setSourceVideos(res.videos);
    } catch {
      setSourceVideos([]);
    }
  };

  const pickSourceVideo = async (name: string) => {
    setError(null);
    try {
      const res = await fetch(api.sourceVideoUrl(name));
      if (!res.ok) throw new Error(`Gagal memuat video sumber: ${res.status}`);
      const blob = await res.blob();
      const f = new File([blob], name, { type: blob.type || "video/mp4" });
      await pickFile(f);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.show(msg, "error");
    }
  };

  const value: Ctx = {
    config, refreshConfig, fileName, objUrl, frame, roi, setRoi: updateRoi,
    name, setName, phase, sessionId, liveFrames, stats, setStats, progress,
    busy, error, paused, stopped, detectionDone, sourceVideos, loadSourceVideos, pickSourceVideo,
    subscribeLive, unsubscribeLive,
    togglePause, replay, pickFile, start, stop, reset,
  };
  return <DashboardCtx.Provider value={value}>{children}</DashboardCtx.Provider>;
}
