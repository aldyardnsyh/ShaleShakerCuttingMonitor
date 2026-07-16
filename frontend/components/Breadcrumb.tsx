"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LABELS: Record<string, string> = {
  "": "Dashboard",
  settings: "Settings",
  history: "Riwayat",
  panduan: "Panduan",
};

const ROOT = "Cutting Monitoring";

export default function Breadcrumb() {
  const pathname = usePathname();
  const seg = pathname.replace(/\//g, "").trim(); // "", "settings", "history", "panduan"
  const current = LABELS[seg] ?? "Dashboard";

  // "Cutting Monitoring" is a soft link to the Dashboard (Next.js client nav) so
  // it never triggers a full reload/reset of the running live session.
  return (
    <nav className="flex items-center gap-2 text-sm font-medium text-white/90">
      <Link href="/" className="text-white/80 hover:text-white transition-colors">{ROOT}</Link>
      <span className="text-white/50">›</span>
      <span className="text-white">{current}</span>
    </nav>
  );
}
