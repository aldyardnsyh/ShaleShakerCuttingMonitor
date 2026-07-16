"use client";

import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

export interface TrendPoint {
  idx: number;
  pct: number;
  stone: number;
  ts?: string;
  t?: number;
}

function fmtClock(p: TrendPoint): { date: string; time: string } {
  if (p.ts) {
    const d = new Date(p.ts);
    return {
      date: d.toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" }),
      time: d.toLocaleTimeString("id-ID", { hour12: false }),
    };
  }
  const s = Math.floor(p.t ?? 0);
  return { date: "video", time: `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}` };
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: { payload: TrendPoint }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  const { date, time } = fmtClock(p);
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-card dark:bg-slate-800 dark:border-slate-700">
      <div className="text-slate-500">Tanggal <span className="font-medium text-slate-700 dark:text-slate-200">{date}</span></div>
      <div className="text-slate-500">Waktu <span className="font-mono font-medium text-slate-700 dark:text-slate-200">{time}</span></div>
      <div className="text-slate-500">Stone <span className="font-medium text-sky-600">{p.stone}</span></div>
      <div className="text-slate-500">Coverage <span className="font-semibold text-brand">{p.pct.toFixed(2)}%</span></div>
    </div>
  );
}

/**
 * Vertical trend (per design guideline): time runs DOWN the Y axis (oldest at
 * top → newest at bottom), coverage % on the X axis (0–100). Hover shows
 * date, time, stone count, and coverage.
 */
export default function TrendChart({ data, height = 320 }: { data: TrendPoint[]; height?: number | string }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} layout="vertical" margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis type="number" domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 11 }} unit="%" />
        <YAxis
          type="category"
          dataKey="idx"
          reversed
          width={44}
          tick={{ fill: "#94a3b8", fontSize: 10 }}
          tickFormatter={(_v, i) => {
            const p = data[i];
            return p ? fmtClock(p).time : "";
          }}
          interval="preserveStartEnd"
          minTickGap={18}
        />
        <Tooltip content={<CustomTooltip />} />
        <Line type="monotone" dataKey="pct" stroke="#F47A20" strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
