"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { ScoreBar } from "@/components/metrics/ScoreBar";
import { WarningList } from "@/components/metrics/WarningList";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { ErrorBlock, LoadingBlock } from "@/components/ui/state";
import { num, pct, signedMoney } from "@/lib/format";
import { useBt, useBtQuery } from "@/lib/hooks";
import type { PropMcSummary, RobustnessData } from "@/lib/types-api";
import type { DashboardData } from "@/lib/types-api";

export default function OverfittingPage() {
  const { id } = useBt();
  const dash = useBtQuery<DashboardData>("/dashboard");
  const [go, setGo] = useState(false);
  const ready = go || Boolean(dash.data?.cached_score);
  const q = useBtQuery<RobustnessData>("/robustness", ready);
  const r = q.data;
  return (
    <>
      <PageHeader title="Strategy score, robustness & overfitting" description="A transparent 0–100 score built from documented formulas. A strategy that loses money, or whose profit cannot be told apart from luck, is capped no matter how smooth the curve looks." />
      {!ready && (
        <Panel title="Compute robustness report">
          <p className="mb-3 text-[12px] text-muted">Runs stress tests, a Monte Carlo, a parameter grid, walk-forward windows and a prop-firm simulation for {id}. The first run takes roughly 20–60 seconds; results are cached afterwards.</p>
          <Button variant="primary" onClick={() => setGo(true)}>Run full robustness analysis</Button>
        </Panel>
      )}
      {ready && (q.error ? <ErrorBlock error={q.error} /> : !r ? <LoadingBlock label="Running stress tests, Monte Carlo, grid and walk-forward (first run only)…" height="h-56" /> : (() => {
        const sc = r.score;
        const o = r.overfitting;
        const tone = sc.score >= 65 ? "up" : sc.score >= 45 ? "warn" : "down";
        const wf = r.inputs.walk_forward as { windows: number; consistency: number; aggregate: { stitched_oos?: Record<string, number> } | null };
        const prop = r.inputs.prop as PropMcSummary;
        return (
          <div className="space-y-4">
            <div className={"rounded-lg border p-4 " + (tone === "up" ? "border-up/40 bg-up/5" : tone === "warn" ? "border-warn/40 bg-warn/5" : "border-down/40 bg-down/5")}>
              <div className="flex flex-wrap items-center gap-6">
                <div>
                  <div className="text-[10.5px] uppercase tracking-wide text-muted">Strategy score</div>
                  <div className="num text-[44px] font-bold leading-none">{sc.score.toFixed(0)}<span className="text-[18px] text-muted">/100</span></div>
                </div>
                <div className="num text-[34px] font-bold">{sc.grade}</div>
                <div className="min-w-[260px] flex-1">
                  <div className="text-[13px] font-semibold">{sc.verdict}</div>
                  {sc.capped && <div className="mt-1 text-[12px] text-muted">Score capped at {sc.cap.toFixed(0)}. Without the honesty gate the component scores alone would give {sc.uncapped_score.toFixed(0)} - do not be impressed by smooth curves on a result that may be luck.</div>}
                </div>
              </div>
            </div>
            <KpiGrid>
              <KpiCard label="Robustness score" value={num(r.robustness.score, 0)} sub="/100" tone={r.robustness.score >= 65 ? "up" : r.robustness.score >= 45 ? "warn" : "down"} />
              <KpiCard label="Overfitting risk" value={o.level} sub={`score ${o.score.toFixed(0)}/100`} tone={o.level === "LOW" ? "up" : o.level === "MEDIUM" ? "warn" : "down"} />
              <KpiCard label="Walk-forward consistency" value={pct(wf.consistency, 0)} sub={`${wf.windows} windows`} />
              <KpiCard label="OOS stitched net" value={signedMoney(wf.aggregate?.stitched_oos?.net_profit)} tone={(wf.aggregate?.stitched_oos?.net_profit ?? 0) >= 0 ? "up" : "down"} />
              <KpiCard label="Prop pass probability" value={pct(prop.pass_probability, 0)} sub="default 50K rules" />
              <KpiCard label="Optimisation trials logged" value={String((r.inputs.optimization_trials as number) ?? 0)} />
            </KpiGrid>
            <div className="grid gap-4 xl:grid-cols-3">
              <Panel title="Score components" subtitle="Weighted into the strategy score">
                <div className="space-y-2.5">{Object.entries(sc.components).map(([k, v]) => <ScoreBar key={k} label={k} value={v} weight={sc.weights[k]} />)}</div>
                <Methodology items={sc.methodology} />
              </Panel>
              <Panel title="Robustness components">
                <div className="space-y-2.5">{Object.entries(r.robustness.components).map(([k, v]) => <ScoreBar key={k} label={k} value={v} weight={r.robustness.weights[k]} />)}</div>
                <Methodology items={r.robustness.methodology} />
              </Panel>
              <Panel title="Overfitting risk factors" subtitle="Higher = worse" actions={<Badge tone={o.level === "LOW" ? "up" : o.level === "MEDIUM" ? "warn" : "down"}>{o.level}</Badge>}>
                <div className="space-y-2.5">{Object.entries(o.factors).map(([k, v]) => <ScoreBar key={k} label={k} value={v * 100} weight={o.weights[k]} invert />)}</div>
                <Methodology items={o.methodology} />
              </Panel>
            </div>
            <Panel title="Automated warnings"><WarningList warnings={r.warnings} empty="No warnings fired. That is not proof of an edge." /></Panel>
            <p className="text-[11px] text-muted">Scores summarise the evidence; they do not replace judgement. Every component is computed from this single backtest, so it cannot detect problems in the data or in assumptions you have not tested.</p>
          </div>
        );
      })())}
    </>
  );
}

function Methodology({ items }: { items: string[] }) {
  return (
    <details className="mt-3 text-[11px] text-muted">
      <summary className="cursor-pointer text-accent">Show methodology</summary>
      <ul className="mt-1.5 list-disc space-y-1 pl-4">{items.map((m, i) => <li key={i}>{m}</li>)}</ul>
    </details>
  );
}
