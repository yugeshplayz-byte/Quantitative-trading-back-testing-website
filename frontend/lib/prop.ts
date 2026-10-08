"use client";

import { useCallback, useMemo } from "react";
import { useLocalValue } from "./store";
import type { PropFirmRules } from "./types";

/** Generic starting rules. Edit them to match the firm you are evaluating - nothing is firm-specific. */
export const DEFAULT_RULES: PropFirmRules = {
  name: "Generic 50K evaluation",
  starting_balance: 50000,
  profit_target: 3000,
  max_drawdown: 2500,
  daily_loss_limit: 1100,
  max_contracts: 10,
  drawdown_type: "eod_trailing",
  trailing_locks_at_start: true,
  min_trading_days: 5,
  consistency_pct: 50,
  min_profitable_days: 0,
  min_profitable_day_amount: 0,
  trading_start: "09:30",
  trading_end: "16:00",
  liquidation_time: "15:55",
  max_evaluation_days: 90,
  payout: { threshold: 2000, min_balance: 0, max_withdrawal: 5000, frequency_days: 14, profit_split: 0.9 },
};

/** Rules shared across every prop page and persisted in the browser (localStorage). */
export function usePropRules(): [PropFirmRules, (r: PropFirmRules) => void] {
  const [raw, setRaw] = useLocalValue("qbt_prop_rules", JSON.stringify(DEFAULT_RULES));
  const rules = useMemo<PropFirmRules>(() => {
    try {
      return { ...DEFAULT_RULES, ...JSON.parse(raw), payout: { ...DEFAULT_RULES.payout, ...(JSON.parse(raw).payout ?? {}) } };
    } catch {
      return DEFAULT_RULES;
    }
  }, [raw]);
  const set = useCallback((r: PropFirmRules) => setRaw(JSON.stringify(r)), [setRaw]);
  return [rules, set];
}
