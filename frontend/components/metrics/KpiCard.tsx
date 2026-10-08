import type { ReactNode } from "react";
import { Tip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export type KpiTone = "up" | "down" | "warn" | "neutral";

const toneClass: Record<KpiTone, string> = {
  up: "text-up",
  down: "text-down",
  warn: "text-warn",
  neutral: "text-foreground",
};

export function KpiCard({ label, value, sub, tone = "neutral", hint }: { label: string; value: ReactNode; sub?: ReactNode; tone?: KpiTone; hint?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2">
      <div className="flex items-center gap-1 text-[10.5px] uppercase tracking-wide text-muted">
        <span className="truncate">{label}</span>
        {hint && <Tip content={hint} />}
      </div>
      <div className={cn("num mt-0.5 truncate text-[18px] font-semibold leading-tight", toneClass[tone])}>{value}</div>
      {sub && <div className="num mt-0.5 truncate text-[10.5px] text-muted">{sub}</div>}
    </div>
  );
}

export function KpiGrid({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6", className)}>{children}</div>;
}

/** Positive -> up, negative -> down, zero/unknown -> neutral. */
export function signTone(v: number | null | undefined): KpiTone {
  if (v === null || v === undefined || v === 0 || !Number.isFinite(v)) return "neutral";
  return v > 0 ? "up" : "down";
}
