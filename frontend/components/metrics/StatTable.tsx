import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface StatRow {
  label: ReactNode;
  value: ReactNode;
  tone?: "up" | "down" | "warn";
}

export function StatTable({ rows, className }: { rows: StatRow[]; className?: string }) {
  return (
    <table className={cn("w-full text-[12px]", className)}>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} className="border-b border-border/60 last:border-0">
            <td className="py-1 pr-3 text-muted">{r.label}</td>
            <td
              className={cn(
                "num py-1 text-right",
                r.tone === "up" && "text-up",
                r.tone === "down" && "text-down",
                r.tone === "warn" && "text-warn",
              )}
            >
              {r.value}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
