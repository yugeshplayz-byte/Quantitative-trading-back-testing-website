"use client";

import { Panel } from "@/components/ui/card";
import { Field, Input, NumberField, Select, ToggleField } from "@/components/ui/inputs";
import { useApiQuery } from "@/lib/hooks";
import { DEFAULT_RULES, usePropRules } from "@/lib/prop";
import type { DrawdownType, PropFirmRules } from "@/lib/types";

interface Template { name: string; rules: Partial<PropFirmRules> }

/** The configurable prop-firm rule engine inputs. Shared and persisted across all prop pages. */
export function RulesPanel({ showPayout = false }: { showPayout?: boolean }) {
  const [r, setR] = usePropRules();
  const templates = useApiQuery<Template[]>("/prop-firm/templates");
  const set = <K extends keyof PropFirmRules>(k: K, v: PropFirmRules[K]) => setR({ ...r, [k]: v });
  const setPayout = (patch: Partial<PropFirmRules["payout"]>) => setR({ ...r, payout: { ...r.payout, ...patch } });

  return (
    <Panel
      title="Prop firm rules"
      subtitle="Fully configurable - enter the rules from your firm's current terms. Saved in this browser."
      className="mb-4"
      actions={
        <Select
          value=""
          className="h-7 w-52"
          onChange={(e) => {
            const t = templates.data?.find((x) => x.name === e.target.value);
            if (t) setR({ ...DEFAULT_RULES, ...t.rules, name: t.name, payout: DEFAULT_RULES.payout });
          }}
        >
          <option value="">Load generic template…</option>
          {templates.data?.map((t) => <option key={t.name}>{t.name}</option>)}
        </Select>
      }
    >
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
        <Field label="Rule set name"><Input className="font-sans" value={r.name} onChange={(e) => set("name", e.target.value)} /></Field>
        <NumberField label="Starting balance ($)" value={r.starting_balance} step={5000} min={1000} onChange={(v) => set("starting_balance", v ?? 50000)} />
        <NumberField label="Profit target ($)" value={r.profit_target} step={250} min={1} onChange={(v) => set("profit_target", v ?? 3000)} />
        <NumberField label="Maximum drawdown ($)" value={r.max_drawdown} step={250} min={1} onChange={(v) => set("max_drawdown", v ?? 2500)} />
        <NumberField label="Daily loss limit ($)" value={r.daily_loss_limit} nullable step={100} onChange={(v) => set("daily_loss_limit", v)} hint="Blank = none" />
        <NumberField label="Max contracts" value={r.max_contracts} min={1} onChange={(v) => set("max_contracts", Math.round(v ?? 1))} />
        <Field label="Drawdown type">
          <Select value={r.drawdown_type} onChange={(e) => set("drawdown_type", e.target.value as DrawdownType)}>
            <option value="static">Static</option>
            <option value="eod_trailing">End-of-day trailing</option>
            <option value="intraday_trailing">Intraday trailing</option>
          </Select>
        </Field>
        <NumberField label="Min trading days" value={r.min_trading_days} min={0} onChange={(v) => set("min_trading_days", Math.round(v ?? 0))} />
        <NumberField label="Consistency: best day ≤ (% of profit)" value={r.consistency_pct} nullable step={5} min={1} max={100} onChange={(v) => set("consistency_pct", v)} hint="Blank = no rule" />
        <NumberField label="Min profitable days" value={r.min_profitable_days} min={0} onChange={(v) => set("min_profitable_days", Math.round(v ?? 0))} />
        <NumberField label="Profitable day ≥ ($)" value={r.min_profitable_day_amount} step={25} min={0} onChange={(v) => set("min_profitable_day_amount", v ?? 0)} />
        <NumberField label="Evaluation window (trading days)" value={r.max_evaluation_days} min={5} max={400} onChange={(v) => set("max_evaluation_days", Math.round(v ?? 90))} />
        <Field label="Trading hours start"><Input type="time" value={r.trading_start} onChange={(e) => set("trading_start", e.target.value)} /></Field>
        <Field label="Trading hours end"><Input type="time" value={r.trading_end} onChange={(e) => set("trading_end", e.target.value)} /></Field>
        <Field label="Forced liquidation"><Input type="time" value={r.liquidation_time} onChange={(e) => set("liquidation_time", e.target.value)} /></Field>
        <div className="col-span-2 md:col-span-2 xl:col-span-3">
          <ToggleField label="Trailing floor locks at starting balance" checked={r.trailing_locks_at_start} onChange={(v) => set("trailing_locks_at_start", v)} hint="Trailing drawdown stops rising once it reaches the starting balance" />
        </div>
      </div>
      {showPayout && (
        <div className="mt-4 border-t border-border pt-3">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">Payout rules</div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <NumberField label="Payout threshold (profit $)" value={r.payout.threshold} step={250} min={0} onChange={(v) => setPayout({ threshold: v ?? 0 })} />
            <NumberField label="Minimum balance after (profit $)" value={r.payout.min_balance} step={250} min={0} onChange={(v) => setPayout({ min_balance: v ?? 0 })} />
            <NumberField label="Max withdrawal ($)" value={r.payout.max_withdrawal} step={250} min={1} onChange={(v) => setPayout({ max_withdrawal: v ?? 5000 })} />
            <NumberField label="Withdrawal frequency (trading days)" value={r.payout.frequency_days} min={1} onChange={(v) => setPayout({ frequency_days: Math.round(v ?? 14) })} />
            <NumberField label="Profit split (trader share, 0–1)" value={r.payout.profit_split} step={0.05} min={0} max={1} onChange={(v) => setPayout({ profit_split: v ?? 0.9 })} />
          </div>
        </div>
      )}
      <p className="mt-3 text-[11px] text-muted">Day-level model: each day&apos;s intraday low/high comes from the trades&apos; closed P&amp;L extended by their recorded MAE/MFE. Intraday trailing assumes the high prints before the low (worst case). Check your firm&apos;s exact wording for unrealised-profit and liquidation rules.</p>
    </Panel>
  );
}
