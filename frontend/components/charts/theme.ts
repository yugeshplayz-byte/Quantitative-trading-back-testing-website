export const C = {
  up: "#2ebd85",
  down: "#f6465d",
  accent: "#4c8dff",
  warn: "#f0b429",
  purple: "#a371f7",
  teal: "#39c5cf",
  orange: "#f08a4b",
  grid: "#1c2431",
  axis: "#8592a6",
  text: "#d5dbe6",
  surface: "#151b25",
  border: "#232c3a",
};

export const SERIES_COLORS = [C.accent, C.warn, C.purple, C.teal, C.orange, C.up, C.down, "#e879b9"];

export const tooltipStyle = {
  contentStyle: {
    background: C.surface,
    border: `1px solid ${C.border}`,
    borderRadius: 6,
    fontSize: 11,
    padding: "6px 8px",
    color: C.text,
  },
  labelStyle: { color: C.axis, marginBottom: 2 },
  itemStyle: { padding: 0 },
  cursor: { stroke: C.axis, strokeDasharray: "3 3" },
};

export const axisProps = {
  stroke: C.border,
  tick: { fill: C.axis, fontSize: 11 },
  tickLine: false,
} as const;
