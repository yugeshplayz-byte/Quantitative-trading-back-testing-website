"use client";

import { useState, type ReactNode } from "react";
import { API_CONFIGURED } from "@/lib/config";
import { useLocalValue } from "@/lib/store";
import { cn } from "@/lib/utils";
import { HonestyBar } from "./HonestyBar";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell({ children }: { children: ReactNode }) {
  const [sidebar, setSidebar] = useLocalValue("qbt_sidebar", "open");
  const [mobileOpen, setMobileOpen] = useState(false);
  const collapsed = sidebar === "closed";

  if (!API_CONFIGURED) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="max-w-lg rounded-lg border border-down/40 bg-down/5 p-5 text-[13px]">
          <h1 className="mb-2 text-base font-semibold text-down">Backend URL not configured</h1>
          <p className="text-muted">
            Set <code className="num text-foreground">NEXT_PUBLIC_API_URL</code> to your deployed FastAPI URL (for example in
            Vercel → Project Settings → Environment Variables) and redeploy. See the README deployment section.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <div className="hidden md:flex">
        <Sidebar collapsed={collapsed} onToggle={() => setSidebar(collapsed ? "open" : "closed")} />
      </div>
      <div className={cn("fixed inset-0 z-40 md:hidden", mobileOpen ? "block" : "hidden")}>
        <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
        <div className="relative h-full w-60">
          <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} onNavigate={() => setMobileOpen(false)} />
        </div>
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setMobileOpen(true)} />
        <HonestyBar />
        <main className="min-h-0 flex-1 overflow-y-auto p-4">{children}</main>
      </div>
    </div>
  );
}
