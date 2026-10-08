"use client";

import { useState } from "react";
import { parseList } from "@/components/forms/ParamPicker";
import { PageHeader } from "@/components/layout/PageHeader";
import { ALL_RISK_METRICS, RiskCurves } from "@/components/prop/RiskCurves";
import { RulesPanel } from "@/components/prop/RulesForm";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/inputs";
import { ErrorBlock, LoadingBlock } from "@/components/ui/state";
import { useBt, usePostQuery } from "@/lib/hooks";
import { usePropRules } from "@/lib/prop";
import type { RiskOptData } from "@/lib/types-api";

export default function PropOptimizerPage() {
  const { id } = useBt();
  const [rules] = usePropRules();
  const [risks, setRisks] = useState("50,75,100,125,150,175,200,250,300,400,500");
  const [applied, setApplied] = useState<string | null>(risks);
  const q = usePostQuery<RiskOptData>("/prop-firm/optimizer", applied && id ? { backtest_id: id, rules, risks: parseList(applied), simulations: 1500 } : null);
  return (
    <>
      <PageHeader title="Prop risk optimiser" description="Plots risk per trade against pass probability, failure probability, days to pass, payout probability and expected payouts under YOUR rules. The green zone is where expected payout per evaluation attempt is within 10% of the best. More risk is not better: it speeds up passing and failing alike." />
      <RulesPanel showPayout />
      <Panel title="Risk levels" className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Risk per trade ($, comma-separated)" className="w-[28rem]"><Input value={risks} onChange={(e) => setRisks(e.target.value)} /></Field>
          <Button variant="primary" onClick={() => setApplied(risks)} disabled={q.isFetching}>Optimise</Button>
          <span className="text-[11px] text-muted">Each level runs thousands of simulated evaluations and funded accounts - about 10–30 seconds.</span>
        </div>
      </Panel>
      {q.error ? <ErrorBlock error={q.error} /> : !q.data ? <LoadingBlock label="Simulating each risk level…" height="h-48" /> : <RiskCurves data={q.data} metrics={ALL_RISK_METRICS.filter((m) => m.key !== "expected_return" && m.key !== "max_drawdown").concat([{ key: "payout_probability", title: "Payout probability", fmt: (v) => `${(v * 100).toFixed(0)}%`, color: "#2ebd85" }, { key: "funded_survival_90d", title: "Funded 90-day survival", fmt: (v) => `${(v * 100).toFixed(0)}%`, color: "#39c5cf" }])} />}
    </>
  );
}
