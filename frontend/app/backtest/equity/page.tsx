"use client";

import { useQueries } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { TimeSeriesChart, type Series } from "@/components/charts/TimeSeriesChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { Panel } from "@/components/ui/card";
import { Query } from "@/components/ui/state";
import { apiGet } from "@/lib/api";
import { money } from "@/lib/format";
import { useBt, useBtQuery } from "@/lib/hooks";
import type { EquityData } from "@/lib/types-api";
import { cn } from "@/lib/utils";
import { SERIES_COLORS } from "@/components/charts/theme";

type Mode = "net_equity" | "cumulative_pnl" | "gross_equity";
const MODES: { key: Mode; label: string }[] = [
  { key: "net_equity", label: "Account equity (net)" },
  { key: "cumulative_pnl", label: "Cumulative P&L" },
  { key: "gross_equity", label: "Gross equity (before costs)" },
];

export default function EquityPage() {
  const { id, list } = useBt();
  const q = useBtQuery<EquityData & { benchmark: number[]; benchmark_label: string }>("/analytics/equity");
  const [mode, setMode] = useState<Mode>("net_equity");
  const [sides, setSides] = useState({ long: false, short: false, benchmark: false });
  const [overlay, setOverlay] = useState<string[]>([]);

  const overlayQs = useQueries({
    queries: overlay.map((oid) => ({ queryKey: ["bt", oid, "/analytics/equity"], queryFn: () => apiGet<EquityData>(`/backtests/${oid}/analytics/equity`) })),
  });

  const built = useMemo(() => {
    const d = q.data;
    if (!d) return null;
    const key = mode;
    const base = d[key];
    const start = d.net_equity[0] - (d.cumulative_pnl[0] ?? 0);
    const rows = d.dates.map((date, i) => {
      const row: Record<string, number | string> = { date, main: base[i] };
      const toMode = (series: number[], j: number) => (mode === "cumulative_pnl" ? series[j] - start : series[j]);
      if (sides.long) row.long = toMode(d.long_equity, i);
      if (sides.short) row.short = toMode(d.short_equity, i);
      if (sides.benchmark) row.bench = toMode(d.benchmark, i);
      return row;
    });
    const byDate = new Map(rows.map((r) => [r.date as string, r]));
    const series: Series[] = [{ key: "main", label: MODES.find((m) => m.key === mode)?.label ?? "", kind: "area", color: "#4c8dff", width: 2 }];
    if (sides.long) series.push({ key: "long", label: "Long only (net)", color: "#2ebd85" });
    if (sides.short) series.push({ key: "short", label: "Short only (net)", color: "#f6465d" });
    if (sides.benchmark) series.push({ key: "bench", label: d.benchmark_label, color: "#8592a6", dashed: true });
    overlay.forEach((oid, k) => {
      const od = overlayQs[k]?.data;
      if (!od) return;
      const name = list.find((b) => b.id === oid)?.name ?? oid;
      od.dates.forEach((dt, j) => {
        const r = byDate.get(dt);
        if (r) r[`o_${oid}`] = od[key][j];
      });
      series.push({ key: `o_${oid}`, label: `${oid} ${name}`, color: SERIES_COLORS[(k + 2) % SERIES_COLORS.length] });
    });
    return { rows, series };
  }, [q.data, mode, sides, overlay, overlayQs, list]);

  return (
    <>
      <PageHeader title="Equity curve" description="Account equity after fees and slippage. Gross equity shows what the strategy would have made with zero costs. Overlay other experiments to compare strategy versions on the same dates." />
      <Query q={q} height="h-80">
        {(d) => (
          <div className="space-y-4">
            <Panel title="Series">
              <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[12px]">
                <div className="flex gap-1 rounded-md border border-border p-0.5">
                  {MODES.map((m) => (
                    <button key={m.key} onClick={() => setMode(m.key)} className={cn("rounded px-2 py-1", mode === m.key ? "bg-surface-2 text-foreground" : "text-muted hover:text-foreground")}>{m.label}</button>
                  ))}
                </div>
                {([["long", "Long-only"], ["short", "Short-only"], ["benchmark", "Benchmark (buy & hold)"]] as const).map(([k, label]) => (
                  <label key={k} className="flex items-center gap-1.5">
                    <input type="checkbox" checked={sides[k]} onChange={(e) => setSides({ ...sides, [k]: e.target.checked })} className="accent-[#4c8dff]" />
                    {label}
                  </label>
                ))}
              </div>
              {list.length > 1 && (
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pt-3 text-[12px]">
                  <span className="text-muted">Overlay strategy versions:</span>
                  {list.filter((b) => b.id !== id).map((b) => (
                    <label key={b.id} className="flex items-center gap-1.5">
                      <input type="checkbox" checked={overlay.includes(b.id)} onChange={(e) => setOverlay(e.target.checked ? [...overlay, b.id] : overlay.filter((x) => x !== b.id))} className="accent-[#4c8dff]" />
                      {b.id} {b.name}
                    </label>
                  ))}
                </div>
              )}
            </Panel>
            <Panel title="Equity" subtitle={`Ending net equity ${money(d.net_equity[d.net_equity.length - 1])}`}>
              {built && <TimeSeriesChart data={built.rows} series={built.series} height={420} yFormat={(v) => (Math.abs(v) >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(0)}`)} />}
            </Panel>
          </div>
        )}
      </Query>
    </>
  );
}
