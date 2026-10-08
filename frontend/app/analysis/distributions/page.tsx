"use client";

import { BarsChart } from "@/components/charts/BarsChart";
import { Histogram } from "@/components/charts/Histogram";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { StatTable } from "@/components/metrics/StatTable";
import { Panel } from "@/components/ui/card";
import { Query } from "@/components/ui/state";
import { money, num } from "@/lib/format";
import { useBtQuery } from "@/lib/hooks";
import type { DistributionsData, StatsBlock, StreakData } from "@/lib/types-api";

const CHARTS: { key: string; title: string; unit: "money" | "r" | "min" | "pct"; split?: number; color?: string }[] = [
  { key: "trade_pnl", title: "Trade P&L", unit: "money", split: 0 },
  { key: "winners", title: "Winners", unit: "money", color: "#2ebd85" },
  { key: "losers", title: "Losers", unit: "money", color: "#f6465d" },
  { key: "r_multiples", title: "R multiples", unit: "r", split: 0 },
  { key: "holding_time", title: "Holding time (minutes)", unit: "min", color: "#a371f7" },
  { key: "daily_returns", title: "Daily returns (%)", unit: "pct", split: 0 },
];

const fmt = (unit: string, v: number | null) => (v === null ? "–" : unit === "money" ? money(v, 2) : unit === "r" ? `${num(v)}R` : unit === "min" ? `${num(v, 0)}m` : `${num(v, 3)}%`);

function Stats({ s, unit }: { s: StatsBlock; unit: string }) {
  return (
    <StatTable
      rows={[
        { label: "Count", value: s.count },
        { label: "Mean", value: fmt(unit, s.mean) },
        { label: "Median", value: fmt(unit, s.median) },
        { label: "Std dev", value: fmt(unit, s.std) },
        { label: "Skewness", value: num(s.skew) },
        { label: "Excess kurtosis", value: num(s.kurtosis) },
        { label: "5th percentile", value: fmt(unit, s.p5) },
        { label: "95th percentile", value: fmt(unit, s.p95) },
      ]}
    />
  );
}

export default function DistributionsPage() {
  const q = useBtQuery<DistributionsData>("/analytics/distributions");
  const streaks = useBtQuery<StreakData>("/analytics/streaks");
  return (
    <>
      <PageHeader title="Distributions & streaks" description="Shape of the return distribution. Negative skew and high kurtosis mean the average hides rare large losses. Excess kurtosis is relative to a normal distribution (0)." />
      <Query q={q} height="h-80">
        {(d) => (
          <div className="space-y-4">
            <div className="grid gap-4 xl:grid-cols-2">
              {CHARTS.map((c) => (
                <Panel key={c.key} title={c.title}>
                  <div className="grid gap-3 lg:grid-cols-[1fr_200px]">
                    <Histogram hist={d[c.key].hist} height={210} splitAt={c.split} color={c.color} xFormat={(v) => (c.unit === "money" ? `$${v.toFixed(0)}` : num(v, c.unit === "pct" ? 2 : 1))} />
                    <Stats s={d[c.key].stats} unit={c.unit} />
                  </div>
                </Panel>
              ))}
            </div>
            <Query q={streaks} height="h-40">
              {(s) => (
                <div className="space-y-4">
                  <KpiGrid>
                    <KpiCard label="Longest losing streak" value={String(s.longest_loss)} tone="down" />
                    <KpiCard label="Longest winning streak" value={String(s.longest_win)} tone="up" />
                    <KpiCard label="Avg losing streak" value={num(s.avg_loss_streak)} />
                    <KpiCard label="Avg winning streak" value={num(s.avg_win_streak)} />
                    <KpiCard label="Current streak" value={`${s.current_streak.length} ${s.current_streak.type}`} />
                  </KpiGrid>
                  <div className="grid gap-4 xl:grid-cols-2">
                    <Panel title="Consecutive-loss distribution"><BarsChart data={s.loss_distribution as unknown as Record<string, number>[]} xKey="length" bars={[{ key: "count", label: "Occurrences", color: "#f6465d" }]} height={200} yFormat={(v) => v.toFixed(0)} /></Panel>
                    <Panel title="Consecutive-win distribution"><BarsChart data={s.win_distribution as unknown as Record<string, number>[]} xKey="length" bars={[{ key: "count", label: "Occurrences", color: "#2ebd85" }]} height={200} yFormat={(v) => v.toFixed(0)} /></Panel>
                  </div>
                </div>
              )}
            </Query>
          </div>
        )}
      </Query>
    </>
  );
}
