"use client";

import { useState } from "react";
import { ParamPicker, parseList, METRICS, type ParamCatalog } from "@/components/forms/ParamPicker";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { SimpleTable } from "@/components/tables/SimpleTable";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, NumberField, Select } from "@/components/ui/inputs";
import { ErrorBlock, LoadingBlock, Query } from "@/components/ui/state";
import { int, money, num, pct, pnlClass, signedMoney } from "@/lib/format";
import { useBt, useBtQuery, usePostQuery } from "@/lib/hooks";
import type { WalkForwardResult } from "@/lib/types";

const ROWS: { key: string; label: string; fmt: (v: number) => string; lowerBetter?: boolean }[] = [
  { key: "net_profit_per_day", label: "Net profit / trading day", fmt: (v) => signedMoney(v, 2) },
  { key: "sharpe", label: "Sharpe", fmt: (v) => num(v) },
  { key: "sortino", label: "Sortino", fmt: (v) => num(v) },
  { key: "profit_factor", label: "Profit factor", fmt: (v) => num(v) },
  { key: "win_rate", label: "Win rate", fmt: (v) => pct(v) },
  { key: "expectancy", label: "Expectancy / trade", fmt: (v) => signedMoney(v, 2) },
  { key: "max_drawdown", label: "Max drawdown", fmt: (v) => money(v), lowerBetter: true },
  { key: "trades", label: "Trades (avg per window)", fmt: (v) => int(v) },
];

export default function WalkForwardPage() {
  const { id } = useBt();
  const catalog = useBtQuery<ParamCatalog>("/parameters");
  return (
    <>
      <PageHeader title="Walk-forward analysis" description="Rolling train/test: parameters are optimised on each training window, then traded on the NEXT unseen window. In-sample (IS) numbers are what the optimiser saw; out-of-sample (OOS) numbers are the honest estimate. A large IS→OOS drop signals overfitting." />
      <Query q={catalog}>{(c) => <Runner key={id} catalog={c} />}</Query>
    </>
  );
}

function Runner({ catalog }: { catalog: ParamCatalog }) {
  const { id } = useBt();
  const strat = catalog.parameters.filter((p) => p.group === "strategy");
  const [d, setD] = useState({ train: 6, test: 2, step: 2, metric: "sharpe", x: strat[0]?.key ?? "stop.value", y: strat[1]?.key ?? "target.value", xs: "", ys: "" });
  const [applied, setApplied] = useState<typeof d | null>(null);
  const body = applied && id ? { backtest_id: id, train_months: applied.train, test_months: applied.test, step_months: applied.step, metric: applied.metric, param_x: applied.x, param_y: applied.y, x_values: parseList(applied.xs), y_values: parseList(applied.ys) } : null;
  const q = usePostQuery<WalkForwardResult>("/walk-forward", body);
  const r = q.data;
  const agg = r?.aggregate;
  const patch = (p: Partial<typeof d>) => setD({ ...d, ...p });
  return (
    <div className="space-y-4">
      <Panel title="Setup">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <NumberField label="Train (months)" value={d.train} min={1} max={36} onChange={(v) => patch({ train: Math.round(v ?? 6) })} />
          <NumberField label="Test (months)" value={d.test} min={1} max={12} onChange={(v) => patch({ test: Math.round(v ?? 2) })} />
          <NumberField label="Step (months)" value={d.step} min={1} max={12} onChange={(v) => patch({ step: Math.round(v ?? 2) })} />
          <Field label="Select parameters by"><Select value={d.metric} onChange={(e) => patch({ metric: e.target.value })}>{METRICS.filter((m) => m.key !== "prop_pass_probability").map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}</Select></Field>
        </div>
        <div className="mt-3"><ParamPicker catalog={catalog} x={d.x} y={d.y} xs={d.xs} ys={d.ys} onChange={(p) => patch(p)} /></div>
        <div className="mt-3 flex items-center gap-3">
          <Button variant="primary" onClick={() => setApplied(d)} disabled={q.isFetching}>Run walk-forward</Button>
          <span className="text-[11px] text-muted">Searching a small grid per window (default 3×3 around the current values). Runs can take 10–30 seconds.</span>
        </div>
      </Panel>
      {!applied ? null : q.error ? <ErrorBlock error={q.error} /> : !r ? <LoadingBlock label="Running walk-forward windows…" height="h-48" /> : !agg ? (
        <ErrorBlock error="No windows fit inside this backtest's date range. Shorten the train/test months or extend the backtest dates." />
      ) : (
        <>
          <KpiGrid>
            <KpiCard label="Windows" value={String(r.windows.length)} />
            <KpiCard label="Profitable OOS windows" value={`${r.profitable_windows}/${r.windows.length}`} sub={pct(r.consistency, 0)} tone={r.consistency >= 0.6 ? "up" : r.consistency >= 0.4 ? "warn" : "down"} />
            <KpiCard label="Stitched OOS net profit" value={signedMoney(agg.stitched_oos.net_profit)} tone={agg.stitched_oos.net_profit >= 0 ? "up" : "down"} />
            <KpiCard label="Stitched OOS Sharpe" value={num(agg.stitched_oos.sharpe)} tone={agg.stitched_oos.sharpe >= 0 ? "up" : "down"} />
            <KpiCard label="Stitched OOS profit factor" value={num(agg.stitched_oos.profit_factor)} />
            <KpiCard label="Stitched OOS max DD" value={money(agg.stitched_oos.max_drawdown)} tone="down" />
          </KpiGrid>
          <Panel title="Out-of-sample equity (stitched)" subtitle="Only days after each previous window's coverage are used, so nothing is counted twice">
            <TimeSeriesChart data={r.oos_curve as unknown as Record<string, number | string>[]} series={[{ key: "equity", label: "OOS equity", kind: "area", color: "#2ebd85" }]} height={240} yFormat={(v) => `$${(v / 1000).toFixed(1)}k`} />
          </Panel>
          <Panel title="In-sample vs out-of-sample" subtitle={`Selection metric: ${r.metric}. Averages across windows. Degradation = OOS vs IS (negative = OOS worse).`} bodyClassName="p-2">
            <SimpleTable
              rows={ROWS}
              columns={[
                { key: "label", header: "Metric", className: "font-sans" },
                { key: "is", header: "In-sample", align: "right", render: (x) => x.fmt(agg.is[x.key] ?? 0) },
                { key: "oos", header: "Out-of-sample", align: "right", render: (x) => x.fmt(agg.oos[x.key] ?? 0) },
                { key: "deg", header: "OOS degradation", align: "right", render: (x) => { const dg = agg.degradation[x.key]; return dg === null || dg === undefined ? "–" : `${dg > 0 ? "+" : ""}${(dg * 100).toFixed(0)}%`; }, cellClass: (x) => { const dg = agg.degradation[x.key]; if (dg === null || dg === undefined) return undefined; const good = x.lowerBetter ? dg < 0 : dg >= 0; return good ? "text-up" : "text-down"; } },
              ]}
            />
          </Panel>
          <Panel title="Windows" bodyClassName="p-2">
            <SimpleTable
              rows={r.windows}
              columns={[
                { key: "index", header: "#" },
                { key: "train", header: "Train period", render: (w) => `${w.train_start} → ${w.train_end}` },
                { key: "test", header: "Test period", render: (w) => `${w.test_start} → ${w.test_end}` },
                { key: "params", header: "Selected parameters", render: (w) => Object.entries(w.params).map(([k, v]) => `${k.split(".").pop()}=${v}`).join(", ") },
                { key: "is_net", header: "IS net", align: "right", render: (w) => signedMoney(w.is_metrics.net_profit), cellClass: (w) => pnlClass(w.is_metrics.net_profit) },
                { key: "is_sh", header: "IS Sharpe", align: "right", render: (w) => num(w.is_metrics.sharpe) },
                { key: "oos_net", header: "OOS net", align: "right", render: (w) => signedMoney(w.oos_metrics.net_profit), cellClass: (w) => pnlClass(w.oos_metrics.net_profit) },
                { key: "oos_sh", header: "OOS Sharpe", align: "right", render: (w) => num(w.oos_metrics.sharpe) },
                { key: "oos_n", header: "OOS trades", align: "right", render: (w) => int(w.oos_metrics.trades) },
                { key: "deg", header: "Degradation", align: "right", render: (w) => (w.degradation === null ? "–" : `${w.degradation > 0 ? "-" : "+"}${Math.abs(w.degradation * 100).toFixed(0)}%`), cellClass: (w) => (w.degradation !== null && w.degradation > 0.5 ? "text-down" : undefined) },
              ]}
            />
          </Panel>
          <p className="text-[11px] text-muted">Honesty note: walk-forward keeps the optimiser away from each test window, but if you chose this strategy after looking at the same period, the whole process is still biased. Treat results as an estimate, and prefer data the strategy has never seen.</p>
        </>
      )}
    </div>
  );
}
