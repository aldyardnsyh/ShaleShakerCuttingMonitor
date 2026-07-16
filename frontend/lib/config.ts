import { Roi } from "./api";

// Default ROI corners (TL, TR, BR, BL) from the training notebook.
export const DEFAULT_ROI: Roi = [
  [760, 650],
  [1300, 614],
  [1315, 795],
  [780, 845],
];

export interface ActiveConfig {
  model: string;
  threshold: number;
  stride: number;
  roi: Roi;
  grid_cell_px: number;
  grid_occ_fraction: number;
  refine_edges: boolean;
}

const KEY = "shaker.activeConfig";

export const DEFAULT_CONFIG: ActiveConfig = {
  model: "mobilevit",
  threshold: 0.65,
  stride: 3,
  roi: DEFAULT_ROI,
  grid_cell_px: 16,
  grid_occ_fraction: 0.05,
  refine_edges: true,
};

export function loadConfig(): ActiveConfig {
  if (typeof window === "undefined") return DEFAULT_CONFIG;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULT_CONFIG;
    return { ...DEFAULT_CONFIG, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_CONFIG;
  }
}

export function saveConfig(cfg: ActiveConfig): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify(cfg));
}

// Remember the last session id so the dashboard can attach to it.
export function setLastSession(id: number): void {
  if (typeof window !== "undefined") window.localStorage.setItem("shaker.lastSession", String(id));
}
export function getLastSession(): number | null {
  if (typeof window === "undefined") return null;
  const v = window.localStorage.getItem("shaker.lastSession");
  return v ? Number(v) : null;
}

// Store a downscaled JPEG (data URL) of the last uploaded video's first frame
// + its natural size, so the Settings page can preview the rectified ROI
// without re-uploading. localStorage-friendly (small thumbnail).
const FRAME_KEY = "shaker.lastFrame";
export interface LastFrame {
  dataUrl: string;
  width: number;
  height: number;
}
export function setLastFrame(f: LastFrame): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(FRAME_KEY, JSON.stringify(f));
  } catch {
    /* quota: ignore */
  }
}
export function getLastFrame(): LastFrame | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(FRAME_KEY);
    return raw ? (JSON.parse(raw) as LastFrame) : null;
  } catch {
    return null;
  }
}
