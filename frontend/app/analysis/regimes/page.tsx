"use client";

import { GroupTable } from "@/components/analysis/GroupTable";
import { BarsChart } from "@/components/charts/BarsChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { SimpleTable } from "@/components/tables/SimpleTable";
import { Panel } from "@/components/ui/card";
import { Query } from "@/components/ui/state";
import { int, money, num, pct, pnlClass, signedMoney } from "@/lib/format";
import { useBtQuery } from "@/lib/hooks";
import type { RegimesData } from "@/lib/types-api";

const PHASES = ["Before", "During", "After"] as const;

export default function RegimesPage() {
  const q = useBtQuery<RegimesData>("/analytics/regimes");
  return (
    <>
      <PageHeader title="Market regimes, volatility & events" description="Regimes are classified from price using only information available at the time of each signal (volatility percentile, efficiency ratio and trend vs a slow EMA) - never with hindsight. Compare buckets only when each has a meaningful number of trades." />
      <Query q={q} height="h-80">
        {(d) => (
          <div className="space-y-4">
            <div className="grid gap-4 xl:grid-cols-2">
              <Panel title="Net P&L by regime">
                <BarsChart data={d.rows as unknown as Record<string, number | string>[]} xKey="label" bars={[{ key: "net_pnl", label: "Net P&L", bySign: true }]} height={240} yFormat={money} xFormat={(v) => v.replace("Volatility", "Vol")} />
              </Panel>
              <Panel title="Net P&L by ATR percentile">
                <BarsChart data={d.volatility as unknown as Record<string, number | string>[]} xKey="label" bars={[{ key: "net_pnl", label: "Net P&L", bySign: true }]} height={240} yFormat={money} />
              </Panel>
            </div>
            <Panel title="Regime comparison" bodyClassName="p-2"><GroupTable rows={d.rows} labelHeader="Regime" /></Panel>
            <Panel title="Volatility analysis (ATR percentile at signal)" bodyClassName="p-2"><GroupTable rows={d.volatility} labelHeader="ATR percentile" /></Panel>
            <Panel title="Event analysis" subtitle={d.events.note}>
              <SimpleTable
                rows={d.events.rows}
                columns={[
                  { key: "event", header: "Event", className: "font-sans" },
                  { key: "occurrences", header: "Dates", align: "right", render: (r) => int(r.occurrences) },
                  ...PHASES.flatMap((ph) => [
                    { key: `${ph}-n`, header: `${ph}: trades`, align: "right" as const, render: (r: RegimesData["events"]["rows"][number]) => int(r.phases[ph].trades) },
                    { key: `${ph}-pnl`, header: `${ph}: net P&L`, align: "right" as const, render: (r: RegimesData["events"]["rows"][number]) => signedMoney(r.phases[ph].net_pnl), cellClass: (r: RegimesData["events"]["rows"][number]) => pnlClass(r.phases[ph].net_pnl) },
                    { key: `${ph}-wr`, header: `${ph}: win`, align: "right" as const, render: (r: RegimesData["events"]["rows"][number]) => (r.phases[ph].trades ? pct(r.phases[ph].win_rate, 0) : "–") },
                  ]),
                ]}
                footer={
                  d.events.baseline ? (
                    <tr className="border-t border-border bg-surface-2/50 text-muted">
                      <td className="px-2 py-1 font-sans" colSpan={2}>Non-event days (baseline)</td>
                      <td className="num px-2 py-1 text-right" colSpan={9}>
                        {int(d.events.baseline.trades)} trades · {signedMoney(d.events.baseline.net_pnl)} · win {pct(d.events.baseline.win_rate, 0)} · expectancy {num(d.events.baseline.expectancy)}
                      </td>
                    </tr>
                  ) : null
                }
              />
              <p className="mt-2 text-[11px] text-muted">Before = previous trading day. During = first 90 minutes after the later of the release time and the 09:30 open. After = the rest of the event day.</p>
            </Panel>
          </div>
        )}
      </Query>
    </>
  );
}
