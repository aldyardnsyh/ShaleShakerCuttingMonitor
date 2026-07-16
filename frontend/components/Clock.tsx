"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

function fmtTime(d: Date): string {
  return d.toLocaleTimeString("id-ID", { hour12: false });
}
function fmtDate(d: Date): string {
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}-${mm}-${d.getFullYear()}`;
}

/** Header clock: server time (anchored via /api/health offset) + local device time. */
export default function Clock() {
  const [now, setNow] = useState<Date>(new Date());
  const [serverOk, setServerOk] = useState<boolean | null>(null);
  const offsetRef = useRef<number>(0);

  useEffect(() => {
    let mounted = true;
    const sync = async () => {
      try {
        const h = await api.health();
        if (mounted) {
          offsetRef.current = new Date(h.server_time).getTime() - Date.now();
          setServerOk(true);
        }
      } catch {
        if (mounted) setServerOk(false);
      }
    };
    sync();
    const resync = setInterval(sync, 60_000);
    const tick = setInterval(() => setNow(new Date()), 1000);
    return () => { mounted = false; clearInterval(resync); clearInterval(tick); };
  }, []);

  const serverNow = new Date(now.getTime() + offsetRef.current);

  return (
    <div className="flex items-center gap-3 text-white">
      <span
        className={`inline-block h-2 w-2 rounded-full ${serverOk === false ? "bg-rose-300" : "bg-emerald-300"}`}
        title={serverOk === false ? "server tak terjangkau" : "server terhubung"}
      />
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" />
      </svg>
      <span className="font-mono text-sm tabular-nums tracking-tight">
        {fmtTime(serverNow)} {fmtDate(serverNow)}
      </span>
      <span className="hidden md:inline text-white/60 text-xs">
        · lokal {fmtTime(now)}
      </span>
    </div>
  );
}
