"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const MODULES = [
  { href: "/", label: "Dashboard", icon: "M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" },
  { href: "/settings/", label: "Settings", icon: "M12 15a3 3 0 100-6 3 3 0 000 6z M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z" },
  { href: "/history/", label: "Riwayat", icon: "M3 3v5h5 M3.05 13A9 9 0 106 5.3L3 8 M12 7v5l4 2" },
  { href: "/panduan/", label: "Panduan", icon: "M12 22a10 10 0 100-20 10 10 0 000 20z M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3 M12 17h.01" },
];

export default function Sidebar({ collapsed }: { collapsed: boolean }) {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <aside
      className={`${collapsed ? "w-16" : "w-60"} shrink-0 bg-white border-r border-slate-200 dark:bg-slate-800 dark:border-slate-700 flex flex-col transition-all duration-200`}
    >
      <div className={`h-16 flex items-center gap-2 border-b border-slate-200 dark:border-slate-700 ${collapsed ? "justify-center" : "px-5"}`}>
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-white overflow-hidden shrink-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.png" alt="Logo" className="h-8 w-8 object-contain" />
        </div>
        {!collapsed && (
          <div className="leading-tight">
            <div className="font-bold text-slate-800 dark:text-slate-100 text-sm">Shale Shaker</div>
            <div className="text-[11px] text-slate-500">Cutting Monitoring</div>
          </div>
        )}
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {MODULES.map((m) => {
          const active = isActive(m.href);
          return (
            <Link
              key={m.href}
              href={m.href}
              title={collapsed ? "" : m.label}
              className={`group relative flex items-center ${collapsed ? "justify-center" : ""} gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-brand-light text-brand-dark font-semibold dark:bg-brand/15"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700/60"
              }`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d={m.icon} />
              </svg>
              {!collapsed && m.label}
              {collapsed && (
                <span className="pointer-events-none absolute left-full ml-2 top-1/2 -translate-y-1/2 z-50 whitespace-nowrap rounded-md bg-slate-800 text-white text-xs font-medium px-2.5 py-1 shadow-lg opacity-0 translate-x-[-4px] group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-150">
                  {m.label}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
      {!collapsed && (
        <div className="p-4 text-[10px] text-slate-500 border-t border-slate-200 dark:border-slate-700">
          Internal tool · v0.2
        </div>
      )}
    </aside>
  );
}
