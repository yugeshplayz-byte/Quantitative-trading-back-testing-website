"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ALL_RISK_METRICS, RiskCurves } from "@/components/prop/RiskCurves";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Input, NumberField } from "@/components/ui/inputs";
import { ErrorBlock, LoadingBlock } from "@/components/ui/state";
import { useBt, usePostQuery } from "@/lib/hooks";
import type { RiskOptData } from "@/lib/types-api";
import { parseList } from "@/components/forms/ParamPicker";

export default function RiskOptimizationPage() {
  const { id, current } = useBt();
  const [d, setD] = useState({ account: current?.config.starting_balance ?? 50000, dd: 2500, risks: "50,75,100,125,150,175,200,250,300,400,500" });
  const [applied, setApplied] = useState<typeof d | null>(d);
  const q = usePostQuery<RiskOptData>("/risk/optimizer", applied && id ? { backtest_id: id, account_size: applied.account, max_drawdown: applied.dd, risks: parseList(applied.risks), simulations: 1500 } : null);
  return (
    <>
      <PageHeader title="Risk-per-trade optimisation" description="Sweeps risk per trade and simulates 60-day outcomes plus a trailing-drawdown account. Higher risk raises both reward AND failure odds; the green zone marks where expected payouts per attempt are within 10% of the best. If no level has a positive payout, the strategy has nothing to size." />
      <Panel title="Inputs" className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <NumberField label="Account size ($)" value={d.account} step={5000} min={1000} onChange={(v) => setD({ ...d, account: v ?? 50000 })} className="w-40" />
          <NumberField label="Allowed drawdown ($)" value={d.dd} step={250} min={100} onChange={(v) => setD({ ...d, dd: v ?? 2500 })} className="w-40" />
          <Field label="Risk levels ($)" className="w-96"><Input value={d.risks} onChange={(e) => setD({ ...d, risks: e.target.value })} /></Field>
          <Button variant="primary" onClick={() => setApplied(d)} disabled={q.isFetching}>Run sweep</Button>
        </div>
      </Panel>
      {q.error ? <ErrorBlock error={q.error} /> : !q.data ? <LoadingBlock label="Simulating each risk level…" height="h-48" /> : <RiskCurves data={q.data} metrics={ALL_RISK_METRICS} accountMetrics />}
    </>
  );
}
