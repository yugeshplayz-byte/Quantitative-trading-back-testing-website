"use client";

import { useMemo } from "react";
import { money, pct } from "@/lib/format";

interface Day {
  date: string;
  net_pnl: number;
  trades: number;
  win_rate: number | null;
}

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** GitHub-style daily P&L calendar: one column per week, one row per weekday, grouped by year. */
export function CalendarHeatmap({ days }: { days: Day[] }) {
  const { years, absMax } = useMemo(() => {
    const byYear = new Map<number, Day[]>();
    let mx = 1;
    for (const d of days) {
      const y = Number(d.date.slice(0, 4));
      byYear.set(y, [...(byYear.get(y) ?? []), d]);
      mx = Math.max(mx, Math.abs(d.net_pnl));
    }
    return { years: [...byYear.entries()].sort((a, b) => a[0] - b[0]), absMax: mx };
  }, [days]);

  const color = (v: number, trades: number) => {
    if (trades === 0) return "rgba(255,255,255,0.04)";
    const t = Math.min(Math.abs(v) / absMax, 1);
    return v >= 0 ? `rgba(46,189,133,${0.15 + t * 0.75})` : `rgba(246,70,93,${0.15 + t * 0.75})`;
  };

  return (
    <div className="space-y-3 overflow-x-auto">
      {years.map(([year, ds]) => {
        const jan1 = new Date(Date.UTC(year, 0, 1));
        const offset = (jan1.getUTCDay() + 6) % 7; // Monday = 0
        const cells = ds.map((d) => {
          const dt = new Date(d.date + "T00:00:00Z");
          const doy = Math.floor((dt.getTime() - jan1.getTime()) / 86400000);
          return { d, col: Math.floor((doy + offset) / 7), row: (dt.getUTCDay() + 6) % 7 };
        });
        const cols = Math.max(...cells.map((c) => c.col)) + 1;
        const monthStart = MONTHS.map((_, m) => Math.floor((Math.floor((Date.UTC(year, m, 1) - jan1.getTime()) / 86400000) + offset) / 7));
        const total = ds.reduce((s, d) => s + d.net_pnl, 0);
        return (
          <div key={year}>
            <div className="mb-1 flex items-baseline gap-3 text-[11px]">
              <span className="font-semibold text-foreground">{year}</span>
              <span className={total >= 0 ? "text-up" : "text-down"}>{money(total)}</span>
            </div>
            <div className="relative" style={{ width: cols * 14 + 30, height: 5 * 14 + 16 }}>
              {monthStart.map((c, m) => (
                <span key={m} className="absolute text-[9.5px] text-muted" style={{ left: 30 + c * 14, top: 0 }}>{MONTHS[m]}</span>
              ))}
              {DOW.map((n, r) => (
                <span key={n} className="absolute text-[9.5px] text-muted" style={{ left: 0, top: 14 + r * 14 }}>{n}</span>
              ))}
              {cells.map(({ d, col, row }) => (
                <div
                  key={d.date}
                  title={`${d.date}: ${money(d.net_pnl)} · ${d.trades} trades${d.win_rate !== null ? ` · ${pct(d.win_rate, 0)} win` : ""}`}
                  className="absolute rounded-[2px]"
                  style={{ left: 30 + col * 14, top: 14 + row * 14, width: 12, height: 12, background: color(d.net_pnl, d.trades) }}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
