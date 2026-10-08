"use client";

import Link from "next/link";
import { BarsChart } from "@/components/charts/BarsChart";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { EdgeVerdict } from "@/components/metrics/EdgeVerdict";
import { KpiSection } from "@/components/metrics/KpiSection";
import { WarningList } from "@/components/metrics/WarningList";
import { SimpleTable } from "@/components/tables/SimpleTable";
import { Badge, severityTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { EmptyState, Query } from "@/components/ui/state";
import { money, pnlClass, ratio, signedMoney } from "@/lib/format";
import { useBt, useBtQuery } from "@/lib/hooks";
import type { DashboardData } from "@/lib/types-api";

export default function DashboardPage() {
  const { current, id, loading, error } = useBt();
  const q = useBtQuery<DashboardData>("/dashboard");

  if (!loading && !error && !current) return <EmptyState>No backtests yet. <Link className="text-accent underline" href="/backtest/configuration">Run one</Link>.</EmptyState>;

  return (
    <>
      <PageHeader
        title={current ? current.name : "Dashboard"}
        description={current ? `${id} · ${current.symbol} · ${current.config.timeframe} · ${current.start_date} → ${current.end_date} · ${current.trade_count} trades · commit ${current.git_commit}` : undefined}
        actions={
          <>
            <Button asChild variant="secondary" size="sm"><Link href="/research/reports">Full report</Link></Button>
            <Button asChild variant="primary" size="sm"><Link href="/backtest/configuration">New backtest</Link></Button>
          </>
        }
      />
      <Query q={q} label="Loading dashboard…" height="h-64">
        {(d) => (
          <div className="space-y-4">
            <EdgeVerdict metrics={d.metrics} />
            <KpiSection m={d.metrics} />
            <div className="grid gap-4 xl:grid-cols-3">
              <Panel title="Equity curve" subtitle="Net of fees & slippage, closed-trade equity" className="xl:col-span-2">
                <TimeSeriesChart
                  data={d.equity as unknown as Record<string, number | string>[]}
                  series={[{ key: "equity", label: "Equity", kind: "area", color: "#4c8dff" }]}
                  height={260}
                  yFormat={(v) => `$${(v / 1000).toFixed(1)}k`}
                />
              </Panel>
              <Panel title="Strategy health">
                <ul className="space-y-2">
                  {d.health.map((h) => (
                    <li key={h.name} className="flex items-start gap-2">
                      <Badge tone={severityTone(h.status)} className="mt-0.5 w-12 justify-center">{h.status}</Badge>
                      <div>
                        <div className="text-[12px] font-medium">{h.name}</div>
                        <div className="text-[11px] text-muted">{h.detail}</div>
                      </div>
                    </li>
                  ))}
                </ul>
                {d.cached_score && (
                  <div className="mt-3 border-t border-border pt-2 text-[12px]">
                    Strategy score <span className="num font-semibold">{d.cached_score.score.toFixed(0)}/100</span> (grade {d.cached_score.grade}) · overfitting {d.cached_score.overfitting}
                  </div>
                )}
                {!d.cached_score && (
                  <Link href="/robustness/overfitting" className="mt-3 block border-t border-border pt-2 text-[12px] text-accent hover:underline">
                    Compute strategy score & robustness →
                  </Link>
                )}
              </Panel>
            </div>
            <div className="grid gap-4 xl:grid-cols-3">
              <Panel title="Drawdown" subtitle="% below prior equity peak (daily close)">
                <TimeSeriesChart
                  data={d.equity.map((e) => ({ date: e.date, dd: -e.drawdown_pct })) as unknown as Record<string, number | string>[]}
                  series={[{ key: "dd", label: "Drawdown %", kind: "area", color: "#f6465d" }]}
                  height={200}
                  yFormat={(v) => `${v.toFixed(0)}%`}
                />
              </Panel>
              <Panel title="Monthly performance" subtitle="Net P&L by month">
                <BarsChart
                  data={d.monthly as unknown as Record<string, number | string>[]}
                  xKey="period"
                  bars={[{ key: "net_pnl", label: "Net P&L", bySign: true }]}
                  height={200}
                  xFormat={(v) => v.slice(2)}
                  yFormat={(v) => money(v)}
                />
              </Panel>
              <Panel title="Backtest quality warnings">
                <WarningList warnings={d.warnings} />
              </Panel>
            </div>
            <Panel title="Recent trades" actions={<Link href="/backtest/trades" className="text-[11px] text-accent hover:underline">Open Trade Explorer →</Link>}>
              <SimpleTable
                rows={d.recent_trades}
                maxHeight="320px"
                columns={[
                  { key: "id", header: "ID" },
                  { key: "date", header: "Date" },
                  { key: "direction", header: "Dir", cellClass: (r) => (r.direction === "Long" ? "text-up" : "text-down") },
                  { key: "quantity", header: "Qty", align: "right" },
                  { key: "setup", header: "Setup" },
                  { key: "exit_reason", header: "Exit" },
                  { key: "r_multiple", header: "R", align: "right", render: (r) => ratio(r.r_multiple as number) },
                  { key: "net_pnl", header: "Net P&L", align: "right", render: (r) => signedMoney(r.net_pnl as number, 2), cellClass: (r) => pnlClass(r.net_pnl as number) },
                ]}
              />
            </Panel>
          </div>
        )}
      </Query>
    </>
  );
}
