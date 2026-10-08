"use client";

import { Download, Printer } from "lucide-react";
import { useState } from "react";
import { Heatmap } from "@/components/charts/Heatmap";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { EdgeVerdict } from "@/components/metrics/EdgeVerdict";
import { KpiSection } from "@/components/metrics/KpiSection";
import { ReadinessPanel, type ReadinessData } from "@/components/metrics/ReadinessPanel";
import { ScoreBar } from "@/components/metrics/ScoreBar";
import { StatTable } from "@/components/metrics/StatTable";
import { WarningList } from "@/components/metrics/WarningList";
import { SimpleTable } from "@/components/tables/SimpleTable";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { ErrorBlock, LoadingBlock } from "@/components/ui/state";
import { apiUrl } from "@/lib/api";
import { days, money, num, pct, shortDate, signedMoney } from "@/lib/format";
import { useBt, useBtQuery } from "@/lib/hooks";
import type { Metrics, ScoreResult, Warning } from "@/lib/types";
import type { DrawdownData, EquityData, GroupMetrics, PropMcSummary } from "@/lib/types-api";

interface Report {
  generated_at: string;
  summary: { id: string; name: string; symbol: string; strategy: string; start_date: string; end_date: string; git_commit: string; seed: number; config: { data_model: string } };
  performance: Metrics;
  equity: EquityData;
  drawdowns: DrawdownData;
  monthly: { year: string; months: (number | null)[]; total: number }[];
  time_analysis: { time_of_day: GroupMetrics[] };
  mfe_mae: Record<string, number | null>;
  distributions: Record<string, Record<string, number | null>>;
  monte_carlo: Record<string, number | null>;
  walk_forward: { windows: number; consistency: number; aggregate: { stitched_oos?: Record<string, number> } | null };
  parameter_stability: { param_x: string; param_y: string; stability: { score: number; classification: string; message: string } };
  stress_tests: { slippage: Record<string, number>[]; commission: Record<string, number | string>[]; outliers: { warning: string | null; top10_share_of_gross_profit: number } };
  prop_simulation: { single_run: { status: string; reason: string }; monte_carlo: PropMcSummary; survival_90d: number };
  risk_analysis: { risk_of_ruin: Record<string, number>; losing_streaks: { longest: number; median_longest_streak_250: number; loss_probability: number } };
  score: ScoreResult;
  robustness: { score: number };
  overfitting: { level: string; score: number };
  readiness: ReadinessData;
  warnings: Warning[];
  data_note: string;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export default function ReportsPage() {
  const { id } = useBt();
  const [go, setGo] = useState(false);
  const q = useBtQuery<Report>("/report", go);
  const r = q.data;
  return (
    <>
      <PageHeader
        title="Report"
        description="A complete, printable summary of one experiment: results, robustness, risk and the honest caveats. Download as standalone HTML or print / save as PDF from your browser."
        actions={
          <>
            <Button size="sm" onClick={() => window.print()} disabled={!r}><Printer size={13} /> Print / PDF</Button>
            <Button asChild size="sm" variant="secondary"><a href={apiUrl(`/backtests/${id}/report.html`)}><Download size={13} /> Download HTML</a></Button>
          </>
        }
      />
      {!go && (
        <Panel title="Generate report">
          <p className="mb-3 text-[12px] text-muted">Builds every section for {id}. The first run computes the full robustness analysis (about 20–60 seconds); later runs are instant.</p>
          <Button variant="primary" onClick={() => setGo(true)}>Generate report</Button>
        </Panel>
      )}
      {go && (q.error ? <ErrorBlock error={q.error} /> : !r ? <LoadingBlock label="Building report (first run runs the full robustness analysis)…" height="h-56" /> : (
        <div className="space-y-4">
          <Panel title="1 · Strategy summary">
            <h2 className="text-[15px] font-semibold">{r.summary.name} <span className="text-muted">({r.summary.id})</span></h2>
            <p className="text-[12px] text-muted">{r.summary.symbol} · {r.summary.strategy} · {shortDate(r.summary.start_date)} → {shortDate(r.summary.end_date)} · {r.summary.config.data_model === "structured" ? "ENGINEERED synthetic market (validation only)" : "synthetic random-walk market"} · seed {r.summary.seed} · commit {r.summary.git_commit} · generated {r.generated_at.slice(0, 16).replace("T", " ")} UTC</p>
            <div className="mt-3"><EdgeVerdict metrics={r.performance} /></div>
          </Panel>
          <Panel title="Deployment readiness"><ReadinessPanel data={r.readiness} /></Panel>
          <Panel title="2 · Final score & warnings">
            <div className="grid gap-4 xl:grid-cols-2">
              <div>
                <div className="num mb-1 text-[28px] font-bold">{r.score.score.toFixed(0)}<span className="text-[14px] text-muted">/100 · grade {r.score.grade}</span></div>
                <p className="mb-2 text-[12px]">{r.score.verdict}</p>
                <div className="space-y-2">{Object.entries(r.score.components).map(([k, v]) => <ScoreBar key={k} label={k} value={v} weight={r.score.weights[k]} />)}</div>
                <p className="mt-2 text-[11px] text-muted">Robustness {r.robustness.score.toFixed(0)}/100 · overfitting risk {r.overfitting.level} ({r.overfitting.score.toFixed(0)})</p>
              </div>
              <WarningList warnings={r.warnings} />
            </div>
          </Panel>
          <Panel title="3 · Performance"><KpiSection m={r.performance} /></Panel>
          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="4 · Equity">
              <TimeSeriesChart data={r.equity.dates.map((date, i) => ({ date, equity: r.equity.net_equity[i] }))} series={[{ key: "equity", label: "Net equity", kind: "area" }]} height={220} yFormat={(v) => `$${(v / 1000).toFixed(0)}k`} />
            </Panel>
            <Panel title="5 · Drawdown">
              <TimeSeriesChart data={r.drawdowns.dates.map((date, i) => ({ date, dd: -r.drawdowns.drawdown_pct[i] }))} series={[{ key: "dd", label: "Drawdown %", kind: "area", color: "#f6465d" }]} height={220} yFormat={(v) => `${v.toFixed(0)}%`} />
            </Panel>
          </div>
          <Panel title="Top drawdowns" bodyClassName="p-2">
            <SimpleTable rows={r.drawdowns.periods.slice(0, 5)} columns={[
              { key: "start", header: "Start", render: (p) => shortDate(p.start) },
              { key: "bottom", header: "Bottom", render: (p) => shortDate(p.bottom) },
              { key: "recovery", header: "Recovery", render: (p) => (p.recovery ? shortDate(p.recovery) : "not recovered") },
              { key: "depth", header: "Depth", align: "right", render: (p) => `${money(p.depth)} (${pct(p.depth_pct)})` },
              { key: "duration_days", header: "Duration", align: "right", render: (p) => days(p.duration_days) },
            ]} />
          </Panel>
          <Panel title="6 · Monthly returns">
            <Heatmap rows={r.monthly.map((m) => m.year)} cols={[...MONTHS, "Year"]} values={r.monthly.map((m) => [...m.months, m.total])} format={(v) => `${v.toFixed(1)}%`} rowLabelWidth="w-14" />
          </Panel>
          <Panel title="7 · Time analysis" bodyClassName="p-2">
            <SimpleTable rows={r.time_analysis.time_of_day} columns={[
              { key: "label", header: "Entry time" }, { key: "trades", header: "Trades", align: "right" },
              { key: "net_pnl", header: "Net P&L", align: "right", render: (x) => signedMoney(x.net_pnl) },
              { key: "win_rate", header: "Win rate", align: "right", render: (x) => pct(x.win_rate, 0) },
              { key: "profit_factor", header: "PF", align: "right", render: (x) => num(x.profit_factor) },
              { key: "expectancy", header: "Expectancy", align: "right", render: (x) => signedMoney(x.expectancy, 2) },
            ]} />
          </Panel>
          <div className="grid gap-4 xl:grid-cols-3">
            <Panel title="8 · MFE / MAE"><StatTable rows={[{ label: "Average MFE", value: money(r.mfe_mae.avg_mfe, 2) }, { label: "Average MAE", value: money(r.mfe_mae.avg_mae, 2) }, { label: "Winner MAE", value: money(r.mfe_mae.winner_mae, 2) }, { label: "Loser MAE", value: money(r.mfe_mae.loser_mae, 2) }]} /></Panel>
            <Panel title="9 · Distribution of trade P&L"><StatTable rows={Object.entries(r.distributions.trade_pnl).map(([k, v]) => ({ label: k, value: v === null ? "–" : num(v as number, 2) }))} /></Panel>
            <Panel title="10 · Monte Carlo (1,000 paths)"><StatTable rows={[{ label: "Median ending balance", value: money(r.monte_carlo.median_ending_balance) }, { label: "5th pct ending", value: money(r.monte_carlo.p5_ending_balance) }, { label: "Probability of profit", value: pct(r.monte_carlo.prob_profit) }, { label: "Probability of ruin", value: pct(r.monte_carlo.prob_ruin) }, { label: "95th pct drawdown", value: money(r.monte_carlo.p95_max_drawdown) }]} /></Panel>
          </div>
          <div className="grid gap-4 xl:grid-cols-3">
            <Panel title="11 · Walk-forward"><StatTable rows={[{ label: "Windows", value: String(r.walk_forward.windows) }, { label: "Profitable OOS windows", value: pct(r.walk_forward.consistency, 0) }, { label: "Stitched OOS net profit", value: signedMoney(r.walk_forward.aggregate?.stitched_oos?.net_profit) }, { label: "Stitched OOS Sharpe", value: num(r.walk_forward.aggregate?.stitched_oos?.sharpe) }]} /></Panel>
            <Panel title="12 · Parameter stability"><StatTable rows={[{ label: "Grid", value: `${r.parameter_stability.param_x} × ${r.parameter_stability.param_y}` }, { label: "Stability score", value: num(r.parameter_stability.stability.score, 0) }, { label: "Classification", value: r.parameter_stability.stability.classification }]} /><p className="mt-2 text-[11px] text-muted">{r.parameter_stability.stability.message}</p></Panel>
            <Panel title="13 · Stress tests"><StatTable rows={[{ label: "Net at +2 ticks slippage", value: signedMoney(r.stress_tests.slippage.find((s) => s.ticks === 2)?.net_profit) }, { label: "Net at 2× commissions", value: signedMoney(r.stress_tests.commission.find((s) => s.multiplier === 2)?.net_profit as number) }, { label: "Top-10 trades' share of gross profit", value: pct(r.stress_tests.outliers.top10_share_of_gross_profit, 0) }]} />{r.stress_tests.outliers.warning && <p className="mt-2 text-[11px] text-warn">{r.stress_tests.outliers.warning}</p>}</Panel>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="14 · Prop simulation (generic 50K rules)"><StatTable rows={[{ label: "Single replay", value: r.prop_simulation.single_run.status }, { label: "Pass probability", value: pct(r.prop_simulation.monte_carlo.pass_probability, 0) }, { label: "Fail probability", value: pct(r.prop_simulation.monte_carlo.fail_probability, 0) }, { label: "Funded 90-day survival", value: pct(r.prop_simulation.survival_90d, 0) }]} /><p className="mt-2 text-[11px] text-muted">{r.prop_simulation.single_run.reason}</p></Panel>
            <Panel title="15 · Risk analysis"><StatTable rows={[{ label: "Risk of ruin (2.5k drawdown)", value: pct(r.risk_analysis.risk_of_ruin.risk_of_ruin) }, { label: "Longest losing streak", value: String(r.risk_analysis.losing_streaks.longest) }, { label: "Typical worst streak in 250 trades", value: String(r.risk_analysis.losing_streaks.median_longest_streak_250) }]} /></Panel>
          </div>
          <p className="rounded-md border border-border bg-surface px-3 py-2 text-[11.5px] text-muted">{r.data_note} Every figure is net of fees and slippage. See &quot;What do these numbers assume?&quot; in the banner for the full list of caveats.</p>
        </div>
      ))}
    </>
  );
}
