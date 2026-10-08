"use client";

import { useState } from "react";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { RulesPanel } from "@/components/prop/RulesForm";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { NumberField } from "@/components/ui/inputs";
import { ErrorBlock, LoadingBlock } from "@/components/ui/state";
import { pct } from "@/lib/format";
import { useBt, usePostQuery } from "@/lib/hooks";
import { usePropRules } from "@/lib/prop";
import type { SurvivalData } from "@/lib/types-api";

export default function SurvivalPage() {
  const { id } = useBt();
  const [rules] = usePropRules();
  const [d, setD] = useState({ sims: 3000, risk: null as number | null, seed: 5 });
  const [applied, setApplied] = useState<typeof d | null>(d);
  const q = usePostQuery<SurvivalData>("/prop-firm/survival", applied && id ? { backtest_id: id, rules, simulations: applied.sims, risk_per_trade: applied.risk, seed: applied.seed, block_size: 1 } : null);
  return (
    <>
      <PageHeader title="Funded account survival" description="Probability that a funded account has NOT yet breached the drawdown, daily-loss or contract rules after N days. Funded mode has no profit target, so this isolates how long the account lives under your rules." />
      <RulesPanel />
      <Panel title="Simulation" className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <NumberField label="Simulated accounts" value={d.sims} step={500} min={100} max={20000} onChange={(v) => setD({ ...d, sims: Math.round(v ?? 3000) })} className="w-40" />
          <NumberField label="Risk per trade ($)" value={d.risk} nullable step={25} min={1} onChange={(v) => setD({ ...d, risk: v })} className="w-40" />
          <NumberField label="Seed" value={d.seed} onChange={(v) => setD({ ...d, seed: Math.round(v ?? 5) })} className="w-24" />
          <Button variant="primary" onClick={() => setApplied(d)} disabled={q.isFetching}>Run</Button>
        </div>
      </Panel>
      {q.error ? <ErrorBlock error={q.error} /> : !q.data ? <LoadingBlock height="h-48" /> : (
        <div className="space-y-4">
          <KpiGrid className="xl:grid-cols-5">
            {q.data.marks.map((m) => <KpiCard key={m.calendar_days} label={`${m.calendar_days}-day survival`} value={pct(m.survival, 0)} sub={`${m.trading_days} trading days`} tone={m.survival >= 0.7 ? "up" : m.survival >= 0.4 ? "warn" : "down"} />)}
          </KpiGrid>
          <Panel title="Survival curve" subtitle="Share of simulated accounts still alive (calendar days converted to trading days at 5/7)">
            <TimeSeriesChart data={q.data.curve.map((c) => ({ day: c.trading_day, s: c.survival * 100 }))} xKey="day" xFormat={(v) => `${v}d`} series={[{ key: "s", label: "Survival %", kind: "area", color: "#2ebd85", width: 2 }]} height={300} yFormat={(v) => `${v.toFixed(0)}%`} domain={[0, 100]} minTickGap={25} />
          </Panel>
        </div>
      )}
    </>
  );
}
