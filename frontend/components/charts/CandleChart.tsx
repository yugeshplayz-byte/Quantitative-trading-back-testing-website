"use client";

import { useEffect, useRef, useState } from "react";
import { C } from "./theme";

export interface CandleBar {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
  vwap: number;
  ema9: number;
  ema21: number;
  atr: number;
}
export interface Marker {
  time: string;
  price: number;
  kind: "scale_in" | "scale_out" | "breakeven" | "trail";
}

function useWidth(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement | null>(null);
  const [w, setW] = useState(900);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => setW(Math.max(320, Math.floor(entries[0].contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

/** Index of the last bar whose timestamp is <= t (ISO strings compare lexicographically). */
function indexAt(bars: CandleBar[], t: string): number {
  let idx = 0;
  for (let i = 0; i < bars.length; i++) if (bars[i].t <= t) idx = i;
  return idx;
}

const MARKER_STYLE: Record<Marker["kind"], { color: string; label: string }> = {
  scale_in: { color: C.accent, label: "Scale in" },
  scale_out: { color: C.up, label: "Scale out" },
  breakeven: { color: C.warn, label: "Breakeven" },
  trail: { color: C.orange, label: "Trail" },
};

export function CandleChart({
  bars,
  entryTime,
  exitTime,
  direction,
  levels,
  stopPath,
  events,
  show,
  height = 420,
}: {
  bars: CandleBar[];
  entryTime: string;
  exitTime: string;
  direction: "Long" | "Short";
  levels: { entry: number; exit: number; stop: number; target: number | null };
  stopPath: { t: string; price: number }[];
  events: Marker[];
  show: { vwap: boolean; ema: boolean };
  height?: number;
}) {
  const [ref, width] = useWidth();
  const [hover, setHover] = useState<number | null>(null);
  const padL = 8, padR = 62, padT = 12, padB = 24;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  const n = bars.length;
  if (n === 0) return null;

  const prices = bars.flatMap((b) => [b.h, b.l]).concat([levels.entry, levels.stop, levels.exit], levels.target ? [levels.target] : []);
  const lo = Math.min(...prices), hi = Math.max(...prices);
  const pad = (hi - lo) * 0.05 || 1;
  const y0 = lo - pad, y1 = hi + pad;
  const y = (p: number) => padT + (1 - (p - y0) / (y1 - y0)) * plotH;
  const step = plotW / n;
  const x = (i: number) => padL + step * (i + 0.5);
  const iEntry = indexAt(bars, entryTime), iExit = indexAt(bars, exitTime);
  const ticks = Array.from({ length: 6 }, (_, i) => y0 + ((y1 - y0) * i) / 5);
  const line = (key: "vwap" | "ema9" | "ema21") => bars.map((b, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(b[key]).toFixed(1)}`).join(" ");
  const stopSteps = stopPath.map((p) => ({ i: indexAt(bars, p.t), price: p.price }));
  const stopD = stopSteps
    .map((p, k) => {
      const xi = x(p.i);
      const prev = stopSteps[k - 1];
      return k === 0 ? `M${xi.toFixed(1)},${y(p.price).toFixed(1)}` : `L${xi.toFixed(1)},${y(prev.price).toFixed(1)} L${xi.toFixed(1)},${y(p.price).toFixed(1)}`;
    })
    .join(" ");
  const win = direction === "Long" ? levels.exit >= levels.entry : levels.exit <= levels.entry;
  const hb = hover !== null ? bars[hover] : null;
  const labelEvery = Math.max(1, Math.ceil(n / Math.max(4, Math.floor(plotW / 70))));

  return (
    <div ref={ref} className="relative w-full min-w-0 select-none overflow-hidden">
      <svg
        width={width}
        height={height}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const i = Math.floor((e.clientX - r.left - padL) / step);
          setHover(i >= 0 && i < n ? i : null);
        }}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((p, i) => (
          <g key={i}>
            <line x1={padL} x2={padL + plotW} y1={y(p)} y2={y(p)} stroke={C.grid} />
            <text x={padL + plotW + 6} y={y(p) + 3} fill={C.axis} fontSize={10} className="num">{p.toFixed(1)}</text>
          </g>
        ))}
        {bars.map((b, i) =>
          i % labelEvery === 0 ? (
            <text key={i} x={x(i)} y={height - 8} fill={C.axis} fontSize={10} textAnchor="middle" className="num">{b.t.slice(11, 16)}</text>
          ) : null,
        )}
        {/* shaded trade span */}
        <rect x={x(iEntry) - step / 2} y={padT} width={Math.max(step, x(iExit) - x(iEntry) + step)} height={plotH} fill={win ? C.up : C.down} opacity={0.06} />
        {/* levels */}
        {levels.target !== null && <Level y={y(levels.target)} x1={padL} x2={padL + plotW} color={C.up} label={`T ${levels.target.toFixed(2)}`} />}
        <Level y={y(levels.entry)} x1={padL} x2={padL + plotW} color={C.accent} label={`E ${levels.entry.toFixed(2)}`} />
        <path d={stopD} fill="none" stroke={C.down} strokeWidth={1.2} strokeDasharray="5 3" />
        <text x={padL + plotW + 6} y={y(stopPath[stopPath.length - 1]?.price ?? levels.stop) - 4} fill={C.down} fontSize={10} className="num">stop</text>
        {show.vwap && <path d={line("vwap")} fill="none" stroke={C.purple} strokeWidth={1.2} />}
        {show.ema && <path d={line("ema9")} fill="none" stroke={C.accent} strokeWidth={1} opacity={0.9} />}
        {show.ema && <path d={line("ema21")} fill="none" stroke={C.warn} strokeWidth={1} opacity={0.9} />}
        {/* candles */}
        {bars.map((b, i) => {
          const up = b.c >= b.o;
          const col = up ? C.up : C.down;
          return (
            <g key={i}>
              <line x1={x(i)} x2={x(i)} y1={y(b.h)} y2={y(b.l)} stroke={col} />
              <rect x={x(i) - step * 0.33} y={Math.min(y(b.o), y(b.c))} width={step * 0.66} height={Math.max(1, Math.abs(y(b.o) - y(b.c)))} fill={col} />
            </g>
          );
        })}
        {/* entry / exit */}
        <Arrow cx={x(iEntry)} cy={y(levels.entry)} dir={direction === "Long" ? "up" : "down"} color={C.accent} />
        <Arrow cx={x(iExit)} cy={y(levels.exit)} dir={direction === "Long" ? "down" : "up"} color={win ? C.up : C.down} />
        {events.map((ev, k) => {
          const st = MARKER_STYLE[ev.kind];
          const cx = x(indexAt(bars, ev.time)), cy = y(ev.price);
          return (
            <g key={k}>
              <rect x={cx - 4} y={cy - 4} width={8} height={8} fill={st.color} transform={`rotate(45 ${cx} ${cy})`} />
              <title>{`${st.label} @ ${ev.price}`}</title>
            </g>
          );
        })}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={padT} y2={padT + plotH} stroke={C.axis} strokeDasharray="3 3" />}
      </svg>
      {hb && (
        <div className="num pointer-events-none absolute left-2 top-1 rounded border border-border bg-surface-2/90 px-2 py-1 text-[10.5px]">
          {hb.t.slice(0, 16).replace("T", " ")} · O {hb.o.toFixed(2)} H {hb.h.toFixed(2)} L {hb.l.toFixed(2)} C {hb.c.toFixed(2)} · VWAP {hb.vwap.toFixed(2)} · ATR {hb.atr.toFixed(2)}
        </div>
      )}
    </div>
  );
}

function Level({ y, x1, x2, color, label }: { y: number; x1: number; x2: number; color: string; label: string }) {
  return (
    <g>
      <line x1={x1} x2={x2} y1={y} y2={y} stroke={color} strokeWidth={1} strokeDasharray="4 3" opacity={0.85} />
      <text x={x2 + 6} y={y + 3} fill={color} fontSize={10} className="num">{label}</text>
    </g>
  );
}

function Arrow({ cx, cy, dir, color }: { cx: number; cy: number; dir: "up" | "down"; color: string }) {
  const s = 6;
  const pts = dir === "up" ? `${cx},${cy - s} ${cx - s},${cy + s} ${cx + s},${cy + s}` : `${cx},${cy + s} ${cx - s},${cy - s} ${cx + s},${cy - s}`;
  return <polygon points={pts} fill={color} stroke="#000" strokeWidth={0.5} />;
}
