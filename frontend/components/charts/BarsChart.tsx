"use client";

import { Bar, BarChart, CartesianGrid, Cell, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisProps, C, SERIES_COLORS, tooltipStyle } from "./theme";

type Row = Record<string, number | string | null | undefined>;

export interface BarSeries {
  key: string;
  label: string;
  color?: string;
  /** Color each bar green/red by its sign instead of a fixed color. */
  bySign?: boolean;
}

export function BarsChart({
  data,
  xKey,
  bars,
  height = 240,
  yFormat = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: 0 }),
  xFormat,
  stacked = false,
  layout = "horizontal",
}: {
  data: Row[];
  xKey: string;
  bars: BarSeries[];
  height?: number;
  yFormat?: (v: number) => string;
  xFormat?: (v: string) => string;
  stacked?: boolean;
  layout?: "horizontal" | "vertical";
}) {
  const vertical = layout === "vertical";
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout={layout} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={C.grid} vertical={vertical} horizontal={!vertical} />
          {vertical ? (
            <>
              <XAxis type="number" {...axisProps} tickFormatter={yFormat} />
              <YAxis type="category" dataKey={xKey} {...axisProps} width={90} />
            </>
          ) : (
            <>
              <XAxis dataKey={xKey} {...axisProps} tickFormatter={xFormat} interval="preserveStartEnd" minTickGap={14} />
              <YAxis {...axisProps} tickFormatter={yFormat} width={60} />
            </>
          )}
          <Tooltip
            {...tooltipStyle}
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            formatter={(v: unknown, name: unknown) => [typeof v === "number" ? yFormat(v) : String(v), String(name)]}
          />
          {bars.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
          <ReferenceLine {...(vertical ? { x: 0 } : { y: 0 })} stroke={C.axis} />
          {bars.map((b, bi) => (
            <Bar
              key={b.key}
              dataKey={b.key}
              name={b.label}
              fill={b.color ?? SERIES_COLORS[bi % SERIES_COLORS.length]}
              stackId={stacked ? "s" : undefined}
              isAnimationActive={false}
              radius={[2, 2, 0, 0]}
            >
              {b.bySign &&
                data.map((d, i) => <Cell key={i} fill={Number(d[b.key]) >= 0 ? C.up : C.down} />)}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
