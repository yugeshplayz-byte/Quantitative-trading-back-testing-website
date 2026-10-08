/** Response shapes of the analytics endpoints (backend/app/services). */
import type { ReadinessData } from "@/components/metrics/ReadinessPanel";
import type { BacktestResult, DrawdownPeriod, Metrics, ScoreResult, Warning } from "./types";

export interface MonthlyRow {
  period: string;
  net_pnl: number;
  trades: number;
  win_rate: number | null;
  return_pct: number | null;
}

export interface DashboardData {
  backtest: BacktestResult;
  metrics: Metrics;
  equity: { date: string; equity: number; drawdown: number; drawdown_pct: number }[];
  monthly: MonthlyRow[];
  recent_trades: Record<string, string | number>[];
  warnings: Warning[];
  health: { name: string; status: "good" | "warn" | "bad"; detail: string }[];
  cached_score: { score: number; grade: string; robustness: number; overfitting: string; readiness?: string } | null;
}

export interface GroupMetrics {
  label: string;
  trades: number;
  net_pnl: number | null;
  gross_profit: number | null;
  gross_loss: number | null;
  win_rate: number | null;
  profit_factor: number | null;
  expectancy: number | null;
  avg_winner: number | null;
  avg_loser: number | null;
  sharpe: number | null;
  max_drawdown: number | null;
  avg_r: number | null;
}

export interface EquityData {
  dates: string[];
  net_equity: number[];
  cumulative_pnl: number[];
  gross_equity: number[];
  long_equity: number[];
  short_equity: number[];
}

export interface DrawdownData {
  dates: string[];
  drawdown: number[];
  drawdown_pct: number[];
  days_underwater: number[];
  periods: DrawdownPeriod[];
  period_count: number;
}

export interface CalendarData {
  daily: { date: string; net_pnl: number; trades: number; win_rate: number | null }[];
  weekly: { period: string; net_pnl: number; trades: number; win_rate: number | null }[];
  monthly: MonthlyRow[];
  monthly_matrix: { year: string; months: (number | null)[]; total: number }[];
}

export interface TimeData {
  time_of_day: GroupMetrics[];
  day_of_week: GroupMetrics[];
  heatmap: { rows: string[]; cols: string[]; values: (number | null)[][]; counts: number[][] };
  long_short: { rows: GroupMetrics[] };
}

export interface MfeMaeData {
  points: { id: string; mae: number; mfe: number; net_pnl: number; r: number; winner: boolean; direction: string; regime: string; setup: string }[];
  stats: Record<string, number | null>;
}

export interface StatsBlock {
  count: number;
  mean: number | null;
  median: number | null;
  std: number | null;
  skew: number | null;
  kurtosis: number | null;
  p5: number | null;
  p95: number | null;
}
export type DistributionsData = Record<string, { hist: { centers: number[]; counts: number[]; edges: number[] }; stats: StatsBlock }>;

export interface StreakData {
  win_distribution: { length: number; count: number }[];
  loss_distribution: { length: number; count: number }[];
  longest_win: number;
  longest_loss: number;
  avg_win_streak: number;
  avg_loss_streak: number;
  current_streak: { type: string; length: number };
}

export interface EventsData {
  rows: { event: string; occurrences: number; phases: Record<"Before" | "During" | "After", GroupMetrics> }[];
  baseline?: GroupMetrics;
  note: string;
}

export interface RegimesData {
  rows: GroupMetrics[];
  volatility: GroupMetrics[];
  events: EventsData;
}

export interface PerformanceData {
  metrics: Metrics;
  long_short: { rows: GroupMetrics[] };
  calendar: CalendarData;
  by_setup: GroupMetrics[];
  by_exit: GroupMetrics[];
}

export interface StressData {
  baseline: Record<string, number>;
  slippage: ({ ticks: number } & Record<string, number>)[];
  commission: ({ multiplier: number; label: string } & Record<string, number>)[];
  missed: {
    removed_pct: number;
    runs: number;
    net_profit: { mean: number; p5: number; p95: number };
    max_drawdown: { mean: number; p5: number; p95: number };
    sharpe: { mean: number; p5: number; p95: number };
    profit_factor: { mean: number; p5: number; p95: number };
    prob_profitable: number;
  }[];
  outliers: {
    rows: ({ label: string; removed: number } & Record<string, number>)[];
    top10_share_of_gross_profit: number;
    dependent: boolean;
    warning: string | null;
    severity: string | null;
  };
  base_slippage_ticks: number;
}

export interface RobustnessData {
  robustness: { score: number; components: Record<string, number>; weights: Record<string, number>; methodology: string[] };
  score: ScoreResult;
  overfitting: { level: "LOW" | "MEDIUM" | "HIGH"; score: number; factors: Record<string, number>; weights: Record<string, number>; methodology: string[] };
  warnings: Warning[];
  readiness: ReadinessData;
  inputs: Record<string, unknown>;
}

export interface DatasetReport {
  symbol: string;
  files: string[];
  ok: boolean;
  bars: number;
  days: number;
  start: string | null;
  end: string | null;
  source_bar_minutes?: number;
  issues: { severity: "error" | "warning" | "info"; message: string }[];
}

export interface PropMcSummary {
  pass_probability: number;
  fail_probability: number;
  active_probability: number;
  median_days_to_pass: number | null;
  mean_days_to_pass: number | null;
  p90_days_to_pass: number | null;
  drawdown_failure_probability: number;
  daily_loss_failure_probability: number;
  other_failure_probability: number;
  ending_balance_median: number;
  ending_balance_p5: number;
  ending_balance_p95: number;
  simulations: number;
  horizon_days: number;
  ending_balance_hist: { centers: number[]; counts: number[] };
  days_to_pass_hist: { centers: number[]; counts: number[] };
}

export interface SurvivalData {
  curve: { trading_day: number; survival: number }[];
  marks: { calendar_days: number; trading_days: number; survival: number; capped: boolean }[];
}

export interface PayoutData {
  prob_first_payout: number;
  prob_second_payout: number;
  prob_third_payout: number;
  expected_total_payouts: number;
  median_total_payouts_given_paid: number;
  expected_payout_count: number;
  prob_lose_account_after_withdrawal: number;
  prob_lose_account_given_withdrawal: number;
  median_days_to_first_payout: number | null;
  payout_total_hist: { centers: number[]; counts: number[] };
  horizon_days: number;
  profit_split: number;
  survival: SurvivalData;
}

export interface RiskOptRow {
  risk_per_trade: number;
  risk_scale: number;
  expected_return: number;
  max_drawdown: number;
  p95_max_drawdown: number;
  failure_probability: number;
  pass_probability: number;
  median_days_to_pass: number | null;
  expected_payouts: number;
  payout_probability: number;
  funded_survival_90d: number;
  score: number;
  achievable: boolean;
  oversized: boolean;
}
export interface RiskOptData {
  rows: RiskOptRow[];
  best_risk: number | null;
  best_zone: [number, number] | null;
  contract_risk: number | null;
  note: string;
  score_definition: string;
  base_risk: number;
}
