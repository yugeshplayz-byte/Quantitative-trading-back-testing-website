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
import type { PayoutData } from "@/lib/types-api";

export default function PayoutsPage() {
  const { id } = useBt();
  const [rules] = usePropRules();
  const [d, setD] = useState({ sims: 3000, horizon: 180, risk: null as number | null, seed: 5 });
  const [applied, setApplied] = useState<typeof d | null>(d);
  const q = usePostQuery<PayoutData>("/prop-firm/payouts", applied && id ? { backtest_id: id, rules, simulations: applied.sims, horizon_days: applied.horizon, risk_per_trade: applied.risk, seed: applied.seed, block_size: 1 } : null);
  const p = q.data;
  return (
    <>
      <PageHeader title="Payout simulator" description="Simulates a funded account that withdraws profit under your payout rules. Expected payouts are the trader's share after the profit split. Withdrawals reduce the balance but, conservatively, do not lower the drawdown floor." />
      <RulesPanel showPayout />
      <Panel title="Simulation" className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <NumberField label="Simulated accounts" value={d.sims} step={500} min={100} max={20000} onChange={(v) => setD({ ...d, sims: Math.round(v ?? 3000) })} className="w-40" />
          <NumberField label="Horizon (trading days)" value={d.horizon} step={20} min={20} max={600} onChange={(v) => setD({ ...d, horizon: Math.round(v ?? 180) })} className="w-40" />
          <NumberField label="Risk per trade ($)" value={d.risk} nullable step={25} min={1} onChange={(v) => setD({ ...d, risk: v })} className="w-40" />
          <NumberField label="Seed" value={d.seed} onChange={(v) => setD({ ...d, seed: Math.round(v ?? 5) })} className="w-24" />
          <Button variant="primary" onClick={() => setApplied(d)} disabled={q.isFetching}>Run</Button>
        </div>
      </Panel>
      {q.error ? <ErrorBlock error={q.error} /> : !p ? <LoadingBlock height="h-48" /> : (
        <div className="space-y-4">
          {p.prob_first_payout < 0.01 && <div className="rounded-lg border border-down/40 bg-down/5 p-3 text-[12px] text-down">Almost no simulated account reached a payout. Under these rules this strategy is not expected to pay out.</div>}
          <KpiGrid>
            <KpiCard label="P(first payout)" value={pct(p.prob_first_payout)} tone="up" />
            <KpiCard label="P(second payout)" value={pct(p.prob_second_payout)} />
            <KpiCard label="P(third payout)" value={pct(p.prob_third_payout)} />
            <KpiCard label="Expected total payouts" value={money(p.expected_total_payouts)} sub={`trader share ${pct(p.profit_split, 0)}`} tone="up" />
            <KpiCard label="P(lose account after a withdrawal)" value={pct(p.prob_lose_account_after_withdrawal)} tone="down" sub={`${pct(p.prob_lose_account_given_withdrawal, 0)} of accounts that were paid`} />
            <KpiCard label="Median days to first payout" value={p.median_days_to_first_payout === null ? "–" : num(p.median_days_to_first_payout, 0)} sub={`avg ${num(p.expected_payout_count, 2)} payouts`} />
          </KpiGrid>
          <Panel title="Total payouts distribution" subtitle={`Trader share over ${p.horizon_days} trading days, all simulated accounts (many receive $0)`}>
            <Histogram hist={p.payout_total_hist} color="#f0b429" xFormat={(v) => `$${(v / 1000).toFixed(1)}k`} />
          </Panel>
        </div>
      )}
    </>
  );
}
