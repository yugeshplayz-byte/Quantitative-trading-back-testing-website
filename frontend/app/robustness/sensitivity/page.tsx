"use client";

import { useState } from "react";
import { ParamPicker, parseList, METRICS, type ParamCatalog } from "@/components/forms/ParamPicker";
import { Heatmap } from "@/components/charts/Heatmap";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/inputs";
import { ErrorBlock, LoadingBlock, Query } from "@/components/ui/state";
import { num, pct } from "@/lib/format";
import { useBt, useBtQuery, usePostQuery } from "@/lib/hooks";
import type { ParameterOptimizationResult } from "@/lib/types";

const fmtMetric = (metric: string) => (v: number) => (metric === "net_profit" || metric === "max_drawdown" ? `$${v.toFixed(0)}` : metric === "prop_pass_probability" ? `${(v * 100).toFixed(0)}%` : v.toFixed(2));

export default function SensitivityPage() {
  const { id } = useBt();
  const catalog = useBtQuery<ParamCatalog>("/parameters");
  return (
    <>
      <PageHeader title="Parameter sensitivity & stability" description="Backtests a grid of two parameters and shows how performance changes between neighbouring values. A good strategy has a broad plateau; a single hot cell surrounded by poor ones is almost always curve-fitting." />
      <Query q={catalog}>{(c) => <Runner key={id} catalog={c} />}</Query>
    </>
  );
}

function Runner({ catalog }: { catalog: ParamCatalog }) {
  const { id } = useBt();
  const strat = catalog.parameters.filter((p) => p.group === "strategy");
  const [d, setD] = useState({ x: strat[0]?.key ?? "stop.value", y: strat[1]?.key ?? "target.value", xs: "", ys: "", metric: "sharpe" });
  const [applied, setApplied] = useState<typeof d | null>(null);
  const body = applied && id ? { backtest_id: id, param_x: applied.x, param_y: applied.y, x_values: parseList(applied.xs), y_values: parseList(applied.ys), metric: applied.metric } : null;
  const q = usePostQuery<ParameterOptimizationResult>("/optimization", body);
  const r = q.data;
  const patch = (p: Partial<typeof d>) => setD({ ...d, ...p });

  const markers = r ? r.y_values.map((yv, i) => r.x_values.map((xv, j) => {
    const parts: string[] = [];
    if (r.best.x === xv && r.best.y === yv) parts.push("★");
    if (r.current.x === xv && r.current.y === yv) parts.push("●");
    const flag = r.stability.flags[i]?.[j];
    if (flag === "peak") parts.push("▲");
    if (flag === "unstable") parts.push("≀");
    return parts.length ? parts.join("") : null;
  })) : [];

  return (
    <div className="space-y-4">
      <Panel title="Grid">
        <ParamPicker catalog={catalog} x={d.x} y={d.y} xs={d.xs} ys={d.ys} onChange={patch} />
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <Field label="Optimisation metric" className="w-64"><Select value={d.metric} onChange={(e) => patch({ metric: e.target.value })}>{METRICS.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}</Select></Field>
          <Button variant="primary" onClick={() => setApplied(d)} disabled={q.isFetching}>Run grid</Button>
          <span className="text-[11px] text-muted">Each cell is a full backtest (≈0.3s). Cells with fewer than 30 trades are blank.</span>
        </div>
      </Panel>
      {!applied ? null : q.error ? <ErrorBlock error={q.error} /> : !r ? <LoadingBlock label="Running grid…" height="h-48" /> : (
        <>
          <div className="rounded-lg border border-warn/40 bg-warn/5 p-3 text-[12px] text-warn">
            <b>In-sample results.</b> {r.selection_bias.note}
          </div>
          <KpiGrid>
            <KpiCard label="Stability score" value={num(r.stability.score, 0)} sub={r.stability.classification} tone={r.stability.score >= 70 ? "up" : r.stability.score >= 40 ? "warn" : "down"} hint="0–100: neighbourhood of the best cell, plateau width, share of positive cells, largest jump between adjacent cells" />
            <KpiCard label="Best cell" value={r.best.value === null ? "–" : fmtMetric(r.metric)(r.best.value)} sub={r.best.x === null ? "" : `${r.param_x}=${r.best.x}, ${r.param_y}=${r.best.y}`} />
            <KpiCard label="Your current settings" value={r.current.value === null ? "–" : fmtMetric(r.metric)(r.current.value)} sub={`${r.param_x}=${r.current.x}, ${r.param_y}=${r.current.y}`} />
            <KpiCard label="Plateau (cells ≥60% of best)" value={pct(r.stability.plateau_fraction, 0)} />
            <KpiCard label="Neighbours vs best" value={pct(r.stability.best_neighbour_ratio, 0)} hint="Average of the 3×3 block around the best cell, relative to the grid range" />
            <KpiCard label="Cells tested" value={String(r.selection_bias.cells_tested)} sub={`luck-only best Sharpe ≈ ${num(r.selection_bias.expected_best_sharpe_if_no_edge)}`} />
          </KpiGrid>
          <Panel title={`${METRICS.find((m) => m.key === r.metric)?.label} by ${r.param_y} (rows) × ${r.param_x} (columns)`} subtitle="★ best · ● your current settings · ▲ isolated peak · ≀ unstable neighbourhood">
            <Heatmap rows={r.y_values} cols={r.x_values} values={r.grid} format={fmtMetric(r.metric)} higherIsBetter={r.higher_is_better} diverging={r.metric !== "prop_pass_probability"} markers={markers} rowLabelWidth="w-16" subtitles={r.trades_grid.map((row) => row.map((n) => `${n} tr`))} />
            <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px]">
              <Badge tone={r.stability.score >= 70 ? "up" : r.stability.score >= 40 ? "warn" : "down"}>{r.stability.classification}</Badge>
              <span className="text-muted">{r.stability.message}</span>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
