"use client";

import { useState } from "react";
import { Histogram } from "@/components/charts/Histogram";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { RulesPanel } from "@/components/prop/RulesForm";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { NumberField } from "@/components/ui/inputs";
import { ErrorBlock, LoadingBlock } from "@/components/ui/state";
import { money, num, pct } from "@/lib/format";
import { useBt, usePostQuery } from "@/lib/hooks";
import { usePropRules } from "@/lib/prop";
import type { PropMcSummary } from "@/lib/types-api";

export default function PassProbabilityPage() {
  const { id } = useBt();
  const [rules] = usePropRules();
  const [d, setD] = useState({ sims: 3000, risk: null as number | null, seed: 5, block: 1 });
  const [applied, setApplied] = useState<typeof d | null>(d);
  const q = usePostQuery<{ summary: PropMcSummary; risk_per_trade: number; base_risk: number }>("/prop-firm/monte-carlo", applied && id ? { backtest_id: id, rules, simulations: applied.sims, risk_per_trade: applied.risk, seed: applied.seed, block_size: applied.block } : null);
  const s = q.data?.summary;
  return (
    <>
      <PageHeader title="Challenge pass probability" description="Runs thousands of simulated evaluations by resampling this backtest's trading days. It answers: if the future looks like this backtest's past, how often does the evaluation pass, and how does it fail? It cannot tell you whether the past edge was real." />
      <RulesPanel />
      <Panel title="Simulation" className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <NumberField label="Simulated evaluations" value={d.sims} step={500} min={100} max={20000} onChange={(v) => setD({ ...d, sims: Math.round(v ?? 3000) })} className="w-40" />
          <NumberField label="Risk per trade ($)" value={d.risk} nullable step={25} min={1} onChange={(v) => setD({ ...d, risk: v })} className="w-40" hint="Blank = backtest's own size" />
          <NumberField label="Seed" value={d.seed} onChange={(v) => setD({ ...d, seed: Math.round(v ?? 5) })} className="w-24" />
          <NumberField label="Day block size" value={d.block} min={1} max={20} onChange={(v) => setD({ ...d, block: Math.round(v ?? 1) })} className="w-28" hint="1 = independent days" />
          <Button variant="primary" onClick={() => setApplied(d)} disabled={q.isFetching}>Run</Button>
        </div>
      </Panel>
      {q.error ? <ErrorBlock error={q.error} /> : !s ? <LoadingBlock label="Simulating evaluations…" height="h-48" /> : (
        <div className="space-y-4">
          {s.pass_probability < 0.01 && <div className="rounded-lg border border-down/40 bg-down/5 p-3 text-[12px] text-down">Essentially none of the {s.simulations.toLocaleString()} simulated evaluations passed. Under these rules this strategy does not pass.</div>}
          <KpiGrid>
            <KpiCard label="Pass probability" value={pct(s.pass_probability)} tone={s.pass_probability >= 0.5 ? "up" : s.pass_probability >= 0.2 ? "warn" : "down"} />
            <KpiCard label="Fail probability" value={pct(s.fail_probability)} tone="down" />
            <KpiCard label="Still active at window end" value={pct(s.active_probability)} sub={`${s.horizon_days} trading days`} />
            <KpiCard label="Median days to pass" value={s.median_days_to_pass === null ? "–" : num(s.median_days_to_pass, 0)} />
            <KpiCard label="Mean days to pass" value={s.mean_days_to_pass === null ? "–" : num(s.mean_days_to_pass, 1)} sub={s.p90_days_to_pass === null ? undefined : `90th pct ${num(s.p90_days_to_pass, 0)}`} />
            <KpiCard label="Ending balance (median)" value={money(s.ending_balance_median)} sub={`${money(s.ending_balance_p5)} – ${money(s.ending_balance_p95)} (5–95%)`} />
          </KpiGrid>
          <KpiGrid className="xl:grid-cols-3">
            <KpiCard label="Drawdown failure" value={pct(s.drawdown_failure_probability)} tone="down" />
            <KpiCard label="Daily-loss failure" value={pct(s.daily_loss_failure_probability)} tone="down" />
            <KpiCard label="Other failure (contracts)" value={pct(s.other_failure_probability)} tone="down" />
          </KpiGrid>
          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="Ending balance distribution"><Histogram hist={s.ending_balance_hist} marker={rules.starting_balance} markerLabel="start" splitAt={rules.starting_balance} xFormat={(v) => `$${(v / 1000).toFixed(1)}k`} /></Panel>
            <Panel title="Days to pass (passing runs only)"><Histogram hist={s.days_to_pass_hist} color="#4c8dff" xFormat={(v) => v.toFixed(0)} /></Panel>
          </div>
        </div>
      )}
    </>
  );
}
