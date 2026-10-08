"use client";

import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisProps, C, SERIES_COLORS, tooltipStyle } from "./theme";

export interface Series {
  key: string;
  label: string;
  color?: string;
  kind?: "line" | "area" | "step";
  dashed?: boolean;
  width?: number;
}

type Row = Record<string, number | string | null | undefined>;

export function TimeSeriesChart({
  data,
  xKey = "date",
  series,
  height = 280,
  yFormat = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: 0 }),
  xFormat = (v: string) => v.slice(0, 7),
  referenceY,
  legend = true,
  minTickGap = 50,
  domain,
  zone,
}: {
  data: Row[];
  xKey?: string;
  series: Series[];
  height?: number;
  yFormat?: (v: number) => string;
  xFormat?: (v: string) => string;
  referenceY?: number;
  legend?: boolean;
  minTickGap?: number;
  domain?: [number | "auto" | "dataMin" | "dataMax", number | "auto" | "dataMin" | "dataMax"];
  /** Highlighted x-range (e.g. the best risk-per-trade zone); values must exist on the x axis. */
  zone?: [number | string, number | string] | null;
}) {
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
          <defs>
            {series.map((s, i) => {
              const color = s.color ?? SERIES_COLORS[i % SERIES_COLORS.length];
              return (
                <linearGradient key={s.key} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={color} stopOpacity={0.02} />
                </linearGradient>
              );
            })}
          </defs>
          <CartesianGrid stroke={C.grid} vertical={false} />
          <XAxis dataKey={xKey} {...axisProps} tickFormatter={xFormat} minTickGap={minTickGap} />
          <YAxis {...axisProps} tickFormatter={yFormat} width={64} domain={domain ?? ["auto", "auto"]} />
          <Tooltip
            {...tooltipStyle}
            formatter={(v: unknown, name: unknown) => [typeof v === "number" ? yFormat(v) : String(v), String(name)]}
          />
          {legend && series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
          {referenceY !== undefined && <ReferenceLine y={referenceY} stroke={C.axis} strokeDasharray="4 4" />}
          {zone && <ReferenceArea x1={zone[0]} x2={zone[1]} fill={C.up} fillOpacity={0.12} stroke={C.up} strokeOpacity={0.3} />}
          {series.map((s, i) => {
            const color = s.color ?? SERIES_COLORS[i % SERIES_COLORS.length];
            return s.kind === "area" ? (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={color}
                strokeWidth={s.width ?? 1.5}
                fill={`url(#grad-${s.key})`}
                dot={false}
                isAnimationActive={false}
              />
            ) : (
              <Line
                key={s.key}
                type={s.kind === "step" ? "stepAfter" : "monotone"}
                dataKey={s.key}
                name={s.label}
                stroke={color}
                strokeWidth={s.width ?? 1.5}
                strokeDasharray={s.dashed ? "5 4" : undefined}
                dot={false}
                isAnimationActive={false}
              />
            );
          })}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
