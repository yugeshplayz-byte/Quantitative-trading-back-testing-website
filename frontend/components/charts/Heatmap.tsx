"use client";

import { cn } from "@/lib/utils";

/**
 * Dense colour-grid heatmap.
 * diverging=true centres the scale on 0 (green positive / red negative); otherwise low->high blue ramp.
 */
export function Heatmap({
  rows,
  cols,
  values,
  format = (v: number) => v.toFixed(0),
  diverging = true,
  higherIsBetter = true,
  cellClass,
  rowLabelWidth = "w-24",
  markers,
  title,
  subtitles,
}: {
  rows: (string | number)[];
  cols: (string | number)[];
  values: (number | null)[][];
  format?: (v: number) => string;
  diverging?: boolean;
  higherIsBetter?: boolean;
  cellClass?: string;
  rowLabelWidth?: string;
  /** Optional per-cell badge (e.g. "★" for best, "●" for current). Same shape as values. */
  markers?: (string | null)[][];
  title?: string;
  subtitles?: (string | null)[][];
}) {
  const flat = values.flat().filter((v): v is number => typeof v === "number" && Number.isFinite(v));
  const max = flat.length ? Math.max(...flat) : 0;
  const min = flat.length ? Math.min(...flat) : 0;
  const absMax = Math.max(Math.abs(max), Math.abs(min)) || 1;

  const color = (v: number | null): string => {
    if (v === null || !Number.isFinite(v)) return "transparent";
    if (diverging) {
      const t = Math.min(Math.abs(v) / absMax, 1);
      const good = higherIsBetter ? v >= 0 : v <= 0;
      return good ? `rgba(46,189,133,${0.12 + t * 0.6})` : `rgba(246,70,93,${0.12 + t * 0.6})`;
    }
    const range = max - min || 1;
    let t = (v - min) / range;
    if (!higherIsBetter) t = 1 - t;
    return `rgba(76,141,255,${0.08 + t * 0.7})`;
  };

  return (
    <div className="overflow-x-auto">
      {title && <div className="mb-1 text-[11px] text-muted">{title}</div>}
      <table className="border-separate border-spacing-[2px] text-[11px]">
        <thead>
          <tr>
            <th className={rowLabelWidth} />
            {cols.map((c) => (
              <th key={String(c)} className="num px-1 pb-1 text-center font-normal text-muted">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={String(r)}>
              <th className={cn("num whitespace-nowrap pr-2 text-right font-normal text-muted", rowLabelWidth)}>{r}</th>
              {cols.map((c, j) => {
                const v = values[i]?.[j] ?? null;
                return (
                  <td
                    key={String(c)}
                    className={cn("num min-w-[52px] rounded-sm px-1.5 py-1 text-center", cellClass)}
                    style={{ background: color(v) }}
                    title={v === null ? "no data" : String(v)}
                  >
                    {v === null ? <span className="text-muted/50">–</span> : format(v)}
                    {markers?.[i]?.[j] && <span className="ml-0.5 text-warn">{markers[i][j]}</span>}
                    {subtitles?.[i]?.[j] && <div className="text-[9.5px] text-muted">{subtitles[i][j]}</div>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
