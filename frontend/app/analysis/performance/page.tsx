"use client";

import { CalendarHeatmap } from "@/components/analysis/CalendarHeatmap";
import { GroupTable } from "@/components/analysis/GroupTable";
import { BarsChart } from "@/components/charts/BarsChart";
import { Heatmap } from "@/components/charts/Heatmap";
import { PageHeader } from "@/components/layout/PageHeader";
import { EdgeVerdict } from "@/components/metrics/EdgeVerdict";
import { KpiSection } from "@/components/metrics/KpiSection";
import { SimpleTable } from "@/components/tables/SimpleTable";
import { Panel } from "@/components/ui/card";
import { Query } from "@/components/ui/state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { int, money, pct, pctRaw, pnlClass, signedMoney } from "@/lib/format";
import { useBtQuery } from "@/lib/hooks";
import type { PerformanceData } from "@/lib/types-api";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export default function PerformancePage() {
  const q = useBtQuery<PerformanceData>("/analytics/performance");
  return (
    <>
      <PageHeader title="Performance" description="Full metric set, calendar analytics, monthly returns and splits by direction, setup and exit type. All figures are net of fees and slippage." />
      <Query q={q} height="h-80">
        {(d) => (
          <div className="space-y-4">
            <EdgeVerdict metrics={d.metrics} />
            <KpiSection m={d.metrics} />
            <Panel title="Calendar P&L">
              <Tabs defaultValue="daily">
                <TabsList>
                  <TabsTrigger value="daily">Daily</TabsTrigger>
                  <TabsTrigger value="weekly">Weekly</TabsTrigger>
                  <TabsTrigger value="monthly">Monthly</TabsTrigger>
                </TabsList>
                <TabsContent value="daily">
                  <CalendarHeatmap days={d.calendar.daily} />
                </TabsContent>
                <TabsContent value="weekly">
                  <BarsChart data={d.calendar.weekly as unknown as Record<string, number | string>[]} xKey="period" bars={[{ key: "net_pnl", label: "Net P&L", bySign: true }]} height={260} xFormat={(v) => v.slice(2)} yFormat={money} />
                </TabsContent>
                <TabsContent value="monthly">
                  <BarsChart data={d.calendar.monthly as unknown as Record<string, number | string>[]} xKey="period" bars={[{ key: "net_pnl", label: "Net P&L", bySign: true }]} height={220} xFormat={(v) => v.slice(2)} yFormat={money} />
                  <div className="mt-3">
                    <SimpleTable
                      maxHeight="260px"
                      rows={d.calendar.monthly}
                      columns={[
                        { key: "period", header: "Month" },
                        { key: "net_pnl", header: "Net P&L", align: "right", render: (r) => signedMoney(r.net_pnl), cellClass: (r) => pnlClass(r.net_pnl) },
                        { key: "return_pct", header: "Return", align: "right", render: (r) => pctRaw(r.return_pct, 2), cellClass: (r) => pnlClass(r.return_pct) },
                        { key: "trades", header: "Trades", align: "right", render: (r) => int(r.trades) },
                        { key: "win_rate", header: "Win rate", align: "right", render: (r) => pct(r.win_rate) },
                      ]}
                    />
                  </div>
                </TabsContent>
              </Tabs>
            </Panel>
            <Panel title="Monthly return matrix" subtitle="% return on equity at the start of each month">
              <Heatmap
                rows={d.calendar.monthly_matrix.map((r) => r.year)}
                cols={[...MONTHS, "Year"]}
                values={d.calendar.monthly_matrix.map((r) => [...r.months, r.total])}
                format={(v) => `${v.toFixed(1)}%`}
                rowLabelWidth="w-14"
              />
            </Panel>
            <div className="grid gap-4 xl:grid-cols-2">
              <Panel title="Long vs short" bodyClassName="p-2"><GroupTable rows={d.long_short.rows} labelHeader="Side" /></Panel>
              <Panel title="By exit reason" bodyClassName="p-2"><GroupTable rows={d.by_exit} labelHeader="Exit" showDrawdown={false} /></Panel>
            </div>
            <Panel title="By setup" bodyClassName="p-2"><GroupTable rows={d.by_setup} labelHeader="Setup" /></Panel>
          </div>
        )}
      </Query>
    </>
  );
}
