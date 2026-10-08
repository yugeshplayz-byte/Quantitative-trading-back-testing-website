"use client";

import { useState } from "react";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { RulesPanel } from "@/components/prop/RulesForm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { NumberField } from "@/components/ui/inputs";
import { ErrorBlock, LoadingBlock } from "@/components/ui/state";
import { money, signedMoney } from "@/lib/format";
import { useBt, usePostQuery } from "@/lib/hooks";
import { usePropRules } from "@/lib/prop";
import type { PropSimulationResult } from "@/lib/types";

export default function ChallengePage() {
  const { id } = useBt();
  const [rules] = usePropRules();
  const [startDay, setStartDay] = useState(0);
  const [applied, setApplied] = useState<{ start: number } | null>({ start: 0 });
  const q = usePostQuery<PropSimulationResult>("/prop-firm/simulate", applied && id ? { backtest_id: id, rules, start_day: applied.start } : null);
  const r = q.data;
  const tone = r?.status === "PASS" ? "up" : r?.status === "FAIL" ? "down" : "warn";
  return (
    <>
      <PageHeader title="Challenge simulator" description="Replays this backtest's actual trading days against your prop-firm rules and reports PASS, FAIL or ACTIVE with the exact reason. Change the start day to see how the same strategy fares if the evaluation had begun on a different date." />
      <RulesPanel />
      <Panel title="Run" className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <NumberField label="Start on trading day #" value={startDay} min={0} step={5} onChange={(v) => setStartDay(Math.max(0, Math.round(v ?? 0)))} className="w-48" hint="0 = first day of the backtest" />
          <Button variant="primary" onClick={() => setApplied({ start: startDay })}>Simulate challenge</Button>
        </div>
      </Panel>
      {q.error ? <ErrorBlock error={q.error} /> : !r ? <LoadingBlock height="h-40" /> : (
        <div className="space-y-4">
          <div className={"flex items-center gap-4 rounded-lg border p-4 " + (tone === "up" ? "border-up/40 bg-up/5" : tone === "down" ? "border-down/40 bg-down/5" : "border-warn/40 bg-warn/5")}>
            <Badge tone={tone === "up" ? "up" : tone === "down" ? "down" : "warn"} className="px-3 py-1.5 text-[15px]">{r.status}</Badge>
            <div>
              <div className="text-[13px] font-semibold">{r.reason}</div>
              {r.checks.map((c, i) => <div key={i} className="text-[11.5px] text-muted">{c.detail}</div>)}
            </div>
          </div>
          <KpiGrid>
            <KpiCard label="Profit vs target" value={signedMoney(r.profit)} sub={`target ${money(rules.profit_target)}`} tone={r.profit >= rules.profit_target ? "up" : r.profit >= 0 ? "warn" : "down"} />
            <KpiCard label="Final balance" value={money(r.final_balance)} />
            <KpiCard label="Peak balance" value={money(r.peak_balance)} />
            <KpiCard label="Max drawdown used" value={money(r.max_drawdown_used)} sub={`of ${money(rules.max_drawdown)}`} tone={r.max_drawdown_used >= rules.max_drawdown * 0.8 ? "down" : "neutral"} />
            <KpiCard label="Trading days" value={`${r.days_traded}`} sub={`${r.trading_days_elapsed} elapsed`} />
            <KpiCard label="Best day" value={money(r.best_day)} sub={r.profit > 0 ? `${((r.best_day / r.profit) * 100).toFixed(0)}% of profit` : undefined} />
          </KpiGrid>
          <Panel title="Balance vs drawdown floor" subtitle="The account fails if the balance touches the floor">
            <TimeSeriesChart data={r.equity_path as unknown as Record<string, number | string>[]} xKey="day" xFormat={(v) => String(v)} series={[{ key: "balance", label: "Balance", kind: "area", color: "#4c8dff" }, { key: "floor", label: "Drawdown floor", kind: "step", color: "#f6465d", dashed: true }]} height={300} yFormat={(v) => `$${(v / 1000).toFixed(1)}k`} minTickGap={25} />
          </Panel>
        </div>
      )}
    </>
  );
}
