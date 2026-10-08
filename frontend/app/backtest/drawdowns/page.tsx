"use client";

import { useState } from "react";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { SimpleTable } from "@/components/tables/SimpleTable";
import { Panel } from "@/components/ui/card";
import { Query } from "@/components/ui/state";
import { days, money, pct, shortDate } from "@/lib/format";
import { useBt, useBtQuery } from "@/lib/hooks";
import type { DrawdownData } from "@/lib/types-api";
import { cn } from "@/lib/utils";

export default function DrawdownsPage() {
  const q = useBtQuery<DrawdownData>("/analytics/drawdowns");
  const { current } = useBt();
  const [unit, setUnit] = useState<"usd" | "pct">("pct");
  const m = current?.metrics;
  return (
    <>
      <PageHeader title="Drawdowns" description="Underwater curves use end-of-day closed equity. The headline max drawdown on the dashboard uses equity after every closed trade, so it can be larger than the daily figure here. Neither includes open-trade excursions (see MAE)." />
      <Query q={q} height="h-80">
        {(d) => (
          <div className="space-y-4">
            {m && (
              <KpiGrid>
                <KpiCard label="Max drawdown (per trade)" value={money(m.max_drawdown)} tone="down" sub={pct(m.max_drawdown_pct)} />
                <KpiCard label="Max drawdown (daily close)" value={money(m.max_drawdown_daily)} tone="down" sub={pct(m.max_drawdown_daily_pct)} />
                <KpiCard label="Average drawdown" value={money(m.average_drawdown)} />
                <KpiCard label="Longest drawdown" value={days(m.longest_drawdown_days)} />
                <KpiCard label="Drawdown periods" value={String(d.period_count)} />
                <KpiCard label="Recovery factor" value={m.recovery_factor === null ? "–" : (m.recovery_factor as number).toFixed(2)} />
              </KpiGrid>
            )}
            <Panel
              title="Underwater chart"
              actions={
                <div className="flex gap-0.5 rounded-md border border-border p-0.5 text-[11px]">
                  {(["pct", "usd"] as const).map((u) => (
                    <button key={u} onClick={() => setUnit(u)} className={cn("rounded px-2 py-0.5", unit === u ? "bg-surface-2 text-foreground" : "text-muted")}>{u === "pct" ? "Percentage" : "Dollar"}</button>
                  ))}
                </div>
              }
            >
              <TimeSeriesChart
                data={d.dates.map((date, i) => ({ date, v: unit === "pct" ? -d.drawdown_pct[i] : -d.drawdown[i] }))}
                series={[{ key: "v", label: unit === "pct" ? "Drawdown %" : "Drawdown $", kind: "area", color: "#f6465d" }]}
                height={260}
                yFormat={(v) => (unit === "pct" ? `${v.toFixed(0)}%` : `$${(v / 1000).toFixed(1)}k`)}
              />
            </Panel>
            <Panel title="Drawdown duration" subtitle="Consecutive days spent below a prior equity peak">
              <TimeSeriesChart data={d.dates.map((date, i) => ({ date, days: d.days_underwater[i] }))} series={[{ key: "days", label: "Days underwater", kind: "area", color: "#f0b429" }]} height={180} yFormat={(v) => `${v.toFixed(0)}d`} />
            </Panel>
            <Panel title="Top 10 drawdown periods" bodyClassName="p-0">
              <SimpleTable
                rows={d.periods}
                columns={[
                  { key: "start", header: "Start", render: (r) => shortDate(r.start) },
                  { key: "bottom", header: "Bottom", render: (r) => shortDate(r.bottom) },
                  { key: "recovery", header: "Recovery", render: (r) => (r.recovery ? shortDate(r.recovery) : <span className="text-warn">not recovered</span>) },
                  { key: "depth", header: "Drawdown $", align: "right", render: (r) => money(r.depth), cellClass: () => "text-down" },
                  { key: "depth_pct", header: "Drawdown %", align: "right", render: (r) => pct(r.depth_pct), cellClass: () => "text-down" },
                  { key: "duration_days", header: "Duration", align: "right", render: (r) => days(r.duration_days) },
                  { key: "recovery_days", header: "Recovery time", align: "right", render: (r) => (r.recovery_days === null ? "–" : days(r.recovery_days)) },
                ]}
              />
            </Panel>
          </div>
        )}
      </Query>
    </>
  );
}
