"use client";

import { useState } from "react";
import { Heatmap } from "@/components/charts/Heatmap";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { SERIES_COLORS } from "@/components/charts/theme";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { SimpleTable } from "@/components/tables/SimpleTable";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, NumberField, Select } from "@/components/ui/inputs";
import { ErrorBlock, LoadingBlock } from "@/components/ui/state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { money, num, pct, pnlClass, signedMoney } from "@/lib/format";
import { useBt, usePostQuery } from "@/lib/hooks";

interface CompareRow { id: string; name: string; symbol: string; net_profit: number; sharpe: number; sortino: number; profit_factor: number; max_drawdown: number; max_drawdown_pct: number; win_rate: number; expectancy: number; trades: number; prop_pass_probability: number }
interface Compare { rows: CompareRow[]; curves: Record<string, number[] | string[]>; names: Record<string, string> }
interface Combine { combined: Record<string, number>; individual: Record<string, { name: string; weight: number; net_profit: number; sharpe: number; max_drawdown: number }>; curve: Record<string, number[] | string[]>; correlation: { labels: string[]; values: number[][] }; avg_pairwise_correlation: number; weights: Record<string, number> }
interface Corr { kind: string; labels: string[]; values: number[][]; observations: number }

const KINDS = [["returns", "Strategy returns"], ["daily_pnl", "Daily P&L"], ["drawdowns", "Drawdowns"], ["signals", "Signals (net long−short trades/day)"], ["instruments", "Instruments (MNQ, NQ, MES, ES)"]];

export default function ComparisonPage() {
  const { list } = useBt();
  const [sel, setSel] = useState<string[]>(["BT-000001", "BT-000002"]);
  const valid = sel.filter((s) => list.some((b) => b.id === s));
  const toggle = (id: string) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length < 8 ? [...s, id] : s));
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [combineApplied, setCombineApplied] = useState<Record<string, number> | null>(null);
  const [kind, setKind] = useState("returns");

  const cmp = usePostQuery<Compare>("/research/compare", valid.length ? { backtest_ids: valid } : null);
  const comb = usePostQuery<Combine>("/research/combine", combineApplied);
  const corr = usePostQuery<Corr>("/research/correlation", valid.length ? { backtest_ids: valid, kind } : null);
  const w = (id: string) => weights[id] ?? Math.round(100 / Math.max(valid.length, 1));

  return (
    <>
      <PageHeader title="Strategy comparison" description="Compare saved experiments side by side, blend them into a weighted portfolio, and check how correlated they are. Diversification only helps if each ingredient has a real edge - blending two losing strategies gives a smoother loser." />
      <Panel title="Select experiments (up to 8)" className="mb-4">
        <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-[12px]">
          {list.map((b) => (
            <label key={b.id} className="flex items-center gap-1.5">
              <input type="checkbox" checked={sel.includes(b.id)} onChange={() => toggle(b.id)} className="accent-[#4c8dff]" />
              {b.id} {b.name}
            </label>
          ))}
        </div>
      </Panel>
      <Tabs defaultValue="compare">
        <TabsList>
          <TabsTrigger value="compare">Comparison</TabsTrigger>
          <TabsTrigger value="combine">Combination</TabsTrigger>
          <TabsTrigger value="corr">Correlation</TabsTrigger>
        </TabsList>
        <TabsContent value="compare">
          {cmp.error ? <ErrorBlock error={cmp.error} /> : !cmp.data ? <LoadingBlock height="h-48" /> : (
            <div className="space-y-4">
              <Panel title="Equity curves" subtitle="Net equity on each strategy's own starting balance">
                <TimeSeriesChart
                  data={(cmp.data.curves.dates as string[]).map((date, i) => ({ date, ...Object.fromEntries(cmp.data!.rows.map((r) => [r.id, (cmp.data!.curves[r.id] as number[])[i]])) }))}
                  series={cmp.data.rows.map((r, i) => ({ key: r.id, label: `${r.id} ${r.name}`, color: SERIES_COLORS[i % SERIES_COLORS.length] }))}
                  height={320}
                  yFormat={(v) => `$${(v / 1000).toFixed(0)}k`}
                />
              </Panel>
              <Panel title="Metrics" bodyClassName="p-2">
                <SimpleTable
                  rows={cmp.data.rows}
                  columns={[
                    { key: "name", header: "Strategy", render: (r) => `${r.id} ${r.name}`, className: "font-sans" },
                    { key: "net_profit", header: "Net profit", align: "right", render: (r) => signedMoney(r.net_profit), cellClass: (r) => pnlClass(r.net_profit) },
                    { key: "sharpe", header: "Sharpe", align: "right", render: (r) => num(r.sharpe) },
                    { key: "sortino", header: "Sortino", align: "right", render: (r) => (r.sortino > 999 ? "–" : num(r.sortino)) },
                    { key: "profit_factor", header: "Profit factor", align: "right", render: (r) => num(r.profit_factor) },
                    { key: "max_drawdown", header: "Max DD", align: "right", render: (r) => `${money(r.max_drawdown)} (${pct(r.max_drawdown_pct, 0)})` },
                    { key: "win_rate", header: "Win rate", align: "right", render: (r) => pct(r.win_rate) },
                    { key: "expectancy", header: "Expectancy", align: "right", render: (r) => signedMoney(r.expectancy, 2), cellClass: (r) => pnlClass(r.expectancy) },
                    { key: "trades", header: "Trades", align: "right" },
                    { key: "prop_pass_probability", header: "Prop pass prob.", align: "right", render: (r) => pct(r.prop_pass_probability, 0) },
                  ]}
                />
                <p className="px-2 pt-2 text-[11px] text-muted">Prop pass probability uses default generic 50K rules (edit rules on the Prop pages). A higher Sharpe or profit here means little unless the strategy&apos;s edge is statistically significant - check each one&apos;s p-value on its dashboard.</p>
              </Panel>
            </div>
          )}
        </TabsContent>
        <TabsContent value="combine">
          <Panel title="Weighted portfolio" subtitle="Each strategy's daily P&L is scaled by its weight (weights are normalised to 100%)" className="mb-4">
            <div className="flex flex-wrap items-end gap-3">
              {valid.map((id) => (
                <NumberField key={id} label={`${id} weight %`} value={w(id)} step={5} min={0} onChange={(v) => setWeights({ ...weights, [id]: v ?? 0 })} className="w-32" />
              ))}
              <Button variant="primary" disabled={valid.length < 1} onClick={() => setCombineApplied(Object.fromEntries(valid.map((id) => [id, w(id)])))}>Combine</Button>
            </div>
          </Panel>
          {combineApplied && (comb.error ? <ErrorBlock error={comb.error} /> : !comb.data ? <LoadingBlock height="h-40" /> : (
            <div className="space-y-4">
              <KpiGrid>
                <KpiCard label="Combined net profit" value={signedMoney(comb.data.combined.net_profit)} tone={comb.data.combined.net_profit >= 0 ? "up" : "down"} />
                <KpiCard label="Return" value={pct(comb.data.combined.return_pct)} />
                <KpiCard label="Sharpe" value={num(comb.data.combined.sharpe)} />
                <KpiCard label="Sortino" value={comb.data.combined.sortino > 999 ? "–" : num(comb.data.combined.sortino)} />
                <KpiCard label="Max drawdown" value={money(comb.data.combined.max_drawdown)} sub={pct(comb.data.combined.max_drawdown_pct)} tone="down" />
                <KpiCard label="Avg pairwise correlation" value={num(comb.data.avg_pairwise_correlation)} />
              </KpiGrid>
              <Panel title="Combined equity">
                <TimeSeriesChart
                  data={(comb.data.curve.dates as string[]).map((date, i) => ({ date, combined: (comb.data!.curve.combined as number[])[i] }))}
                  series={[{ key: "combined", label: "Combined", kind: "area", color: "#4c8dff" }]} height={280} yFormat={(v) => `$${(v / 1000).toFixed(0)}k`} />
              </Panel>
              <div className="grid gap-4 xl:grid-cols-2">
                <Panel title="Contribution" bodyClassName="p-2">
                  <SimpleTable rows={Object.entries(comb.data.individual).map(([id, v]) => ({ id, ...v }))} columns={[
                    { key: "id", header: "Strategy", render: (r) => `${r.id} ${r.name}`, className: "font-sans" },
                    { key: "weight", header: "Weight", align: "right", render: (r) => pct(r.weight, 0) },
                    { key: "net_profit", header: "Net (weighted)", align: "right", render: (r) => signedMoney(r.net_profit), cellClass: (r) => pnlClass(r.net_profit) },
                    { key: "sharpe", header: "Sharpe", align: "right", render: (r) => num(r.sharpe) },
                    { key: "max_drawdown", header: "Max DD", align: "right", render: (r) => money(r.max_drawdown) },
                  ]} />
                </Panel>
                <Panel title="Daily P&L correlation"><Heatmap rows={comb.data.correlation.labels} cols={comb.data.correlation.labels} values={comb.data.correlation.values} format={(v) => v.toFixed(2)} rowLabelWidth="w-24" /></Panel>
              </div>
            </div>
          ))}
        </TabsContent>
        <TabsContent value="corr">
          <Panel title="Correlation matrix" actions={<Field label="Series" className="w-72"><Select value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</Select></Field>}>
            {corr.error ? <ErrorBlock error={corr.error} /> : !corr.data ? <LoadingBlock height="h-40" /> : (
              <>
                <Heatmap rows={corr.data.labels} cols={corr.data.labels.map((l) => l.slice(0, 18))} values={corr.data.values} format={(v) => v.toFixed(2)} rowLabelWidth="w-48" />
                <p className="mt-2 text-[11px] text-muted">{corr.data.observations} overlapping observations. Correlations are noisy over short samples, and tend to rise toward 1 in market stress.</p>
              </>
            )}
          </Panel>
        </TabsContent>
      </Tabs>
    </>
  );
}
