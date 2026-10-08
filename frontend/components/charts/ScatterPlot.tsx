"use client";

import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis, Legend } from "recharts";
import { axisProps, C, SERIES_COLORS, tooltipStyle } from "./theme";

export interface Point {
  x: number;
  y: number;
  label?: string;
  [k: string]: unknown;
}
export interface Group {
  name: string;
  color?: string;
  points: Point[];
}

export function ScatterPlot({
  groups,
  height = 360,
  xLabel,
  yLabel,
  xFormat = (v: number) => v.toFixed(0),
  yFormat = (v: number) => v.toFixed(0),
  diagonal = false,
}: {
  groups: Group[];
  height?: number;
  xLabel: string;
  yLabel: string;
  xFormat?: (v: number) => string;
  yFormat?: (v: number) => string;
  diagonal?: boolean;
}) {
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 12, left: 4, bottom: 18 }}>
          <CartesianGrid stroke={C.grid} />
          <XAxis type="number" dataKey="x" name={xLabel} {...axisProps} tickFormatter={xFormat} label={{ value: xLabel, position: "insideBottom", offset: -10, fill: C.axis, fontSize: 11 }} />
          <YAxis type="number" dataKey="y" name={yLabel} {...axisProps} tickFormatter={yFormat} width={60} label={{ value: yLabel, angle: -90, position: "insideLeft", fill: C.axis, fontSize: 11 }} />
          <ZAxis range={[22, 22]} />
          {diagonal && <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1e5, y: 1e5 }]} stroke={C.axis} strokeDasharray="4 4" />}
          <Tooltip
            {...tooltipStyle}
            cursor={{ strokeDasharray: "3 3", stroke: C.axis }}
            formatter={(v: unknown, name: unknown) => [typeof v === "number" ? v.toFixed(1) : String(v), String(name)]}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {groups.map((g, i) => (
            <Scatter key={g.name} name={g.name} data={g.points} fill={g.color ?? SERIES_COLORS[i % SERIES_COLORS.length]} fillOpacity={0.65} isAnimationActive={false} />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
