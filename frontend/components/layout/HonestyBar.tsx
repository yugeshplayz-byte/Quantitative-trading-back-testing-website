"use client";

import { ShieldCheck, TriangleAlert } from "lucide-react";
import { useBt, useApiQuery } from "@/lib/hooks";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";

interface Meta {
  caveats: string[];
  data_source: { kind: string; note: string };
}

/** Always-visible reminder of what the numbers do and do not mean. Never dismissible. */
export function HonestyBar() {
  const { current } = useBt();
  const meta = useApiQuery<Meta>("/meta");
  const engineered = current?.config.data_model === "structured";
  const synthetic = (meta.data?.data_source.kind ?? "synthetic") === "synthetic";
  if (!synthetic && !engineered) return null;
  return (
    <div
      className={
        "no-print flex flex-wrap items-center gap-x-3 gap-y-0.5 border-b px-4 py-1 text-[11px] " +
        (engineered ? "border-warn/40 bg-warn/10 text-warn" : "border-border bg-surface-2 text-muted")
      }
    >
      {engineered ? <TriangleAlert size={12} /> : <ShieldCheck size={12} />}
      <span>
        {engineered
          ? "ENGINEERED-EDGE MARKET (validation only): this synthetic market was built with structure on purpose. Results do not describe real markets."
          : "SYNTHETIC DATA (random walk, no built-in edge): results demonstrate the platform and are not evidence of live performance."}
      </span>
      <Dialog>
        <DialogTrigger className="underline underline-offset-2 hover:text-foreground">What do these numbers assume?</DialogTrigger>
        <DialogContent title="Assumptions & caveats" description="Read before trusting any result.">
          <ul className="list-disc space-y-2 pl-5 text-[12.5px]">
            {(meta.data?.caveats ?? []).map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </DialogContent>
      </Dialog>
    </div>
  );
}
