"""Deterministic prop-firm challenge evaluator.

Day-level assumptions (documented in docs/QUANT_ASSUMPTIONS.md):
* Balance checks use each day's intraday low/high (closed P&L extended by MAE/MFE).
* Intraday trailing assumes the day's high prints BEFORE its low (the worst case for the floor).
* End-of-day trailing moves the floor only at the close; breaches are still tested intraday.
* A trailing floor never rises above the starting balance when `trailing_locks_at_start` is set.
* PASS is decided at the close: target reached AND minimum trading days, minimum profitable days
  and the consistency rule are all satisfied. Breach checks take precedence over PASS on the same day.
* Maximum contracts is checked against the day's largest position.
"""
from __future__ import annotations

from ..models.prop import PropFirmRules, PropSimulationResult
from .days import DayPool


def _hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m) - (9 * 60 + 30)


def floor_level(rules: PropFirmRules, peak_eod: float, peak_intra: float) -> float:
    b0, dd = rules.starting_balance, rules.max_drawdown
    if rules.drawdown_type == "static":
        return b0 - dd
    peak = peak_eod if rules.drawdown_type == "eod_trailing" else peak_intra
    f = peak - dd
    return min(f, b0) if rules.trailing_locks_at_start else f


def evaluate_challenge(pool: DayPool, rules: PropFirmRules, start_day: int = 0) -> PropSimulationResult:
    b0 = rules.starting_balance
    bal, peak_eod, peak_intra = b0, b0, b0
    traded_days = profitable_days = 0
    best_day = 0.0
    path: list[dict] = []
    checks: list[dict] = []
    liq_min = _hhmm(rules.liquidation_time)
    late_exits = 0
    status, ftype, reason = "ACTIVE", "none", ""
    max_dd_used = 0.0
    days_elapsed = 0
    end = min(len(pool), start_day + rules.max_evaluation_days)

    for t in range(start_day, end):
        days_elapsed += 1
        pnl, low, high = float(pool.pnl[t]), float(pool.low[t]), float(pool.high[t])
        low, high = min(low, pnl, 0.0), max(high, pnl, 0.0)
        # drawdown floor for this day (intraday trailing assumes the high comes first)
        pk_intra_today = max(peak_intra, bal + high) if rules.drawdown_type == "intraday_trailing" else peak_intra
        floor = floor_level(rules, peak_eod, pk_intra_today)
        ref_peak = {"static": b0, "eod_trailing": peak_eod, "intraday_trailing": pk_intra_today}[rules.drawdown_type]
        max_dd_used = max(max_dd_used, ref_peak - (bal + low))
        date = str(pool.dates[t]) if t < len(pool.dates) else str(t)

        if pool.traded[t] and pool.max_contracts[t] > rules.max_contracts:
            status, ftype = "FAIL", "contracts"
            reason = (f"Maximum contracts exceeded on {date}: traded {int(pool.max_contracts[t])} "
                      f"(limit {rules.max_contracts})")
        elif rules.daily_loss_limit and low <= -rules.daily_loss_limit:
            status, ftype = "FAIL", "daily_loss"
            reason = (f"Daily loss limit breached on {date}: intraday low {low:,.0f} "
                      f"vs limit -{rules.daily_loss_limit:,.0f}")
        elif bal + low <= floor:
            status, ftype = "FAIL", "drawdown"
            reason = (f"Maximum drawdown breached on {date}: balance reached {bal + low:,.0f} "
                      f"at/below the {rules.drawdown_type.replace('_', ' ')} floor {floor:,.0f}")
        if status == "FAIL":
            bal = max(floor, bal + low) if ftype == "drawdown" else bal + low
            path.append({"day": days_elapsed, "date": date, "balance": round(bal, 2), "floor": round(floor, 2)})
            break

        bal += pnl
        if pool.traded[t]:
            traded_days += 1
            if pool.last_exit_min[t] > liq_min:
                late_exits += 1
        if pnl > max(rules.min_profitable_day_amount, 0.0):
            profitable_days += 1
        best_day = max(best_day, pnl)
        peak_eod = max(peak_eod, bal)
        peak_intra = max(pk_intra_today, bal)
        path.append({"day": days_elapsed, "date": date, "balance": round(bal, 2),
                     "floor": round(floor_level(rules, peak_eod, peak_intra), 2)})

        profit = bal - b0
        if profit >= rules.profit_target:
            blockers = []
            if traded_days < rules.min_trading_days:
                blockers.append(f"minimum trading days ({traded_days}/{rules.min_trading_days})")
            if profitable_days < rules.min_profitable_days:
                blockers.append(f"minimum profitable days ({profitable_days}/{rules.min_profitable_days})")
            if rules.consistency_pct and profit > 0 and best_day > rules.consistency_pct / 100.0 * profit:
                blockers.append(f"consistency rule (best day {best_day:,.0f} is {best_day / profit:.0%} of profit, "
                                f"limit {rules.consistency_pct:g}%)")
            if not blockers:
                status = "PASS"
                checks = []
                reason = f"Profit target {rules.profit_target:,.0f} reached on {date} after {days_elapsed} trading days"
                break
            checks = [{"rule": "pass_blocked", "detail": "Target reached but waiting on: " + "; ".join(blockers)}]

    if status == "ACTIVE":
        reason = (f"Evaluation still active after {days_elapsed} trading days: profit {bal - b0:,.0f} "
                  f"of {rules.profit_target:,.0f} target") if days_elapsed >= rules.max_evaluation_days or end == len(pool) \
            else "Evaluation in progress"
    checks.append({"rule": "forced_liquidation", "detail": f"{late_exits} day(s) with exits after "
                   f"{rules.liquidation_time} (informational - positions are flattened at the close)"})
    return PropSimulationResult(
        status=status, failure_type=ftype, reason=reason, days_traded=traded_days,
        trading_days_elapsed=days_elapsed, final_balance=round(bal, 2),
        peak_balance=round(max(peak_eod, peak_intra), 2), max_drawdown_used=round(max_dd_used, 2),
        profit=round(bal - b0, 2), best_day=round(best_day, 2), equity_path=path, checks=checks,
    )
