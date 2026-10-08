import { titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Horizontal 0-100 bar. `invert` colours high values red (used for risk factors). */
export function ScoreBar({ label, value, weight, invert = false, suffix = "" }: { label: string; value: number; weight?: number; invert?: boolean; suffix?: string }) {
  const v = Math.max(0, Math.min(100, value));
  const good = invert ? v < 33 : v >= 66;
  const mid = invert ? v < 60 : v >= 40;
  const color = good ? "bg-up" : mid ? "bg-warn" : "bg-down";
  return (
    <div>
      <div className="mb-0.5 flex items-baseline justify-between text-[11.5px]">
        <span className="text-foreground/90">
          {titleCase(label)} {weight !== undefined && <span className="text-muted">· weight {(weight * 100).toFixed(0)}%</span>}
        </span>
        <span className="num text-muted">{v.toFixed(0)}{suffix}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${v}%` }} />
      </div>
    </div>
  );
}
