"use client";

import { useLayoutEffect, useRef, useState, useCallback } from "react";
import { createPortal } from "react-dom";

interface Props {
  text: React.ReactNode;
  width?: number;
}

/**
 * Small "i" info button. The tooltip is rendered in a PORTAL on <body> with
 * fixed positioning computed from the trigger's rect, then clamped to the
 * viewport and flipped above/below as needed — so long tooltips are never
 * clipped by scroll containers (overflow) or covered by other cards.
 */
export default function InfoTip({ text, width = 264 }: Props) {
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const tipRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ left: number; top: number; place: "top" | "bottom" } | null>(null);

  const close = useCallback(() => { setOpen(false); setPos(null); }, []);

  useLayoutEffect(() => {
    if (!open) { setPos(null); return; }
    const place = () => {
      const b = btnRef.current?.getBoundingClientRect();
      if (!b) return;
      const vw = window.innerWidth, vh = window.innerHeight;
      const w = Math.min(width, vw - 16);
      const h = tipRef.current?.offsetHeight ?? 88;
      const cx = b.left + b.width / 2;
      const left = Math.max(8, Math.min(cx - w / 2, vw - w - 8));
      let top = b.top - h - 8;
      let placement: "top" | "bottom" = "top";
      if (top < 8) { top = b.bottom + 8; placement = "bottom"; }       // flip below
      if (placement === "bottom" && top + h > vh - 8) top = Math.max(8, vh - h - 8);
      setPos({ left, top, place: placement });
    };
    place();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    window.addEventListener("keydown", onKey);
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open, width, close]);

  return (
    <span className="relative inline-flex align-middle">
      <button
        ref={btnRef}
        type="button"
        aria-label="Informasi"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => close()}
        onFocus={() => setOpen(true)}
        onBlur={() => close()}
        onClick={(e) => { e.preventDefault(); setOpen((o) => !o); }}
        className="inline-flex items-center justify-center min-h-[44px] min-w-[44px]"
      >
        <span className="grid h-5 w-5 place-items-center rounded-full bg-slate-600 text-white text-[10px] font-bold hover:bg-slate-700 transition-colors dark:bg-slate-500">
          i
        </span>
      </button>
      {open && typeof document !== "undefined" && createPortal(
        <div
          ref={tipRef}
          role="tooltip"
          style={{
            position: "fixed",
            left: pos?.left ?? -9999,
            top: pos?.top ?? -9999,
            width: Math.min(width, typeof window !== "undefined" ? window.innerWidth - 16 : width),
            opacity: pos ? 1 : 0,
          }}
          className="z-[100] rounded-lg bg-slate-800 text-white text-[11px] leading-relaxed px-3 py-2 shadow-xl border border-slate-700 font-normal normal-case tracking-normal pointer-events-none"
        >
          {text}
        </div>,
        document.body
      )}
    </span>
  );
}
