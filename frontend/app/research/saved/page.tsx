"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { ErrorBlock, Query, Spinner } from "@/components/ui/state";
import { apiDelete, apiPost } from "@/lib/api";
import { money } from "@/lib/format";
import { useApiQuery, useBt } from "@/lib/hooks";
import { usePropRules } from "@/lib/prop";
import type { BacktestResult, StrategyPreset } from "@/lib/types";

export default function SavedPage() {
  const q = useApiQuery<StrategyPreset[]>("/strategies");
  const qc = useQueryClient();
  const router = useRouter();
  const { setId } = useBt();
  const [, setRules] = usePropRules();
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState<unknown>(null);

  const run = async (p: StrategyPreset) => {
    setBusy(p.id ?? -1);
    setErr(null);
    try {
      const res = await apiPost<BacktestResult>("/backtest/run", { config: p.config, name: p.name, notes: `Run from saved strategy "${p.name}"`, version: "v1", tags: [] });
      await qc.invalidateQueries({ queryKey: ["backtests"] });
      setId(res.id);
      router.push("/");
    } catch (e) { setErr(e); } finally { setBusy(null); }
  };
  const remove = async (p: StrategyPreset) => {
    if (!window.confirm(`Delete saved strategy "${p.name}"?`)) return;
    await apiDelete(`/strategies/${p.id}`);
    await qc.invalidateQueries({ queryKey: ["api", "/strategies"] });
  };

  return (
    <>
      <PageHeader title="Saved strategies" description="Presets bundle strategy parameters, risk, execution and (optionally) prop-firm settings. Save presets from the Configuration page; run or load them here." />
      {err ? <div className="mb-3"><ErrorBlock error={err} /></div> : null}
      <Query q={q}>
        {(rows) => (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {rows.map((p) => {
              const c = p.config;
              return (
                <Panel key={p.id} title={p.name} subtitle={p.description || undefined} actions={<Badge>{c.symbol}</Badge>}>
                  <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[12px]">
                    <dt className="text-muted">Strategy</dt><dd className="num truncate text-right">{c.strategy}</dd>
                    <dt className="text-muted">Parameters</dt><dd className="num truncate text-right">{Object.keys(c.params).length ? Object.entries(c.params).map(([k, v]) => `${k}=${v}`).join(" ") : "defaults"}</dd>
                    <dt className="text-muted">Stop / target</dt><dd className="num text-right">{c.stop.type} {c.stop.value} / {c.target.type} {c.target.value}</dd>
                    <dt className="text-muted">Risk</dt><dd className="num text-right">{c.risk.sizing_mode === "fixed_dollar" ? money(c.risk.risk_dollars) : c.risk.sizing_mode === "percent" ? `${c.risk.risk_pct}%` : `${c.risk.contracts} ct`}, daily limit {c.risk.daily_loss_limit ? money(c.risk.daily_loss_limit) : "none"}</dd>
                    <dt className="text-muted">Costs</dt><dd className="num text-right">{c.execution.slippage_ticks}t slip · ${(c.execution.commission_per_side + c.execution.exchange_fee_per_side).toFixed(2)}/side</dd>
                    <dt className="text-muted">Market</dt><dd className="num text-right">{c.data_model === "structured" ? "engineered" : "random walk"}</dd>
                    {p.prop_rules && (<><dt className="text-muted">Prop rules</dt><dd className="num text-right">{p.prop_rules.name}</dd></>)}
                  </dl>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button size="sm" variant="primary" onClick={() => run(p)} disabled={busy !== null}>{busy === p.id && <Spinner className="text-white" />} Run backtest</Button>
                    {p.prop_rules && <Button size="sm" onClick={() => setRules(p.prop_rules!)}>Use prop rules</Button>}
                    <Button size="sm" variant="danger" onClick={() => remove(p)}>Delete</Button>
                  </div>
                </Panel>
              );
            })}
          </div>
        )}
      </Query>
    </>
  );
}
