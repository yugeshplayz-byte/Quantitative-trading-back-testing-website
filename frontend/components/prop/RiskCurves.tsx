"use client";

import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { SimpleTable } from "@/components/tables/SimpleTable";
import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/card";
import { money, num, pct, signedMoney } from "@/lib/format";
import type { RiskOptData } from "@/lib/types-api";

type Metric = { key: keyof RiskOptData["rows"][number]; title: string; fmt: (v: number) => string; color?: string };

/** Risk-per-trade sweep: one small chart per metric with the best risk-adjusted zone shaded, plus the table. */
export function RiskCurves({ data, metrics, accountMetrics = false }: { data: RiskOptData; metrics: Metric[]; accountMetrics?: boolean }) {
  const rows = data.rows.map((r) => ({ ...r, x: r.risk_per_trade }));
  const zone = data.best_zone;
  const risky = rows.filter((r) => !r.achievable);
  return (
    <div className="space-y-4">
      {data.best_risk === null ? (
        <div className="rounded-lg border border-down/40 bg-down/5 p-3 text-[12px] text-down">{data.note}</div>
      ) : (
        <div className="rounded-lg border border-up/40 bg-up/5 p-3 text-[12px]">
          <b className="text-up">Strongest risk-adjusted zone: ${zone?.[0]}–${zone?.[1]} per trade</b> (best single level ${data.best_risk}). Score = {data.score_definition}. {data.note}
        </div>
      )}
      {risky.length > 0 && (
        <div className="rounded-lg border border-warn/40 bg-warn/5 p-3 text-[12px] text-warn">
          Not achievable with whole contracts: {risky.map((r) => `$${r.risk_per_trade}`).join(", ")}. One contract of this strategy risks about {money(data.contract_risk)}, so these levels would skip or oversize trades; their numbers below are hypothetical and excluded from the best zone.
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {metrics.map((m) => (
          <Panel key={String(m.key)} title={m.title}>
            <TimeSeriesChart
              data={rows as unknown as Record<string, number | string | null>[]}
              xKey="x"
              xFormat={(v) => `$${v}`}
              series={[{ key: String(m.key), label: m.title, color: m.color ?? "#4c8dff", width: 2 }]}
              height={170}
              yFormat={m.fmt}
              legend={false}
              minTickGap={8}
              zone={zone}
            />
          </Panel>
        ))}
      </div>
      <Panel title="Risk per trade sweep" bodyClassName="p-2">
        <SimpleTable
          rows={data.rows}
          columns={[
            { key: "risk_per_trade", header: "Risk / trade", render: (r) => <span>${r.risk_per_trade}{!r.achievable && <Badge tone="warn" className="ml-1.5">n/a</Badge>}{r.achievable && r.oversized && <Badge className="ml-1.5">oversized</Badge>}{zone && r.risk_per_trade >= zone[0] && r.risk_per_trade <= zone[1] && <Badge tone="up" className="ml-1.5">best zone</Badge>}</span> },
            { key: "expected_return", header: accountMetrics ? "Expected 60d return" : "Expected 60d P&L", align: "right", render: (r) => signedMoney(r.expected_return), cellClass: (r) => (r.expected_return >= 0 ? "text-up" : "text-down") },
            { key: "max_drawdown", header: "Median max DD", align: "right", render: (r) => money(r.max_drawdown) },
            { key: "failure_probability", header: "Failure prob.", align: "right", render: (r) => pct(r.failure_probability, 0) },
            { key: "pass_probability", header: "Pass prob.", align: "right", render: (r) => pct(r.pass_probability, 0) },
            { key: "median_days_to_pass", header: "Median days to pass", align: "right", render: (r) => (r.median_days_to_pass === null ? "–" : num(r.median_days_to_pass, 0)) },
            { key: "funded_survival_90d", header: "Funded 90d survival", align: "right", render: (r) => pct(r.funded_survival_90d, 0) },
            { key: "expected_payouts", header: "Expected payouts", align: "right", render: (r) => money(r.expected_payouts) },
            { key: "score", header: "Score ($/attempt)", align: "right", render: (r) => money(r.score) },
          ]}
        />
      </Panel>
    </div>
  );
}

export const ALL_RISK_METRICS: Metric[] = [
  { key: "expected_return", title: "Expected return ($, 60 days)", fmt: (v) => money(v), color: "#2ebd85" },
  { key: "max_drawdown", title: "Median max drawdown ($)", fmt: (v) => money(v), color: "#f6465d" },
  { key: "failure_probability", title: "Failure probability", fmt: (v) => `${(v * 100).toFixed(0)}%`, color: "#f6465d" },
  { key: "pass_probability", title: "Prop pass probability", fmt: (v) => `${(v * 100).toFixed(0)}%`, color: "#4c8dff" },
  { key: "median_days_to_pass", title: "Median days to pass", fmt: (v) => v.toFixed(0), color: "#a371f7" },
  { key: "expected_payouts", title: "Expected payouts ($)", fmt: (v) => money(v), color: "#f0b429" },
];
