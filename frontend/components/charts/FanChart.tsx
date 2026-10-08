"use client";

import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MonteCarloResult } from "@/lib/types";
import { axisProps, C, tooltipStyle } from "./theme";

/** Monte Carlo equity fan: 5-95% and 25-75% bands, median, and a handful of sample paths. */
export function FanChart({
  result,
  height = 340,
  showPaths = true,
  startingBalance,
  ruinLevel,
  targetLevel,
}: {
  result: MonteCarloResult;
  height?: number;
  showPaths?: boolean;
  startingBalance: number;
  ruinLevel?: number | null;
  targetLevel?: number | null;
}) {
  const { fan, sample_paths } = result;
  const paths = showPaths ? sample_paths.slice(0, 12) : [];
  const data = fan.steps.map((s, i) => {
    const row: Record<string, number | number[]> = {
      step: s,
      band90: [fan.p5[i], fan.p95[i]],
      band50: [fan.p25[i], fan.p75[i]],
      median: fan.p50[i],
    };
    paths.forEach((p, k) => (row[`p${k}`] = p[i]));
    return row;
  });
  const fmt = (v: number) => `$${(v / 1000).toFixed(0)}k`;
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={C.grid} vertical={false} />
          <XAxis dataKey="step" {...axisProps} label={{ value: "trades", position: "insideBottomRight", offset: -2, fill: C.axis, fontSize: 10 }} />
          <YAxis {...axisProps} tickFormatter={fmt} width={52} domain={["auto", "auto"]} />
          <Tooltip
            {...tooltipStyle}
            formatter={(v: unknown, name: unknown) => [
              Array.isArray(v) ? `${fmt(v[0])} – ${fmt(v[1])}` : typeof v === "number" ? `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}` : String(v),
              String(name),
            ]}
          />
          <Area dataKey="band90" name="5–95%" stroke="none" fill={C.accent} fillOpacity={0.14} isAnimationActive={false} />
          <Area dataKey="band50" name="25–75%" stroke="none" fill={C.accent} fillOpacity={0.24} isAnimationActive={false} />
          {paths.map((_, k) => (
            <Line key={k} dataKey={`p${k}`} stroke={C.axis} strokeOpacity={0.35} strokeWidth={0.8} dot={false} isAnimationActive={false} legendType="none" name={`path ${k + 1}`} />
          ))}
          <Line dataKey="median" name="median" stroke={C.warn} strokeWidth={2} dot={false} isAnimationActive={false} />
          <ReferenceLine y={startingBalance} stroke={C.axis} strokeDasharray="4 4" />
          {ruinLevel ? <ReferenceLine y={ruinLevel} stroke={C.down} strokeDasharray="4 3" label={{ value: "ruin", fill: C.down, fontSize: 10, position: "insideTopLeft" }} /> : null}
          {targetLevel ? <ReferenceLine y={targetLevel} stroke={C.up} strokeDasharray="4 3" label={{ value: "target", fill: C.up, fontSize: 10, position: "insideBottomLeft" }} /> : null}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
