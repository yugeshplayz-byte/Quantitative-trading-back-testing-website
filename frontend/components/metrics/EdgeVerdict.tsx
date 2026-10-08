import { CircleCheck, CircleHelp, CircleX } from "lucide-react";
import { money, num } from "@/lib/format";
import type { Metrics } from "@/lib/types";
import { cn } from "@/lib/utils";

export type Verdict = "no_edge" | "unproven" | "evidence";

export function edgeVerdict(m: Metrics): { kind: Verdict; title: string; detail: string } {
  const exp = m.expectancy ?? 0;
  const p = m.expectancy_pvalue;
  const lo = m.expectancy_ci95_low, hi = m.expectancy_ci95_high;
  const ci = lo !== null && lo !== undefined && hi !== null && hi !== undefined ? ` 95% interval for the true average trade: ${money(lo, 2)} to ${money(hi, 2)}.` : "";
  if (exp <= 0) {
    return { kind: "no_edge", title: "No edge after costs", detail: `The average trade loses ${money(Math.abs(exp), 2)} after fees and slippage.${ci}` };
  }
  if (p === null || p === undefined || p > 0.05) {
    return {
      kind: "unproven",
      title: "Profitable, but unproven",
      detail: `The average trade makes ${money(exp, 2)}, but p = ${p === null || p === undefined ? "n/a" : num(p, 2)}: a result this good is common from luck alone.${ci}`,
    };
  }
  return {
    kind: "evidence",
    title: "Statistical evidence of an edge",
    detail: `p = ${num(p, 4)} (t = ${num(m.expectancy_tstat, 2)}).${ci} Still confirm out-of-sample, and discount for any parameter search you ran.`,
  };
}

const STYLE: Record<Verdict, { box: string; icon: typeof CircleX; color: string }> = {
  no_edge: { box: "border-down/40 bg-down/5", icon: CircleX, color: "text-down" },
  unproven: { box: "border-warn/40 bg-warn/5", icon: CircleHelp, color: "text-warn" },
  evidence: { box: "border-up/40 bg-up/5", icon: CircleCheck, color: "text-up" },
};

/** The single most important answer: is the result distinguishable from luck? */
export function EdgeVerdict({ metrics, className }: { metrics: Metrics; className?: string }) {
  const v = edgeVerdict(metrics);
  const { box, icon: Icon, color } = STYLE[v.kind];
  return (
    <div className={cn("flex items-start gap-3 rounded-lg border p-3", box, className)}>
      <Icon size={20} className={cn("mt-0.5 shrink-0", color)} />
      <div>
        <div className={cn("text-[13px] font-semibold", color)}>{v.title}</div>
        <div className="text-[12px] text-foreground/85">{v.detail}</div>
      </div>
    </div>
  );
}
