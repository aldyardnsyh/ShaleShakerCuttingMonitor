import { API_BASE } from "./api";

// Resolve a ws:// or wss:// URL for a backend WebSocket path.
export function wsUrl(path: string): string {
  if (API_BASE) {
    return API_BASE.replace(/^http/, "ws") + path;
  }
  if (typeof window === "undefined") return path;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}${path}`;
}

// Per-frame payload pushed during live detection.
export interface FramePayload {
  frame_idx: number;
  t?: number;
  server_time: string;
  fg_area_pct: number;
  coverage_pct?: number;
  grid_cols?: number;
  grid_rows?: number;
  stone_count: number;
  fps: number;
  infer_ms: number;
  blobs?: { poly: number[][]; vx: number; vy: number }[];
  done?: boolean;
  status?: string;
}
