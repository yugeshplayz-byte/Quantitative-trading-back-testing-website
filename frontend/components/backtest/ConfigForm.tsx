"use client";

import { Panel } from "@/components/ui/card";
import { Field, Input, NumberField, Select, ToggleField } from "@/components/ui/inputs";
import type { BacktestConfig, Strategy } from "@/lib/types";
import type { DatasetReport } from "@/lib/types-api";

type Cfg = BacktestConfig;

export function ConfigForm({
  value,
  onChange,
  strategies,
  datasets = [],
}: {
  value: Cfg;
  onChange: (c: Cfg) => void;
  strategies: Strategy[];
  datasets?: DatasetReport[];
}) {
  const realForSymbol = datasets.find((d) => d.symbol === value.symbol);
  const set = <K extends keyof Cfg>(key: K, v: Cfg[K]) => onChange({ ...value, [key]: v });
  const nested = <K extends "trading" | "risk" | "stop" | "target" | "management" | "execution">(key: K, patch: Partial<Cfg[K]>) =>
    onChange({ ...value, [key]: { ...value[key], ...patch } });
  const strat = strategies.find((s) => s.key === value.strategy);
  const params = strat?.parameters ?? [];

  const pickStrategy = (key: string) => {
    const s = strategies.find((x) => x.key === key);
    onChange({ ...value, strategy: key, params: {}, symbol: (s?.default_symbol as Cfg["symbol"]) ?? value.symbol });
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
      <Panel title="General">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Strategy" className="col-span-2">
            <Select value={value.strategy} onChange={(e) => pickStrategy(e.target.value)}>
              {strategies.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.name}
                </option>
              ))}
            </Select>
          </Field>
          {strat && <p className="col-span-2 text-[11px] text-muted">{strat.description}</p>}
          <Field label="Symbol">
            <Select value={value.symbol} onChange={(e) => set("symbol", e.target.value as Cfg["symbol"])}>
              {["MNQ", "NQ", "MES", "ES"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </Select>
          </Field>
          <Field label="Timeframe">
            <Select value={value.timeframe} onChange={(e) => set("timeframe", e.target.value as Cfg["timeframe"])}>
              <option value="5m">5 minute</option>
              <option value="15m">15 minute</option>
            </Select>
          </Field>
          <Field label="Start date">
            <Input type="date" value={value.start_date} min="2022-06-01" max="2025-12-31" onChange={(e) => set("start_date", e.target.value)} />
          </Field>
          <Field label="End date">
            <Input type="date" value={value.end_date} min="2022-06-01" max="2025-12-31" onChange={(e) => set("end_date", e.target.value)} />
          </Field>
          <NumberField label="Starting balance ($)" value={value.starting_balance} step={1000} min={1000} onChange={(v) => set("starting_balance", v ?? 50000)} />
          <Field label="Trading session">
            <Select value={value.session} onChange={(e) => set("session", e.target.value as Cfg["session"])}>
              <option value="RTH">RTH 09:30–16:00 ET</option>
              <option value="ETH" disabled>
                ETH (needs overnight data)
              </option>
            </Select>
          </Field>
        </div>
      </Panel>

      <Panel title="Strategy parameters" subtitle="Defaults are conventional values - not tuned. Optimising them is in-sample.">
        {params.length === 0 ? (
          <p className="text-[12px] text-muted">This strategy exposes no parameters.</p>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {params.map((p) => (
              <NumberField
                key={p.key}
                label={p.label}
                value={value.params[p.key] ?? p.default}
                step={p.step}
                min={p.min}
                max={p.max}
                hint={`default ${p.default} · range ${p.min}–${p.max}`}
                onChange={(v) => set("params", { ...value.params, [p.key]: v ?? p.default })}
              />
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Data" subtitle="Only real data can inform a decision to trade a strategy.">
        <div className="grid grid-cols-2 gap-3">
          <Field
            label="Market data"
            className="col-span-2"
            hint={{
              random_walk: "Synthetic, no exploitable structure: an honest strategy should NOT make money here.",
              structured: "Synthetic with engineered structure, for platform validation only - says nothing about real markets.",
              real: "Your own CSV bars from backend/data/real (see docs/REAL_DATA.md). Check the quality report below.",
            }[value.data_model]}
          >
            <Select value={value.data_model} onChange={(e) => set("data_model", e.target.value as Cfg["data_model"])}>
              <option value="real" disabled={!realForSymbol}>
                Real data (your CSV){realForSymbol ? "" : ` - no ${value.symbol} file found`}
              </option>
              <option value="random_walk">Synthetic random walk (demo, no edge)</option>
              <option value="structured">Synthetic engineered-edge (validation only)</option>
            </Select>
          </Field>
          {value.data_model !== "real" && (
            <NumberField label="Data seed" value={value.seed} step={1} onChange={(v) => set("seed", Math.round(v ?? 42))} hint="Same seed = identical market" />
          )}
        </div>
        {value.data_model === "real" && realForSymbol && (
          <div className="mt-3 space-y-1.5 rounded-md border border-border p-2.5 text-[11.5px]">
            <div className="font-semibold">
              {realForSymbol.files.join(", ")} · {realForSymbol.bars.toLocaleString()} bars · {realForSymbol.days} days · {realForSymbol.start} → {realForSymbol.end}
            </div>
            {realForSymbol.issues.length === 0 && <div className="text-up">No data-quality issues found.</div>}
            {realForSymbol.issues.map((i, k) => (
              <div key={k} className={i.severity === "error" ? "text-down" : i.severity === "warning" ? "text-warn" : "text-muted"}>
                {i.severity.toUpperCase()}: {i.message}
              </div>
            ))}
          </div>
        )}
        {!realForSymbol && (
          <p className="mt-3 text-[11px] text-muted">No real {value.symbol} data found. Put <code className="num">{value.symbol}.csv</code> in <code className="num">backend/data/real/</code> to enable it.</p>
        )}
      </Panel>

      <Panel title="Trading">
        <div className="grid grid-cols-2 gap-3">
          <ToggleField label="Long enabled" checked={value.trading.long_enabled} onChange={(v) => nested("trading", { long_enabled: v })} />
          <ToggleField label="Short enabled" checked={value.trading.short_enabled} onChange={(v) => nested("trading", { short_enabled: v })} />
          <NumberField label="Max trades per day" value={value.trading.max_trades_per_day} min={1} onChange={(v) => nested("trading", { max_trades_per_day: Math.round(v ?? 1) })} />
          <NumberField label="Max contracts" value={value.trading.max_contracts} min={1} onChange={(v) => nested("trading", { max_contracts: Math.round(v ?? 1) })} />
          <NumberField label="Entry delay (bars)" value={value.trading.entry_delay_bars} min={0} max={10} hint="Extra bars between signal and fill" onChange={(v) => nested("trading", { entry_delay_bars: Math.round(v ?? 0) })} />
          <NumberField label="Exit delay (bars)" value={value.trading.exit_delay_bars} min={0} max={10} hint="Delays signal-based exits" onChange={(v) => nested("trading", { exit_delay_bars: Math.round(v ?? 0) })} />
        </div>
      </Panel>

      <Panel title="Risk">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Position sizing" className="col-span-2">
            <Select value={value.risk.sizing_mode} onChange={(e) => nested("risk", { sizing_mode: e.target.value as Cfg["risk"]["sizing_mode"] })}>
              <option value="fixed_contracts">Fixed contracts</option>
              <option value="fixed_dollar">Fixed-dollar risk</option>
              <option value="percent">Percentage risk</option>
            </Select>
          </Field>
          {value.risk.sizing_mode === "fixed_contracts" && <NumberField label="Contracts" value={value.risk.contracts} min={1} onChange={(v) => nested("risk", { contracts: Math.round(v ?? 1) })} />}
          {value.risk.sizing_mode === "fixed_dollar" && <NumberField label="Risk per trade ($)" value={value.risk.risk_dollars} step={25} min={1} onChange={(v) => nested("risk", { risk_dollars: v ?? 100 })} hint="Trades needing >2x this for one contract are skipped" />}
          {value.risk.sizing_mode === "percent" && <NumberField label="Risk per trade (%)" value={value.risk.risk_pct} step={0.1} min={0.01} onChange={(v) => nested("risk", { risk_pct: v ?? 0.5 })} />}
          <NumberField label="Daily loss limit ($)" value={value.risk.daily_loss_limit} nullable step={100} onChange={(v) => nested("risk", { daily_loss_limit: v })} hint="Stops trading for the day after closed losses reach this" />
          <NumberField label="Max drawdown halt ($)" value={value.risk.max_drawdown} nullable step={500} onChange={(v) => nested("risk", { max_drawdown: v })} hint="Stops trading for good" />
          <NumberField label="Consecutive-loss limit" value={value.risk.consecutive_loss_limit} nullable min={1} onChange={(v) => nested("risk", { consecutive_loss_limit: v === null ? null : Math.round(v) })} hint="Pause for the rest of the day" />
        </div>
      </Panel>

      <Panel title="Stop loss">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Type">
            <Select value={value.stop.type} onChange={(e) => nested("stop", { type: e.target.value as Cfg["stop"]["type"] })}>
              <option value="atr">ATR multiple</option>
              <option value="fixed_point">Fixed points</option>
              <option value="fixed_dollar">Fixed dollars / contract</option>
              <option value="structure">Structure (swing high/low)</option>
            </Select>
          </Field>
          <NumberField
            label={{ atr: "ATR multiple", fixed_point: "Points", fixed_dollar: "Dollars", structure: "Buffer (ticks)" }[value.stop.type]}
            value={value.stop.value}
            step={0.25}
            min={0.01}
            onChange={(v) => nested("stop", { value: v ?? 1 })}
          />
        </div>
      </Panel>

      <Panel title="Target">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Type">
            <Select value={value.target.type} onChange={(e) => nested("target", { type: e.target.value as Cfg["target"]["type"] })}>
              <option value="risk_reward">Risk / reward</option>
              <option value="fixed_point">Fixed points</option>
              <option value="atr">ATR multiple</option>
            </Select>
          </Field>
          <NumberField label={{ risk_reward: "R multiple", fixed_point: "Points", atr: "ATR multiple" }[value.target.type]} value={value.target.value} step={0.25} min={0.01} onChange={(v) => nested("target", { value: v ?? 2 })} />
        </div>
      </Panel>

      <Panel title="Trade management">
        <div className="grid grid-cols-2 gap-3">
          <ToggleField label="Breakeven" checked={value.management.breakeven} onChange={(v) => nested("management", { breakeven: v })} />
          <NumberField label="Breakeven trigger (R)" value={value.management.breakeven_trigger_r} step={0.25} min={0.1} onChange={(v) => nested("management", { breakeven_trigger_r: v ?? 1 })} />
          <ToggleField label="Trailing stop" checked={value.management.trailing_stop} onChange={(v) => nested("management", { trailing_stop: v })} />
          <NumberField label="Trail distance (ATR x)" value={value.management.trail_atr_mult} step={0.25} min={0.1} onChange={(v) => nested("management", { trail_atr_mult: v ?? 1.5 })} />
          <ToggleField label="Partial profit" checked={value.management.partial_profit} onChange={(v) => nested("management", { partial_profit: v })} hint="Needs 2+ contracts" />
          <NumberField label="Partial at (R)" value={value.management.partial_at_r} step={0.25} min={0.1} onChange={(v) => nested("management", { partial_at_r: v ?? 1 })} />
          <NumberField label="Partial size (fraction)" value={value.management.partial_pct} step={0.05} min={0.05} max={0.95} onChange={(v) => nested("management", { partial_pct: v ?? 0.5 })} />
          <ToggleField label="Scaling out (2nd partial at 2x)" checked={value.management.scale_out} onChange={(v) => nested("management", { scale_out: v })} />
          <ToggleField label="Scaling in" checked={value.management.scale_in} onChange={(v) => nested("management", { scale_in: v })} />
          <NumberField label="Scale in at (R)" value={value.management.scale_in_at_r} step={0.25} min={0.1} onChange={(v) => nested("management", { scale_in_at_r: v ?? 0.75 })} />
        </div>
      </Panel>

      <Panel title="Execution costs" subtitle="Every fill pays these. Understating costs is the most common way backtests flatter strategies.">
        <div className="grid grid-cols-2 gap-3">
          <NumberField label="Commission / side ($)" value={value.execution.commission_per_side} step={0.05} min={0} onChange={(v) => nested("execution", { commission_per_side: v ?? 0 })} />
          <NumberField label="Exchange fees / side ($)" value={value.execution.exchange_fee_per_side} step={0.05} min={0} onChange={(v) => nested("execution", { exchange_fee_per_side: v ?? 0 })} />
          <NumberField label="Slippage (ticks)" value={value.execution.slippage_ticks} step={0.25} min={0} onChange={(v) => nested("execution", { slippage_ticks: v ?? 0 })} hint="Per market fill" />
          <NumberField label="Spread (ticks)" value={value.execution.spread_ticks} step={0.25} min={0} onChange={(v) => nested("execution", { spread_ticks: v ?? 0 })} hint="Half is paid per market fill" />
          <NumberField label="Latency (ms)" value={value.execution.latency_ms} step={100} min={0} onChange={(v) => nested("execution", { latency_ms: Math.round(v ?? 0) })} hint="Adds 1 tick of entry slip per 500ms" />
          <NumberField label="Limit fill needs trade-through (ticks)" value={value.execution.limit_through_ticks} step={0.25} min={0} onChange={(v) => nested("execution", { limit_through_ticks: v ?? 0 })} hint="0 = optimistic touch fills" />
        </div>
      </Panel>
    </div>
  );
}
