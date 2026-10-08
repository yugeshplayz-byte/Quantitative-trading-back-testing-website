"use client";

import { useState } from "react";
import { FanChart } from "@/components/charts/FanChart";
import { Histogram } from "@/components/charts/Histogram";
import { BarsChart } from "@/components/charts/BarsChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, NumberField, Select } from "@/components/ui/inputs";
import { ErrorBlock, LoadingBlock } from "@/components/ui/state";
import { int, money, num, pct } from "@/lib/format";
import { useBt, usePostQuery } from "@/lib/hooks";
import type { McMethod, MonteCarloConfig, MonteCarloResult } from "@/lib/types";

type Draft = Omit<MonteCarloConfig, "backtest_id" | "starting_balance">;
const DEFAULT: Draft = { simulations: 2000, trades: 250, risk_per_trade: null, seed: 7, method: "bootstrap", block_size: 5, ruin_drawdown: null, target_profit: null };

export default function MonteCarloPage() {
  const { id, current } = useBt();
  const balance = current?.config.starting_balance ?? 50000;
  const [draft, setDraft] = useState<Draft>(DEFAULT);
  const [applied, setApplied] = useState<Draft>(DEFAULT);
  const body = id ? { ...applied, backtest_id: id, starting_balance: balance } : null;
  const q = usePostQuery<MonteCarloResult>("/monte-carlo", body);
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const s = q.data?.summary;

  return (
    <>
      <PageHeader
        title="Monte Carlo simulation"
        description="Resamples this backtest's trades to show how much path luck matters: the spread of ending balances, drawdowns and losing streaks you could have experienced with the SAME edge. It cannot tell you whether the edge itself is real."
      />
      <Panel title="Inputs" className="mb-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
          <NumberField label="Simulations" value={draft.simulations} step={500} min={100} max={20000} onChange={(v) => set("simulations", Math.round(v ?? 2000))} />
          <NumberField label="Trades per path" value={draft.trades} step={25} min={10} max={5000} onChange={(v) => set("trades", Math.round(v ?? 250))} />
          <NumberField label="Risk per trade ($)" value={draft.risk_per_trade} nullable step={25} min={1} onChange={(v) => set("risk_per_trade", v)} hint="Blank = backtest's own size" />
          <NumberField label="Random seed" value={draft.seed} step={1} onChange={(v) => set("seed", Math.round(v ?? 7))} />
          <Field label="Simulation type">
            <Select value={draft.method} onChange={(e) => set("method", e.target.value as McMethod)}>
              <option value="shuffle">Trade reshuffling</option>
              <option value="bootstrap">Bootstrap sampling</option>
              <option value="block_bootstrap">Block bootstrap</option>
            </Select>
          </Field>
          <NumberField label="Block size" value={draft.block_size} min={2} max={100} onChange={(v) => set("block_size", Math.round(v ?? 5))} hint="Block bootstrap only" />
          <NumberField label="Ruin = lose ($)" value={draft.ruin_drawdown} nullable step={500} onChange={(v) => set("ruin_drawdown", v)} hint="Blank = 20% of balance" />
          <NumberField label="Target profit ($)" value={draft.target_profit} nullable step={500} onChange={(v) => set("target_profit", v)} hint="Blank = 10% of balance" />
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Button variant="primary" onClick={() => setApplied(draft)} disabled={q.isFetching}>Run simulation</Button>
          <span className="text-[11px] text-muted">Starting balance {money(balance)} · same seed always gives the same result.</span>
        </div>
      </Panel>

      {q.error ? <ErrorBlock error={q.error} /> : !q.data || !s ? <LoadingBlock label="Simulating…" height="h-64" /> : (
        <div className="space-y-4">
          {s.risk_achievable === 0 && (
            <div className="rounded-lg border border-warn/40 bg-warn/5 p-3 text-[12px] text-warn">
              Risk per trade is below half the cost of one contract in this backtest ({money(s.contract_risk)}). Trades could not be sized that small, so this scaling is hypothetical.
            </div>
          )}
          <KpiGrid>
            <KpiCard label="Median ending balance" value={money(s.median_ending_balance)} sub={`${num(s.median_return_pct, 1)}% return`} tone={(s.median_ending_balance ?? 0) >= balance ? "up" : "down"} />
            <KpiCard label="5th pct ending" value={money(s.p5_ending_balance)} tone="down" hint="Only 5% of simulated paths ended lower" />
            <KpiCard label="95th pct ending" value={money(s.p95_ending_balance)} tone="up" />
            <KpiCard label="Median max drawdown" value={money(s.median_max_drawdown)} tone="down" />
            <KpiCard label="95th pct drawdown" value={money(s.p95_max_drawdown)} tone="down" hint="Plan for drawdowns this deep" />
            <KpiCard label="Probability of profit" value={pct(s.prob_profit)} tone={(s.prob_profit ?? 0) > 0.5 ? "up" : "down"} />
            <KpiCard label="Probability of ruin" value={pct(s.prob_ruin)} tone={(s.prob_ruin ?? 0) > 0.05 ? "down" : "neutral"} sub={`balance ≤ ${money(s.ruin_level)}`} />
            <KpiCard label="Probability of target" value={pct(s.prob_hit_target)} sub={`balance ≥ ${money(s.target_level)}`} />
            <KpiCard label="Expected longest losing streak" value={num(s.expected_longest_losing_streak, 1)} sub={`95th pct ${num(s.p95_longest_losing_streak, 0)}`} />
            <KpiCard label="Historical trades used" value={int(s.historical_trades)} />
            <KpiCard label="Risk scale" value={`${num(s.risk_scale)}×`} />
            <KpiCard label="Avg trade 95% CI" value={`${money(s.expectancy_ci95_low, 1)} to ${money(s.expectancy_ci95_high, 1)}`} hint="If this interval includes $0, the edge is unproven" tone={(s.expectancy_ci95_low ?? -1) > 0 ? "up" : "warn"} />
          </KpiGrid>
          <p className="rounded-md border border-border bg-surface px-3 py-2 text-[11.5px] text-muted">{q.data.caveat}</p>
          <Panel title="Equity paths" subtitle="Shaded: 5–95% and 25–75% of simulated paths · gold: median · grey: sample paths">
            <FanChart result={q.data} startingBalance={balance} ruinLevel={s.ruin_level} targetLevel={s.target_level} />
          </Panel>
          <div className="grid gap-4 xl:grid-cols-3">
            <Panel title="Ending balance"><Histogram hist={q.data.ending_hist} marker={balance} markerLabel="start" xFormat={(v) => `$${(v / 1000).toFixed(0)}k`} splitAt={balance} /></Panel>
            <Panel title="Maximum drawdown"><Histogram hist={q.data.drawdown_hist} color="#f6465d" xFormat={(v) => `$${(v / 1000).toFixed(1)}k`} /></Panel>
            <Panel title="Longest losing streak">
              <BarsChart data={q.data.streak_dist.lengths.map((l, i) => ({ length: l, p: q.data!.streak_dist.probability[i] * 100 }))} xKey="length" bars={[{ key: "p", label: "% of paths", color: "#f0b429" }]} height={220} yFormat={(v) => `${v.toFixed(0)}%`} />
            </Panel>
          </div>
        </div>
      )}
    </>
  );
}
