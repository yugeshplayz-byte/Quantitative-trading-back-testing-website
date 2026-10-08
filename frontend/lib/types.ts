/** TypeScript mirrors of the backend Pydantic models (backend/app/models) and API payloads. */

// ------------------------------------------------------------------ configuration
export interface ParameterSpec {
  key: string;
  label: string;
  default: number;
  min: number;
  max: number;
  step: number;
  group?: "strategy" | "config";
}

export interface Strategy {
  key: string;
  name: string;
  description: string;
  default_symbol: string;
  parameters: ParameterSpec[];
  custom?: boolean;
}

export interface TradingConfig {
  long_enabled: boolean;
  short_enabled: boolean;
  max_trades_per_day: number;
  max_contracts: number;
  entry_delay_bars: number;
  exit_delay_bars: number;
}

export interface RiskConfig {
  sizing_mode: "fixed_contracts" | "fixed_dollar" | "percent";
  contracts: number;
  risk_dollars: number;
  risk_pct: number;
  daily_loss_limit: number | null;
  max_drawdown: number | null;
  consecutive_loss_limit: number | null;
}

export interface StopConfig {
  type: "fixed_point" | "fixed_dollar" | "atr" | "structure";
  value: number;
}
export interface TargetConfig {
  type: "fixed_point" | "risk_reward" | "atr";
  value: number;
}

export interface ManagementConfig {
  breakeven: boolean;
  breakeven_trigger_r: number;
  trailing_stop: boolean;
  trail_atr_mult: number;
  partial_profit: boolean;
  partial_pct: number;
  partial_at_r: number;
  scale_in: boolean;
  scale_in_at_r: number;
  scale_out: boolean;
}

export interface ExecutionConfig {
  commission_per_side: number;
  exchange_fee_per_side: number;
  slippage_ticks: number;
  spread_ticks: number;
  latency_ms: number;
  limit_through_ticks: number;
}

export type Symbol = "MNQ" | "NQ" | "MES" | "ES";
export type DataModel = "random_walk" | "structured" | "real";

export interface BacktestConfig {
  strategy: string;
  symbol: Symbol;
  start_date: string;
  end_date: string;
  starting_balance: number;
  timeframe: "5m" | "15m";
  session: "RTH" | "ETH";
  params: Record<string, number>;
  trading: TradingConfig;
  risk: RiskConfig;
  stop: StopConfig;
  target: TargetConfig;
  management: ManagementConfig;
  execution: ExecutionConfig;
  seed: number;
  data_model: DataModel;
  name?: string | null;
  notes?: string | null;
  tags: string[];
}

export interface PayoutRules {
  threshold: number;
  min_balance: number;
  max_withdrawal: number;
  frequency_days: number;
  profit_split: number;
}

export type DrawdownType = "static" | "eod_trailing" | "intraday_trailing";

export interface PropFirmRules {
  name: string;
  starting_balance: number;
  profit_target: number;
  max_drawdown: number;
  daily_loss_limit: number | null;
  max_contracts: number;
  drawdown_type: DrawdownType;
  trailing_locks_at_start: boolean;
  min_trading_days: number;
  consistency_pct: number | null;
  min_profitable_days: number;
  min_profitable_day_amount: number;
  trading_start: string;
  trading_end: string;
  liquidation_time: string;
  max_evaluation_days: number;
  payout: PayoutRules;
}

export interface StrategyPreset {
  id?: number;
  name: string;
  description: string;
  config: BacktestConfig;
  prop_rules: PropFirmRules | null;
  created_at?: string;
}

// ------------------------------------------------------------------ results
export interface TradeEvent {
  time: string;
  price: number;
  kind: "scale_in" | "scale_out" | "breakeven" | "trail";
  quantity: number;
}

export interface Trade {
  id: string;
  symbol: string;
  date: string;
  entry_time: string;
  exit_time: string;
  direction: "Long" | "Short";
  entry_price: number;
  exit_price: number;
  quantity: number;
  stop: number;
  target: number | null;
  gross_pnl: number;
  fees: number;
  slippage: number;
  net_pnl: number;
  r_multiple: number;
  risk_dollars: number;
  mae: number;
  mfe: number;
  mae_points: number;
  mfe_points: number;
  duration_minutes: number;
  regime: string;
  setup: string;
  confidence: number;
  atr_percentile: number;
  entry_reason: string;
  exit_reason: string;
  events: TradeEvent[];
}

export type Metrics = Record<string, number | null>;

export interface DrawdownPeriod {
  start: string;
  bottom: string;
  recovery: string | null;
  depth: number;
  depth_pct: number;
  duration_days: number;
  recovery_days: number | null;
}

export interface DailyPerformance {
  date: string;
  net_pnl: number;
  trades: number;
  equity: number;
  drawdown: number;
}

export interface BacktestResult {
  id: string;
  name: string;
  strategy: string;
  symbol: string;
  version: string;
  start_date: string;
  end_date: string;
  created_at: string;
  tags: string[];
  favorite: boolean;
  notes: string;
  git_commit: string;
  seed: number;
  trade_count: number;
  metrics: Metrics;
  meta: { lookahead?: { status: string; message: string } };
  config: BacktestConfig;
  dataset?: string;
}

export interface Experiment extends BacktestResult {
  parameters: Record<string, number>;
  risk_settings: RiskConfig;
  dataset: string;
}

// ------------------------------------------------------------------ monte carlo / optimisation
export type McMethod = "shuffle" | "bootstrap" | "block_bootstrap";

export interface MonteCarloConfig {
  backtest_id: string;
  simulations: number;
  trades: number;
  starting_balance: number;
  risk_per_trade: number | null;
  seed: number;
  method: McMethod;
  block_size: number;
  ruin_drawdown: number | null;
  target_profit: number | null;
}

export interface Hist {
  centers: number[];
  counts: number[];
}

export interface MonteCarloResult {
  config: MonteCarloConfig;
  summary: Record<string, number | null>;
  fan: { steps: number[]; p5: number[]; p25: number[]; p50: number[]; p75: number[]; p95: number[] };
  sample_paths: number[][];
  ending_hist: Hist;
  drawdown_hist: Hist;
  streak_dist: { lengths: number[]; probability: number[] };
  caveat: string;
}

export interface StabilityInfo {
  score: number;
  classification: string;
  plateau_fraction: number;
  best_neighbour_ratio: number;
  flags: string[][];
  message: string;
  best_cell?: { x: number; y: number };
}

export interface ParameterOptimizationResult {
  param_x: string;
  param_y: string;
  x_values: number[];
  y_values: number[];
  metric: string;
  higher_is_better: boolean;
  grid: (number | null)[][];
  trades_grid: number[][];
  best: { x: number | null; y: number | null; value: number | null; trades: number };
  current: { x: number; y: number; value: number | null };
  stability: StabilityInfo;
  selection_bias: { cells_tested: number; years: number; expected_best_sharpe_if_no_edge: number; note: string };
  runs: number;
}

export interface WalkForwardWindow {
  index: number;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  params: Record<string, number>;
  is_metrics: Record<string, number>;
  oos_metrics: Record<string, number>;
  degradation: number | null;
}

export interface WalkForwardResult {
  param_x: string;
  param_y: string;
  metric: string;
  windows: WalkForwardWindow[];
  aggregate: {
    is: Record<string, number>;
    oos: Record<string, number>;
    degradation: Record<string, number | null>;
    stitched_oos: Record<string, number>;
  } | null;
  oos_curve: { date: string; equity: number }[];
  consistency: number;
  profitable_windows?: number;
}

export interface PropSimulationResult {
  status: "PASS" | "FAIL" | "ACTIVE";
  failure_type: string;
  reason: string;
  days_traded: number;
  trading_days_elapsed: number;
  final_balance: number;
  peak_balance: number;
  max_drawdown_used: number;
  profit: number;
  best_day: number;
  equity_path: { day: number; date: string; balance: number; floor: number }[];
  checks: { rule: string; detail: string }[];
}

export interface Warning {
  code: string;
  severity: "high" | "medium" | "low";
  title: string;
  detail: string;
}

export interface ScoreResult {
  score: number;
  uncapped_score: number;
  capped: boolean;
  cap: number;
  verdict: string;
  grade: string;
  components: Record<string, number>;
  weights: Record<string, number>;
  methodology: string[];
}
