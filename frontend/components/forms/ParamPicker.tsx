"use client";

import { Field, Input, Select } from "@/components/ui/inputs";
import type { ParameterSpec } from "@/lib/types";

export type ParamCatalog = { parameters: ParameterSpec[]; current: Record<string, number> };

export const parseList = (s: string): number[] | null => {
  const nums = s.split(/[,\s]+/).filter(Boolean).map(Number);
  return nums.length && nums.every(Number.isFinite) ? nums : null;
};

/** Pick parameters X and Y (strategy parameters + config knobs) and optionally override their value lists. */
export function ParamPicker({
  catalog,
  x,
  y,
  xs,
  ys,
  onChange,
}: {
  catalog: ParamCatalog;
  x: string;
  y: string;
  xs: string;
  ys: string;
  onChange: (p: { x?: string; y?: string; xs?: string; ys?: string }) => void;
}) {
  const label = (k: string) => catalog.parameters.find((p) => p.key === k)?.label ?? k;
  const opts = (
    <>
      <optgroup label="Strategy parameters">
        {catalog.parameters.filter((p) => p.group === "strategy").map((p) => (
          <option key={p.key} value={p.key}>{p.label}</option>
        ))}
      </optgroup>
      <optgroup label="Stops, targets, risk & costs">
        {catalog.parameters.filter((p) => p.group === "config").map((p) => (
          <option key={p.key} value={p.key}>{p.label}</option>
        ))}
      </optgroup>
    </>
  );
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Field label="Parameter X (columns)"><Select value={x} onChange={(e) => onChange({ x: e.target.value, xs: "" })}>{opts}</Select></Field>
      <Field label="Parameter Y (rows)"><Select value={y} onChange={(e) => onChange({ y: e.target.value, ys: "" })}>{opts}</Select></Field>
      <Field label={`${label(x)} values`} hint="Comma-separated, blank = auto (5 around current)"><Input value={xs} placeholder="auto" onChange={(e) => onChange({ xs: e.target.value })} /></Field>
      <Field label={`${label(y)} values`} hint="Comma-separated, blank = auto"><Input value={ys} placeholder="auto" onChange={(e) => onChange({ ys: e.target.value })} /></Field>
    </div>
  );
}

export const METRICS: { key: string; label: string }[] = [
  { key: "sharpe", label: "Sharpe ratio" },
  { key: "net_profit", label: "Net profit" },
  { key: "profit_factor", label: "Profit factor" },
  { key: "sortino", label: "Sortino ratio" },
  { key: "calmar", label: "Calmar ratio" },
  { key: "expectancy", label: "Expectancy" },
  { key: "max_drawdown", label: "Max drawdown (lower is better)" },
  { key: "prop_pass_probability", label: "Prop pass probability" },
];
