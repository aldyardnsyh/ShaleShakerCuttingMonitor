"use client";

import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import Clock from "@/components/Clock";
import Breadcrumb from "@/components/Breadcrumb";
import ThemeToggle from "@/components/ThemeToggle";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar collapsed={collapsed} />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Orange header bar — responsive flex (no absolute overlap) */}
        <header className="h-16 shrink-0 bg-brand flex items-center gap-3 px-3 md:px-6 shadow-sm">
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="grid h-11 w-11 shrink-0 place-items-center rounded-lg text-white hover:bg-white/15 transition-colors"
            aria-label="Toggle sidebar"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 3v18" />
            </svg>
          </button>
          <div className="hidden sm:block h-5 w-px bg-white/30 shrink-0" />

          {/* Breadcrumb: takes remaining space, truncates */}
          <div className="flex-1 min-w-0 truncate">
            <Breadcrumb />
          </div>

          {/* Clock: shrinks, hidden on very small screens */}
          <div className="hidden md:flex shrink-0">
            <Clock />
          </div>

          <ThemeToggle />
        </header>

        {/* Clock for small screens (below md) */}
        <div className="md:hidden bg-brand-dark px-4 py-1">
          <Clock />
        </div>

        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
