"use client";

import { useState } from "react";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { NumberField } from "@/components/ui/inputs";
import { ErrorBlock, LoadingBlock } from "@/components/ui/state";
import { money, num, pct, signedMoney } from "@/lib/format";
import { useBt, usePostQuery } from "@/lib/hooks";

interface Ruin {
  result: { risk_of_ruin: number; drawdown_probability: number; survival_probability: number; monte_carlo_drawdown_probability: number; monte_carlo_survival_probability: number; expectancy_per_trade: number; std_per_trade: number; scale_applied: number; kelly_fraction: number | null };
  sensitivity: { risk_per_trade: number; risk_of_ruin: number; drawdown_probability: number }[];
}

export default function RiskOfRuinPage() {
  const { current } = useBt();
  const m = current?.metrics;
  const [d, setD] = useState({ account: 50000, dd: 2500, risk: null as number | null, win: 0.4, avgWin: 250, avgLoss: 100, n: 250 });
  const [applied, setApplied] = useState<typeof d | null>(d);
  const body = applied ? { account_size: applied.account, allowed_drawdown: applied.dd, risk_per_trade: applied.risk, win_rate: applied.win, avg_win: applied.avgWin, avg_loss: applied.avgLoss, n_trades: applied.n } : null;
  const q = usePostQuery<Ruin>("/risk-of-ruin", body);
  const r = q.data?.result;
  return (
    <>
      <PageHeader title="Risk of ruin" description="Probability of hitting your allowed drawdown, from win rate and average win/loss. Closed-form Brownian-motion approximation cross-checked by a seeded Bernoulli simulation. Inputs are only as good as your estimates - use the backtest's own numbers with care, since a lucky sample overstates the edge." />
      <Panel title="Inputs" className="mb-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
          <NumberField label="Account size ($)" value={d.account} step={1000} min={1} onChange={(v) => setD({ ...d, account: v ?? 50000 })} />
          <NumberField label="Allowed drawdown ($)" value={d.dd} step={250} min={1} onChange={(v) => setD({ ...d, dd: v ?? 2500 })} />
          <NumberField label="Risk per trade ($)" value={d.risk} nullable step={25} min={1} onChange={(v) => setD({ ...d, risk: v })} hint="Blank = outcomes as given" />
          <NumberField label="Win rate (0–1)" value={d.win} step={0.01} min={0} max={1} onChange={(v) => setD({ ...d, win: v ?? 0.4 })} />
          <NumberField label="Average win ($)" value={d.avgWin} step={10} min={0.01} onChange={(v) => setD({ ...d, avgWin: v ?? 250 })} />
          <NumberField label="Average loss ($)" value={d.avgLoss} step={10} min={0.01} onChange={(v) => setD({ ...d, avgLoss: v ?? 100 })} />
          <NumberField label="Number of trades" value={d.n} step={50} min={1} onChange={(v) => setD({ ...d, n: Math.round(v ?? 250) })} />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button variant="primary" onClick={() => setApplied(d)}>Calculate</Button>
          {m && <Button onClick={() => { const next = { ...d, win: Number(((m.win_rate as number) ?? 0.4).toFixed(3)), avgWin: Math.round((m.average_winner as number) ?? 250), avgLoss: Math.round(Math.abs((m.average_loser as number) ?? 100)) }; setD(next); setApplied(next); }}>Use this backtest&apos;s stats</Button>}
        </div>
      </Panel>
      {q.error ? <ErrorBlock error={q.error} /> : !r ? <LoadingBlock height="h-40" /> : (
        <div className="space-y-4">
          {r.expectancy_per_trade <= 0 && <div className="rounded-lg border border-down/40 bg-down/5 p-3 text-[12px] text-down">These inputs have zero or negative expectancy ({signedMoney(r.expectancy_per_trade, 2)} per trade): ruin is mathematically certain given enough trades.</div>}
          <KpiGrid>
            <KpiCard label="Risk of ruin (infinite horizon)" value={pct(r.risk_of_ruin)} tone={r.risk_of_ruin > 0.1 ? "down" : "up"} hint="Chance of EVER hitting the allowed drawdown" />
            <KpiCard label={`Drawdown probability (${applied?.n} trades)`} value={pct(r.drawdown_probability)} tone={r.drawdown_probability > 0.1 ? "down" : "up"} sub={`simulation ${pct(r.monte_carlo_drawdown_probability)}`} />
            <KpiCard label="Survival probability" value={pct(r.survival_probability)} sub={`simulation ${pct(r.monte_carlo_survival_probability)}`} tone="up" />
            <KpiCard label="Expectancy / trade" value={signedMoney(r.expectancy_per_trade, 2)} tone={r.expectancy_per_trade >= 0 ? "up" : "down"} />
            <KpiCard label="Std dev / trade" value={money(r.std_per_trade, 2)} />
            <KpiCard label="Kelly fraction" value={r.kelly_fraction === null ? "–" : pct(r.kelly_fraction)} />
          </KpiGrid>
          <Panel title="Risk of ruin vs risk per trade" subtitle={`Same win rate and win/loss ratio, scaled to each risk level (${money(applied?.dd)} drawdown allowed)`}>
            <TimeSeriesChart data={q.data!.sensitivity.map((s) => ({ x: s.risk_per_trade, ruin: s.risk_of_ruin * 100, dd: s.drawdown_probability * 100 }))} xKey="x" xFormat={(v) => `$${v}`} series={[{ key: "ruin", label: "Risk of ruin %", color: "#f6465d", width: 2 }, { key: "dd", label: `Drawdown prob. (${applied?.n} trades) %`, color: "#f0b429" }]} height={260} yFormat={(v) => `${v.toFixed(0)}%`} minTickGap={8} />
            <p className="mt-2 text-[11px] text-muted">Approximation notes: trade outcomes are treated as two-point (avg win / avg loss) and independent; real outcome distributions are fatter-tailed, so true ruin risk is usually higher. Scale applied to outcomes: {num(r.scale_applied)}×.</p>
          </Panel>
        </div>
      )}
    </>
  );
}
