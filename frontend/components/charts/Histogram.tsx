"use client";

import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Hist } from "@/lib/types";
import { axisProps, C, tooltipStyle } from "./theme";

export function Histogram({
  hist,
  height = 220,
  color = C.accent,
  xFormat = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: 0 }),
  splitAt,
  marker,
  markerLabel,
  yLabel = "count",
}: {
  hist: Hist | { centers: number[]; counts: number[] };
  height?: number;
  color?: string;
  xFormat?: (v: number) => string;
  /** Bars below this x are drawn red and above green (e.g. 0 for P&L). */
  splitAt?: number;
  marker?: number;
  markerLabel?: string;
  yLabel?: string;
}) {
  const data = hist.centers.map((c, i) => ({ x: c, count: hist.counts[i] }));
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }} barCategoryGap={1}>
          <CartesianGrid stroke={C.grid} vertical={false} />
          <XAxis dataKey="x" {...axisProps} tickFormatter={xFormat} interval="preserveStartEnd" minTickGap={30} />
          <YAxis {...axisProps} width={42} />
          <Tooltip
            {...tooltipStyle}
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            labelFormatter={(l: unknown) => xFormat(Number(l))}
            formatter={(v: unknown) => [String(v), yLabel]}
          />
          {marker !== undefined && (
            <ReferenceLine x={nearest(data, marker)} stroke={C.warn} strokeDasharray="4 3" label={{ value: markerLabel ?? "", fill: C.warn, fontSize: 10, position: "top" }} />
          )}
          <Bar dataKey="count" isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell key={i} fill={splitAt === undefined ? color : d.x < splitAt ? C.down : C.up} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function nearest(data: { x: number }[], v: number): number {
  let best = data[0]?.x ?? 0;
  for (const d of data) if (Math.abs(d.x - v) < Math.abs(best - v)) best = d.x;
  return best;
}
