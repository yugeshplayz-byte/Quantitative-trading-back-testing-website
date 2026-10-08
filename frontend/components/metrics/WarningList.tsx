import { Badge, severityTone } from "@/components/ui/badge";
import type { Warning } from "@/lib/types";

export function WarningList({ warnings, empty = "No automated warnings." }: { warnings: Warning[]; empty?: string }) {
  if (warnings.length === 0) return <p className="text-[12px] text-muted">{empty}</p>;
  return (
    <ul className="space-y-2">
      {warnings.map((w) => (
        <li key={w.code + w.title} className="flex gap-2">
          <Badge tone={severityTone(w.severity)} className="mt-0.5 h-fit shrink-0">
            {w.severity}
          </Badge>
          <div>
            <div className="text-[12px] font-medium">{w.title}</div>
            <div className="text-[11.5px] text-muted">{w.detail}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}
