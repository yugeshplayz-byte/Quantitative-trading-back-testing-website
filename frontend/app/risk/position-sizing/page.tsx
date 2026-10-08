"use client";

import { useState } from "react";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { SimpleTable } from "@/components/tables/SimpleTable";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, NumberField, Select } from "@/components/ui/inputs";
import { ErrorBlock, LoadingBlock } from "@/components/ui/state";
import { money, num, pct, pctRaw } from "@/lib/format";
import { useBt, usePostQuery } from "@/lib/hooks";

interface Size {
  risk_budget: number; risk_per_contract: number; contracts: number; actual_risk: number; risk_pct_of_account: number;
  kelly_fraction: number | null; half_kelly_pct: number | null; point_value: number; tick_value: number;
  table: { stop_points: number; risk_per_contract: number; contracts: number; actual_risk: number }[];
}
interface Compare {
  models: Record<string, { final_balance: number; return_pct: number; max_drawdown: number; curve: number[] }>;
  win_rate: number; avg_win_r: number; avg_loss_r: number; kelly_fraction: number; trades: number;
}

export default function PositionSizingPage() {
  const { id, current } = useBt();
  const [d, setD] = useState({ symbol: "MNQ", balance: 50000, mode: "dollar", dollars: 150, pctRisk: 0.5, stop: 25 });
  const [applied, setApplied] = useState<typeof d | null>(d);
  const body = applied ? { symbol: applied.symbol, account_balance: applied.balance, risk_dollars: applied.mode === "dollar" ? applied.dollars : null, risk_pct: applied.mode === "pct" ? applied.pctRisk : null, stop_points: applied.stop } : null;
  const sz = usePostQuery<Size>("/risk/position-size", body);
  const [cmpIn, setCmpIn] = useState({ fixed: 150, pct: 0.5, contracts: 2 });
  const [cmpApplied, setCmpApplied] = useState<typeof cmpIn | null>(null);
  const cmp = usePostQuery<Compare>("/risk/sizing-comparison", cmpApplied && id ? { backtest_id: id, balance: current?.config.starting_balance ?? 50000, fixed_risk: cmpApplied.fixed, pct_risk: cmpApplied.pct, fixed_contracts: cmpApplied.contracts } : null);
  const set = (p: Partial<typeof d>) => setD({ ...d, ...p });
  const names = cmp.data ? Object.keys(cmp.data.models) : [];
  const n = cmp.data ? Math.max(...names.map((k) => cmp.data!.models[k].curve.length)) : 0;
  const rows = cmp.data ? Array.from({ length: n }, (_, i) => Object.fromEntries([["i", i], ...names.map((k) => [k, cmp.data!.models[k].curve[i] ?? null])])) : [];

  return (
    <>
      <PageHeader title="Position sizing" description="Convert a risk budget and a stop distance into a number of contracts, then see how different sizing rules would have changed this backtest's equity curve." />
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Contracts calculator">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <Field label="Symbol"><Select value={d.symbol} onChange={(e) => set({ symbol: e.target.value })}>{["MNQ", "NQ", "MES", "ES"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
            <NumberField label="Account balance ($)" value={d.balance} step={1000} min={1} onChange={(v) => set({ balance: v ?? 50000 })} />
            <NumberField label="Stop distance (points)" value={d.stop} step={1} min={0.25} onChange={(v) => set({ stop: v ?? 25 })} />
            <Field label="Risk by"><Select value={d.mode} onChange={(e) => set({ mode: e.target.value })}><option value="dollar">Fixed dollars</option><option value="pct">% of account</option></Select></Field>
            {d.mode === "dollar" ? <NumberField label="Risk per trade ($)" value={d.dollars} step={25} min={1} onChange={(v) => set({ dollars: v ?? 150 })} /> : <NumberField label="Risk per trade (%)" value={d.pctRisk} step={0.1} min={0.01} onChange={(v) => set({ pctRisk: v ?? 0.5 })} />}
            <div className="flex items-end"><Button variant="primary" onClick={() => setApplied(d)}>Calculate</Button></div>
          </div>
          {sz.error ? <div className="mt-3"><ErrorBlock error={sz.error} /></div> : sz.data && (
            <div className="mt-4 space-y-3">
              <KpiGrid className="xl:grid-cols-3">
                <KpiCard label="Contracts" value={String(sz.data.contracts)} tone={sz.data.contracts === 0 ? "down" : "neutral"} sub={sz.data.contracts === 0 ? "budget below one contract's risk" : undefined} />
                <KpiCard label="Actual risk" value={money(sz.data.actual_risk, 2)} sub={`${pctRaw(sz.data.risk_pct_of_account, 2)} of account`} />
                <KpiCard label="Risk per contract" value={money(sz.data.risk_per_contract, 2)} sub={`$${sz.data.point_value}/pt · $${sz.data.tick_value}/tick`} />
              </KpiGrid>
              <SimpleTable rows={sz.data.table} columns={[
                { key: "stop_points", header: "Stop (pts)", render: (r) => num(r.stop_points, 2) },
                { key: "risk_per_contract", header: "Risk / contract", align: "right", render: (r) => money(r.risk_per_contract, 2) },
                { key: "contracts", header: "Contracts", align: "right" },
                { key: "actual_risk", header: "Actual risk", align: "right", render: (r) => money(r.actual_risk, 2) },
              ]} />
            </div>
          )}
        </Panel>
        <Panel title="Sizing models on this backtest" subtitle={`Re-sizes the ${current?.trade_count ?? ""} historical trades by their R multiples`}>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <NumberField label="Fixed risk ($)" value={cmpIn.fixed} step={25} onChange={(v) => setCmpIn({ ...cmpIn, fixed: v ?? 150 })} />
            <NumberField label="Fixed % of equity" value={cmpIn.pct} step={0.1} onChange={(v) => setCmpIn({ ...cmpIn, pct: v ?? 0.5 })} />
            <NumberField label="Fixed contracts" value={cmpIn.contracts} step={1} min={1} onChange={(v) => setCmpIn({ ...cmpIn, contracts: Math.round(v ?? 2) })} />
            <div className="flex items-end"><Button variant="primary" onClick={() => setCmpApplied(cmpIn)} disabled={cmp.isFetching}>Compare</Button></div>
          </div>
          {cmpApplied && (cmp.error ? <div className="mt-3"><ErrorBlock error={cmp.error} /></div> : !cmp.data ? <LoadingBlock height="h-40" /> : (
            <div className="mt-4 space-y-3">
              <TimeSeriesChart data={rows} xKey="i" xFormat={(v) => String(v)} series={names.map((k) => ({ key: k, label: k }))} height={240} yFormat={(v) => `$${(v / 1000).toFixed(0)}k`} minTickGap={30} />
              <SimpleTable rows={names.map((k) => ({ name: k, ...cmp.data!.models[k] }))} columns={[
                { key: "name", header: "Model", className: "font-sans" },
                { key: "final_balance", header: "Final", align: "right", render: (r) => money(r.final_balance) },
                { key: "return_pct", header: "Return", align: "right", render: (r) => pctRaw(r.return_pct), cellClass: (r) => (r.return_pct >= 0 ? "text-up" : "text-down") },
                { key: "max_drawdown", header: "Max DD", align: "right", render: (r) => money(r.max_drawdown) },
              ]} />
              <p className="text-[11px] text-muted">Win rate {pct(cmp.data.win_rate, 0)} · avg win {num(cmp.data.avg_win_r)}R · avg loss {num(cmp.data.avg_loss_r)}R.{cmp.data.kelly_fraction > 0 ? ` Full Kelly ≈ ${pct(cmp.data.kelly_fraction)} of equity - aggressive, because Kelly assumes the edge is known exactly (it never is).` : " Kelly fraction is zero or negative: the observed edge does not justify risking anything."}</p>
            </div>
          ))}
        </Panel>
      </div>
    </>
  );
}
