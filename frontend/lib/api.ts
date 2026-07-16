// REST client + shared types. When the frontend is served by the backend
// (production), API_BASE is empty (same origin). For local `next dev`, set
// NEXT_PUBLIC_API_BASE=http://localhost:8000 in frontend/.env.local.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  server_time: string;
  timezone: string;
}

export type Point = [number, number];
export type Roi = Point[]; // 4 points: TL, TR, BR, BL

export interface ModelInfo {
  name: string;
  display_name: string;
  fg_threshold: number;
  input_h: number;
  input_w: number;
}

export interface ModelsResponse {
  models: ModelInfo[];
  default_model: string;
}

export interface Preset {
  id: number;
  name: string;
  roi_json: Roi;
  model: string;
  threshold: number;
  stride: number;
  created_at: string;
}

export interface SessionSummary {
  frames: number;
  avg_fg_area_pct: number;
  avg_coverage_pct?: number;
  max_stone_count: number;
  avg_fps: number;
}

export interface SessionOut {
  id: number;
  name: string;
  source_type: string;
  model: string;
  threshold: number;
  roi_json: Roi;
  stride: number;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  summary?: SessionSummary;
  video_fps?: number | null;
  frame_width?: number | null;
  frame_height?: number | null;
  grid_cell_px?: number | null;
  grid_occ_fraction?: number | null;
  refine_edges?: boolean | null;
}

export interface Track {
  id: number;
  x: number;
  y: number;
  w: number;
  h: number;
  vx: number;
  vy: number;
}

export type Polygon = number[][]; // list of [x, y] in full-frame pixels

export interface Blob {
  poly: Polygon;
  vx: number; // px/sec (Kalman) for motion compensation
  vy: number;
}

export interface TrackFrame {
  frame_idx: number;
  t: number; // seconds into the video
  ts?: string; // server wall-clock time (ISO) at detection
  fg_area_pct: number;
  coverage_pct?: number;
  stone_count: number;
  blobs: Blob[];
}

export interface TracksResponse {
  session_id: number;
  fps: number;
  width: number | null;
  height: number | null;
  stride: number;
  roi: Roi;
  frames: TrackFrame[];
}

export interface Measurement {
  frame_idx: number;
  ts: string;
  fg_area_pct: number;
  coverage_pct?: number;
  stone_count: number;
  fps: number;
  infer_ms: number;
}

export interface RoiPreviewResponse {
  width: number;
  height: number;
  image_b64: string;
}

export interface RoiAnalyzeResponse {
  width: number;
  height: number;
  model: string;
  threshold: number;
  fg_area_pct: number;
  image_b64: string;
  mask_b64: string;
}

export interface SourceVideo {
  name: string;
  path: string;
  size_bytes: number;
  size_mb: number;
}

// ---------------------------------------------------------------------------
// Low-level helpers
// ---------------------------------------------------------------------------
async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return (await res.json()) as T;
}

async function sendJSON<T>(method: string, path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status}`);
  return (await res.json()) as T;
}

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`);
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------------
export const api = {
  base: API_BASE,

  health: () => getJSON<HealthResponse>("/api/health"),

  listModels: () => getJSON<ModelsResponse>("/api/models"),

  // Presets
  listPresets: () => getJSON<Preset[]>("/api/presets"),
  createPreset: (p: { name: string; roi_json: Roi; model: string; threshold: number; stride: number }) =>
    sendJSON<Preset>("POST", "/api/presets", p),
  deletePreset: async (id: number) => {
    const res = await fetch(`${API_BASE}/api/presets/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) throw new Error(`DELETE preset ${id} -> ${res.status}`);
  },

  // Sessions
  listSessions: () => getJSON<SessionOut[]>("/api/sessions"),
  getSession: (id: number) => getJSON<SessionOut>(`/api/sessions/${id}`),
  createSession: (s: { name: string; model: string; threshold: number; roi_json: Roi; stride: number; grid_cell_px?: number; grid_occ_fraction?: number; refine_edges?: boolean }) =>
    sendJSON<SessionOut>("POST", "/api/sessions", s),
  uploadVideo: (id: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return postForm<{ session_id: number; bytes: number }>(`/api/sessions/${id}/upload`, fd);
  },
  listMeasurements: (id: number) => getJSON<Measurement[]>(`/api/sessions/${id}/measurements`),
  exportCsvUrl: (id: number) => `${API_BASE}/api/sessions/${id}/export.csv`,
  exportPdfUrl: (id: number) => `${API_BASE}/api/sessions/${id}/export.pdf`,
  deleteSession: async (id: number) => {
    const res = await fetch(`${API_BASE}/api/sessions/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) throw new Error(`DELETE session ${id} -> ${res.status}`);
  },
  getTracks: (id: number) => getJSON<TracksResponse>(`/api/sessions/${id}/tracks`),
  videoUrl: (id: number) => `${API_BASE}/api/sessions/${id}/video`,
  stopSession: (id: number) => sendJSON<{ session_id: number; stopping: boolean }>("POST", `/api/sessions/${id}/stop`, {}),

  // ROI preview
  roiPreview: (image: File, roi: Roi) => {
    const fd = new FormData();
    fd.append("image", image);
    fd.append("roi", JSON.stringify(roi));
    return postForm<RoiPreviewResponse>("/api/roi/preview", fd);
  },

  // ROI analyze: rectified image + segmentation mask + fg% (for live tuning preview)
  roiAnalyze: (image: File, roi: Roi, opts: { model?: string; threshold?: number; refine_edges?: boolean } = {}) => {
    const fd = new FormData();
    fd.append("image", image);
    fd.append("roi", JSON.stringify(roi));
    if (opts.model) fd.append("model", opts.model);
    if (opts.threshold != null) fd.append("threshold", String(opts.threshold));
    fd.append("refine_edges", String(!!opts.refine_edges));
    return postForm<RoiAnalyzeResponse>("/api/roi/analyze", fd);
  },

  // Source videos
  listSourceVideos: () => getJSON<{ videos: SourceVideo[]; count: number }>("/api/source-videos"),
  sourceVideoUrl: (name: string) => `${API_BASE}/api/source-videos/${encodeURIComponent(name)}/download`,
};
