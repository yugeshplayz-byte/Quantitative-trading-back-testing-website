"""Vectorised prop-firm Monte Carlo: evaluations, funded-account survival and payouts.

Days (not trades) are resampled from the backtest's daily records with replacement
(`block` > 1 resamples consecutive-day blocks to keep volatility clustering). Each sampled day
carries its P&L, intraday low/high and peak contracts, rescaled by `risk_scale`
(= target risk per trade / backtest average risk). Rules mirror `rules.evaluate_challenge`.
"""
from __future__ import annotations

import numpy as np

from ..models.prop import PropFirmRules
from .days import DayPool

ACTIVE, PASSED, FAILED = 0, 1, 2
F_NONE, F_DD, F_DAILY, F_CONTRACTS = 0, 1, 2, 3
SURVIVAL_CALENDAR_DAYS = [30, 60, 90, 180, 365]


def trading_days_from_calendar(days: int) -> int:
    return max(1, int(round(days * 5 / 7)))


def _sample(pool: DayPool, sims: int, horizon: int, rng: np.random.Generator, block: int) -> np.ndarray:
    n = len(pool)
    if block <= 1:
        return rng.integers(0, n, size=(sims, horizon))
    nb = int(np.ceil(horizon / block))
    starts = rng.integers(0, n, size=(sims, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
    return idx.reshape(sims, nb * block)[:, :horizon]


def simulate(
    pool: DayPool,
    rules: PropFirmRules,
    sims: int = 2000,
    horizon: int | None = None,
    risk_scale: float = 1.0,
    seed: int = 5,
    mode: str = "evaluation",
    block: int = 1,
    payouts: bool = False,
) -> dict:
    rng = np.random.default_rng(seed)
    horizon = horizon or rules.max_evaluation_days
    idx = _sample(pool, sims, horizon, rng, block)
    pnl = pool.pnl[idx] * risk_scale
    low = np.minimum(np.minimum(pool.low[idx] * risk_scale, pnl), 0.0)
    high = np.maximum(np.maximum(pool.high[idx] * risk_scale, pnl), 0.0)
    traded = pool.traded[idx]
    maxc = np.where(traded, np.maximum(1, np.round(pool.max_contracts[idx] * risk_scale)), 0)

    b0 = rules.starting_balance
    bal = np.full(sims, b0)
    peak_eod = np.full(sims, b0)
    peak_intra = np.full(sims, b0)
    status = np.zeros(sims, dtype=np.int8)
    ftype = np.zeros(sims, dtype=np.int8)
    end_day = np.zeros(sims, dtype=np.int32)
    traded_days = np.zeros(sims, dtype=np.int32)
    prof_days = np.zeros(sims, dtype=np.int32)
    best_day = np.zeros(sims)
    n_pay = np.zeros(sims, dtype=np.int32)
    pay_total = np.zeros(sims)
    last_pay = np.zeros(sims, dtype=np.int32)
    first_pay_day = np.zeros(sims, dtype=np.int32)
    intraday = rules.drawdown_type == "intraday_trailing"
    min_amt = max(rules.min_profitable_day_amount, 0.0)
    po = rules.payout

    for t in range(horizon):
        act = status == ACTIVE
        if not act.any():
            break
        p, lo, hi = pnl[:, t], low[:, t], high[:, t]
        pk_today = np.maximum(peak_intra, bal + hi) if intraday else peak_intra
        if rules.drawdown_type == "static":
            floor = np.full(sims, b0 - rules.max_drawdown)
        else:
            ref = pk_today if intraday else peak_eod
            floor = ref - rules.max_drawdown
            if rules.trailing_locks_at_start:
                floor = np.minimum(floor, b0)
        b_contracts = traded[:, t] & (maxc[:, t] > rules.max_contracts)
        b_daily = (lo <= -rules.daily_loss_limit) if rules.daily_loss_limit else np.zeros(sims, bool)
        b_dd = (bal + lo) <= floor
        fail = act & (b_contracts | b_daily | b_dd)
        ft = np.where(b_contracts, F_CONTRACTS, np.where(b_daily, F_DAILY, F_DD))
        status[fail] = FAILED
        ftype[fail] = ft[fail]
        end_day[fail] = t + 1
        bal = np.where(fail, np.where(ft == F_DD, np.maximum(floor, bal + lo), bal + lo), bal)
        ok = act & ~fail
        bal = np.where(ok, bal + p, bal)
        traded_days += (ok & traded[:, t]).astype(np.int32)
        prof_days += (ok & (p > min_amt)).astype(np.int32)
        best_day = np.where(ok, np.maximum(best_day, p), best_day)
        peak_eod = np.where(ok, np.maximum(peak_eod, bal), peak_eod)
        peak_intra = np.where(ok, np.maximum(pk_today, bal), peak_intra)

        if mode == "evaluation":
            profit = bal - b0
            done = ok & (profit >= rules.profit_target) & (traded_days >= rules.min_trading_days) \
                & (prof_days >= rules.min_profitable_days)
            if rules.consistency_pct:
                done &= best_day <= rules.consistency_pct / 100.0 * np.maximum(profit, 1e-9)
            status[done] = PASSED
            end_day[done] = t + 1
        elif payouts:
            elig = ok & ((t + 1 - last_pay) >= po.frequency_days) & ((bal - b0) >= po.threshold)
            amt = np.where(elig, np.minimum(po.max_withdrawal, bal - (b0 + po.min_balance)), 0.0)
            amt = np.maximum(amt, 0.0)
            paid = amt > 0
            bal = bal - amt
            pay_total += amt * po.profit_split
            first_pay_day = np.where(paid & (n_pay == 0), t + 1, first_pay_day)
            n_pay += paid.astype(np.int32)
            last_pay = np.where(paid, t + 1, last_pay)

    return {
        "status": status, "ftype": ftype, "end_day": end_day, "final_balance": bal, "horizon": horizon,
        "n_payouts": n_pay, "payout_total": pay_total, "first_payout_day": first_pay_day, "sims": sims,
        "risk_scale": risk_scale,
    }


def _hist(x: np.ndarray, bins: int = 30) -> dict:
    if len(x) == 0:
        return {"centers": [], "counts": []}
    c, e = np.histogram(x, bins=bins)
    return {"centers": ((e[:-1] + e[1:]) / 2).round(2).tolist(), "counts": c.tolist()}


def evaluation_summary(res: dict, rules: PropFirmRules) -> dict:
    s, ft, ed = res["status"], res["ftype"], res["end_day"]
    n = res["sims"]
    passed = s == PASSED
    days_to_pass = ed[passed]
    fail = s == FAILED
    return {
        "pass_probability": float(passed.mean()),
        "fail_probability": float(fail.mean()),
        "active_probability": float((s == ACTIVE).mean()),
        "median_days_to_pass": float(np.median(days_to_pass)) if passed.any() else None,
        "mean_days_to_pass": float(days_to_pass.mean()) if passed.any() else None,
        "p90_days_to_pass": float(np.percentile(days_to_pass, 90)) if passed.any() else None,
        "drawdown_failure_probability": float((fail & (ft == F_DD)).mean()),
        "daily_loss_failure_probability": float((fail & (ft == F_DAILY)).mean()),
        "other_failure_probability": float((fail & (ft == F_CONTRACTS)).mean()),
        "ending_balance_median": float(np.median(res["final_balance"])),
        "ending_balance_p5": float(np.percentile(res["final_balance"], 5)),
        "ending_balance_p95": float(np.percentile(res["final_balance"], 95)),
        "simulations": n,
        "horizon_days": res["horizon"],
        "ending_balance_hist": _hist(res["final_balance"]),
        "days_to_pass_hist": _hist(days_to_pass, bins=min(30, max(5, int(res["horizon"] // 3)))),
    }


def survival_summary(res: dict) -> dict:
    s, ed = res["status"], res["end_day"]
    horizon = res["horizon"]
    curve = []
    # survival at every 3rd trading day for the chart, plus the headline calendar horizons
    for d in sorted(set(list(range(0, horizon + 1, 3)) + [horizon])):
        curve.append({"trading_day": d, "survival": float(1.0 - ((s == FAILED) & (ed <= d)).mean())})
    marks = []
    for cal in SURVIVAL_CALENDAR_DAYS:
        td = trading_days_from_calendar(cal)
        use = min(td, horizon)
        marks.append({"calendar_days": cal, "trading_days": use,
                      "survival": float(1.0 - ((s == FAILED) & (ed <= use)).mean()),
                      "capped": td > horizon})
    return {"curve": curve, "marks": marks}


def payout_summary(res: dict, rules: PropFirmRules) -> dict:
    n = res["n_payouts"]
    failed_after = (res["status"] == FAILED) & (n >= 1)
    firsts = res["first_payout_day"][n >= 1]
    return {
        "prob_first_payout": float((n >= 1).mean()),
        "prob_second_payout": float((n >= 2).mean()),
        "prob_third_payout": float((n >= 3).mean()),
        "expected_total_payouts": float(res["payout_total"].mean()),
        "median_total_payouts_given_paid": float(np.median(res["payout_total"][n >= 1])) if (n >= 1).any() else 0.0,
        "expected_payout_count": float(n.mean()),
        "prob_lose_account_after_withdrawal": float(failed_after.mean()),
        "prob_lose_account_given_withdrawal": float(failed_after.sum() / max((n >= 1).sum(), 1)),
        "median_days_to_first_payout": float(np.median(firsts)) if len(firsts) else None,
        "payout_total_hist": _hist(res["payout_total"]),
        "horizon_days": res["horizon"],
        "profit_split": rules.payout.profit_split,
    }
