"use client";

import { BarsChart } from "@/components/charts/BarsChart";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { SimpleTable } from "@/components/tables/SimpleTable";
import { Panel } from "@/components/ui/card";
import { LoadingBlock, ErrorBlock } from "@/components/ui/state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { int, money, num, pct, pnlClass, signedMoney } from "@/lib/format";
import { useBt, usePostQuery } from "@/lib/hooks";
import type { StressData } from "@/lib/types-api";

type Row = Record<string, number | string>;
const cols = (key: "ticks" | "label" | "label2", header: string, base: number) => [
  { key, header, render: (r: Row) => String(r[key === "label2" ? "label" : key]) },
  { key: "net_profit", header: "Net P&L", align: "right" as const, render: (r: Row) => signedMoney(r.net_profit as number), cellClass: (r: Row) => pnlClass(r.net_profit as number) },
  { key: "delta", header: "vs current", align: "right" as const, render: (r: Row) => { const d = (r.net_profit as number) - base; return d === 0 ? "–" : signedMoney(d); }, cellClass: (r: Row) => pnlClass((r.net_profit as number) - base) },
  { key: "profit_factor", header: "Profit factor", align: "right" as const, render: (r: Row) => num(r.profit_factor as number) },
  { key: "sharpe", header: "Sharpe", align: "right" as const, render: (r: Row) => num(r.sharpe as number) },
  { key: "max_drawdown", header: "Max DD", align: "right" as const, render: (r: Row) => money(r.max_drawdown as number) },
];

export default function StressPage() {
  const { id } = useBt();
  const q = usePostQuery<StressData>("/stress-test", id ? { backtest_id: id, runs: 300 } : null);
  return (
    <>
      <PageHeader title="Stress tests" description="How much of the result survives worse execution, higher costs, missed trades and the loss of your best trades? Strategies that only work with perfect fills rarely work live." />
      {q.error ? <ErrorBlock error={q.error} /> : !q.data ? <LoadingBlock label="Running stress tests…" height="h-64" /> : (() => {
        const s = q.data;
        const base = s.baseline.net_profit;
        const slip = s.slippage as unknown as Row[];
        const comm = s.commission as unknown as Row[];
        return (
          <div className="space-y-4">
            <KpiGrid>
              <KpiCard label="Current net profit" value={signedMoney(base)} tone={base >= 0 ? "up" : "down"} />
              <KpiCard label="Profit factor" value={num(s.baseline.profit_factor)} />
              <KpiCard label="Sharpe" value={num(s.baseline.sharpe)} />
              <KpiCard label="Max drawdown" value={money(s.baseline.max_drawdown)} tone="down" />
              <KpiCard label="Base slippage" value={`${s.base_slippage_ticks} tick${s.base_slippage_ticks === 1 ? "" : "s"}`} sub="per market fill" />
              <KpiCard label="Trades" value={int(s.baseline.trades)} />
            </KpiGrid>
            <Tabs defaultValue="slippage">
              <TabsList>
                <TabsTrigger value="slippage">Slippage</TabsTrigger>
                <TabsTrigger value="commission">Commission</TabsTrigger>
                <TabsTrigger value="missed">Missed trades</TabsTrigger>
                <TabsTrigger value="outliers">Outlier dependence</TabsTrigger>
              </TabsList>
              <TabsContent value="slippage">
                <div className="grid gap-4 xl:grid-cols-2">
                  <Panel title="Net P&L vs slippage (ticks per market fill)"><TimeSeriesChart data={slip} xKey="ticks" xFormat={(v) => `${v}t`} series={[{ key: "net_profit", label: "Net P&L", color: "#4c8dff" }]} height={260} referenceY={0} yFormat={money} legend={false} minTickGap={10} /></Panel>
                  <Panel title="Results" bodyClassName="p-2"><SimpleTable rows={slip} columns={cols("ticks", "Slippage (ticks)", base)} /></Panel>
                </div>
                <p className="mt-2 text-[11px] text-muted">Re-prices every market fill (entries; exits other than resting targets) with the given slippage. Trade selection is unchanged.</p>
              </TabsContent>
              <TabsContent value="commission">
                <div className="grid gap-4 xl:grid-cols-2">
                  <Panel title="Net P&L vs fees"><BarsChart data={comm} xKey="label" bars={[{ key: "net_profit", label: "Net P&L", bySign: true }]} height={260} yFormat={money} /></Panel>
                  <Panel title="Results" bodyClassName="p-2"><SimpleTable rows={comm} columns={cols("label2", "Commission & fees", base)} /></Panel>
                </div>
              </TabsContent>
              <TabsContent value="missed">
                <Panel title="Randomly missed trades" subtitle={`Removing a random share of trades, ${s.missed[0]?.runs} seeded runs per level (mean and 5th–95th percentile)`} bodyClassName="p-2">
                  <SimpleTable
                    rows={s.missed}
                    columns={[
                      { key: "removed_pct", header: "Missed", render: (r) => `${r.removed_pct}%` },
                      { key: "net", header: "Net P&L (mean)", align: "right", render: (r) => signedMoney(r.net_profit.mean) , cellClass: (r) => pnlClass(r.net_profit.mean) },
                      { key: "range", header: "Net P&L 5–95%", align: "right", render: (r) => `${money(r.net_profit.p5)} … ${money(r.net_profit.p95)}` },
                      { key: "dd", header: "Max DD (mean)", align: "right", render: (r) => money(r.max_drawdown.mean) },
                      { key: "sh", header: "Sharpe (mean)", align: "right", render: (r) => num(r.sharpe.mean) },
                      { key: "pf", header: "PF (mean)", align: "right", render: (r) => num(r.profit_factor.mean) },
                      { key: "pp", header: "% runs profitable", align: "right", render: (r) => pct(r.prob_profitable, 0) },
                    ]}
                  />
                </Panel>
              </TabsContent>
              <TabsContent value="outliers">
                {s.outliers.warning && <div className={"mb-3 rounded-lg border p-3 text-[12px] " + (s.outliers.severity === "high" ? "border-down/40 bg-down/5 text-down" : "border-warn/40 bg-warn/5 text-warn")}>{s.outliers.warning}</div>}
                <Panel title="Removing the best trades" subtitle={`Top 10 trades supply ${pct(s.outliers.top10_share_of_gross_profit, 0)} of gross profit`} bodyClassName="p-2">
                  <SimpleTable
                    rows={s.outliers.rows as unknown as Row[]}
                    columns={[
                      { key: "label", header: "Removed" },
                      { key: "removed", header: "Trades", align: "right", render: (r) => int(r.removed as number) },
                      { key: "net_profit", header: "Net P&L", align: "right", render: (r) => signedMoney(r.net_profit as number), cellClass: (r) => pnlClass(r.net_profit as number) },
                      { key: "profit_factor", header: "Profit factor", align: "right", render: (r) => num(r.profit_factor as number) },
                      { key: "sharpe", header: "Sharpe", align: "right", render: (r) => num(r.sharpe as number) },
                      { key: "expectancy", header: "Expectancy", align: "right", render: (r) => signedMoney(r.expectancy as number, 2) },
                      { key: "max_drawdown", header: "Max DD", align: "right", render: (r) => money(r.max_drawdown as number) },
                    ]}
                  />
                </Panel>
              </TabsContent>
            </Tabs>
          </div>
        );
      })()}
    </>
  );
}
