import { CircleAlert, CircleCheck, CircleMinus, CircleX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface ReadinessData {
  verdict: "NOT_READY" | "PAPER_TRADE_CANDIDATE";
  headline: string;
  checks: { id: string; label: string; status: "pass" | "fail" | "warn" | "na"; blocking: boolean; detail: string }[];
  blocking_failures: number;
  warnings: number;
  adjusted_pvalue: number;
  next_steps: string[];
  methodology: string[];
}

const ICON = {
  pass: { Icon: CircleCheck, color: "text-up" },
  fail: { Icon: CircleX, color: "text-down" },
  warn: { Icon: CircleAlert, color: "text-warn" },
  na: { Icon: CircleMinus, color: "text-muted" },
} as const;

/** Conservative go / no-go checklist. The best possible verdict is "paper trading candidate" - never "deploy". */
export function ReadinessPanel({ data }: { data: ReadinessData }) {
  const ok = data.verdict === "PAPER_TRADE_CANDIDATE";
  return (
    <div className={cn("rounded-lg border", ok ? "border-warn/40" : "border-down/40")}>
      <div className={cn("flex flex-wrap items-center gap-3 border-b px-4 py-3", ok ? "border-warn/30 bg-warn/5" : "border-down/30 bg-down/5")}>
        <Badge tone={ok ? "warn" : "down"} className="px-2.5 py-1 text-[12px]">{ok ? "Paper-trade candidate" : "Not ready"}</Badge>
        <div className="min-w-[240px] flex-1 text-[13px] font-semibold">{data.headline}</div>
        <div className="text-[11px] text-muted">{data.blocking_failures} blocking · {data.warnings} warnings</div>
      </div>
      <ul className="divide-y divide-border">
        {data.checks.map((c) => {
          const { Icon, color } = ICON[c.status];
          return (
            <li key={c.id} className="flex gap-3 px-4 py-2">
              <Icon size={16} className={cn("mt-0.5 shrink-0", color)} />
              <div className="min-w-0">
                <div className="text-[12.5px] font-medium">
                  {c.label} {!c.blocking && <span className="ml-1 text-[10px] font-normal uppercase tracking-wide text-muted">advisory</span>}
                </div>
                <div className="text-[11.5px] text-muted">{c.detail}</div>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="border-t border-border px-4 py-3 text-[11.5px]">
        <div className="mb-1 font-semibold text-foreground/90">Before any real money</div>
        <ul className="list-disc space-y-0.5 pl-4 text-muted">{data.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul>
        <details className="mt-2 text-muted">
          <summary className="cursor-pointer text-accent">Show thresholds</summary>
          <ul className="mt-1 list-disc space-y-1 pl-4">{data.methodology.map((m, i) => <li key={i}>{m}</li>)}</ul>
        </details>
      </div>
    </div>
  );
}
