"use client";

import { SimpleTable, type Column } from "@/components/tables/SimpleTable";
import { int, money, num, pct, pnlClass, ratio, signedMoney } from "@/lib/format";
import type { GroupMetrics } from "@/lib/types-api";

/** The standard comparison table used for time buckets, weekdays, long/short, regimes, volatility... */
export function GroupTable({ rows, labelHeader = "Group", showDrawdown = true, onlyActive = false }: { rows: GroupMetrics[]; labelHeader?: string; showDrawdown?: boolean; onlyActive?: boolean }) {
  const data = onlyActive ? rows.filter((r) => r.trades > 0) : rows;
  const cols: Column<GroupMetrics>[] = [
    { key: "label", header: labelHeader, className: "font-sans" },
    { key: "trades", header: "Trades", align: "right", render: (r) => int(r.trades) },
    { key: "net_pnl", header: "Net P&L", align: "right", render: (r) => signedMoney(r.net_pnl), cellClass: (r) => pnlClass(r.net_pnl) },
    { key: "win_rate", header: "Win rate", align: "right", render: (r) => (r.trades ? pct(r.win_rate) : "–") },
    { key: "profit_factor", header: "PF", align: "right", render: (r) => (r.trades ? ratio(r.profit_factor) : "–") },
    { key: "expectancy", header: "Expectancy", align: "right", render: (r) => (r.trades ? signedMoney(r.expectancy, 2) : "–"), cellClass: (r) => pnlClass(r.expectancy) },
    { key: "avg_winner", header: "Avg win", align: "right", render: (r) => (r.trades ? money(r.avg_winner, 2) : "–") },
    { key: "avg_loser", header: "Avg loss", align: "right", render: (r) => (r.trades ? money(r.avg_loser, 2) : "–") },
    { key: "sharpe", header: "Sharpe", align: "right", render: (r) => (r.trades ? num(r.sharpe) : "–") },
  ];
  if (showDrawdown) cols.push({ key: "max_drawdown", header: "Max DD", align: "right", render: (r) => (r.trades ? money(r.max_drawdown) : "–") });
  return <SimpleTable columns={cols} rows={data} />;
}
