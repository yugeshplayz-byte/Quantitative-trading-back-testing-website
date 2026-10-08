"use client";

import { GroupTable } from "@/components/analysis/GroupTable";
import { BarsChart } from "@/components/charts/BarsChart";
import { Heatmap } from "@/components/charts/Heatmap";
import { PageHeader } from "@/components/layout/PageHeader";
import { Panel } from "@/components/ui/card";
import { Query } from "@/components/ui/state";
import { money, num } from "@/lib/format";
import { useBtQuery } from "@/lib/hooks";
import type { TimeData } from "@/lib/types-api";

export default function TimePage() {
  const q = useBtQuery<TimeData>("/analytics/time");
  return (
    <>
      <PageHeader title="Time analysis" description="Performance by entry time of day and weekday (US/Eastern, regular trading hours). Small buckets are noisy - check trade counts before reading anything into a single cell." />
      <Query q={q} height="h-80">
        {(d) => {
          const tod = d.time_of_day.map((r) => ({ ...r }));
          const dow = d.day_of_week.map((r) => ({ ...r }));
          return (
            <div className="space-y-4">
              <div className="grid gap-4 xl:grid-cols-2">
                <Panel title="Net P&L by time of day">
                  <BarsChart data={tod as unknown as Record<string, number | string>[]} xKey="label" bars={[{ key: "net_pnl", label: "Net P&L", bySign: true }]} height={240} yFormat={money} />
                </Panel>
                <Panel title="Expectancy by time of day ($ per trade)">
                  <BarsChart data={tod as unknown as Record<string, number | string>[]} xKey="label" bars={[{ key: "expectancy", label: "Expectancy", bySign: true }]} height={240} yFormat={(v) => `$${v.toFixed(1)}`} />
                </Panel>
              </div>
              <Panel title="Time-of-day buckets" bodyClassName="p-2"><GroupTable rows={d.time_of_day} labelHeader="Entry time (ET)" /></Panel>
              <Panel title="Net P&L heatmap" subtitle="30-minute entry bucket × weekday (label = bucket end). Cell text = net $, hover for trade count.">
                <Heatmap
                  rows={d.heatmap.rows}
                  cols={d.heatmap.cols}
                  values={d.heatmap.values}
                  format={(v) => money(v)}
                  rowLabelWidth="w-14"
                  subtitles={d.heatmap.counts.map((r) => r.map((n) => `${n} tr`))}
                />
              </Panel>
              <div className="grid gap-4 xl:grid-cols-2">
                <Panel title="Day of week: net P&L">
                  <BarsChart data={dow as unknown as Record<string, number | string>[]} xKey="label" bars={[{ key: "net_pnl", label: "Net P&L", bySign: true }]} height={220} yFormat={money} />
                </Panel>
                <Panel title="Day of week: profit factor">
                  <BarsChart data={dow.map((r) => ({ label: r.label, pf: r.profit_factor ?? 0 })) as unknown as Record<string, number | string>[]} xKey="label" bars={[{ key: "pf", label: "Profit factor", color: "#4c8dff" }]} height={220} yFormat={(v) => num(v)} />
                </Panel>
              </div>
              <Panel title="Day-of-week comparison" bodyClassName="p-2"><GroupTable rows={d.day_of_week} labelHeader="Weekday" /></Panel>
              <Panel title="Long vs short" bodyClassName="p-2"><GroupTable rows={d.long_short.rows} labelHeader="Side" /></Panel>
            </div>
          );
        }}
      </Query>
    </>
  );
}
