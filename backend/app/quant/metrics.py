"""Core performance statistics.

Assumptions (also documented in docs/QUANT_ASSUMPTIONS.md):
* Trade statistics use net P&L (after fees and slippage) unless a function says otherwise.
* Sharpe / Sortino use DAILY returns over every trading day in the test window
  (days without trades count as 0), annualised with sqrt(252). Risk-free rate = 0.
* Sortino's downside deviation is sqrt(mean(min(r - target, 0)^2)) over ALL observations.
* Drawdown is measured on closed-trade (end-of-day) equity, starting from the starting balance.
* Calmar = CAGR / max drawdown % (both computed on the same equity curve).
"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

TRADING_DAYS = 252


# ----------------------------------------------------------------- simple trade stats
def gross_profit(pnl: np.ndarray) -> float:
    return float(pnl[pnl > 0].sum()) if len(pnl) else 0.0


def gross_loss(pnl: np.ndarray) -> float:
    """Sum of losing trades, returned as a NEGATIVE number."""
    return float(pnl[pnl < 0].sum()) if len(pnl) else 0.0


def win_rate(pnl: np.ndarray) -> float:
    return float((pnl > 0).mean()) if len(pnl) else 0.0


def profit_factor(pnl: np.ndarray) -> float:
    gp, gl = gross_profit(pnl), abs(gross_loss(pnl))
    if gl == 0:
        return math.inf if gp > 0 else 0.0
    return gp / gl


def expectancy(pnl: np.ndarray) -> float:
    return float(pnl.mean()) if len(pnl) else 0.0


def average_winner(pnl: np.ndarray) -> float:
    w = pnl[pnl > 0]
    return float(w.mean()) if len(w) else 0.0


def average_loser(pnl: np.ndarray) -> float:
    """Average losing trade as a NEGATIVE number."""
    l = pnl[pnl < 0]
    return float(l.mean()) if len(l) else 0.0


def r_multiples(pnl: np.ndarray, risk_dollars: np.ndarray) -> np.ndarray:
    risk = np.where(risk_dollars > 0, risk_dollars, np.nan)
    return pnl / risk


# ----------------------------------------------------------------- risk-adjusted returns
def sharpe_ratio(returns: np.ndarray, periods: int = TRADING_DAYS, rf: float = 0.0) -> float:
    r = np.asarray(returns, dtype=float)
    if len(r) < 2:
        return 0.0
    excess = r - rf / periods
    sd = excess.std(ddof=1)
    if sd == 0 or not np.isfinite(sd):
        return 0.0
    return float(excess.mean() / sd * math.sqrt(periods))


def sortino_ratio(returns: np.ndarray, periods: int = TRADING_DAYS, target: float = 0.0) -> float:
    r = np.asarray(returns, dtype=float)
    if len(r) < 2:
        return 0.0
    diff = r - target
    downside = np.minimum(diff, 0.0)
    dd = math.sqrt(float((downside**2).mean()))
    if dd == 0:
        return math.inf if diff.mean() > 0 else 0.0
    return float(diff.mean() / dd * math.sqrt(periods))


# ----------------------------------------------------------------- drawdown
def max_drawdown(equity: np.ndarray) -> tuple[float, float]:
    """Return (max drawdown in $, max drawdown as fraction of the prior peak)."""
    eq = np.asarray(equity, dtype=float)
    if len(eq) == 0:
        return 0.0, 0.0
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    pct = np.where(peak > 0, dd / peak, 0.0)
    return float(dd.max()), float(pct.max())


def underwater(equity: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    eq = np.asarray(equity, dtype=float)
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    return dd, np.where(peak > 0, dd / peak, 0.0)


def drawdown_periods(dates: list, equity: np.ndarray, starting_balance: float) -> list[dict]:
    """Peak-to-recovery drawdown episodes sorted by depth (largest first)."""
    eq = np.asarray(equity, dtype=float)
    periods: list[dict] = []
    if len(eq) == 0:
        return periods
    peak_val, peak_idx = starting_balance, -1
    in_dd, bottom_idx, bottom_val = False, -1, peak_val

    def day(i: int):
        return dates[i] if i >= 0 else dates[0]

    for i, v in enumerate(eq):
        if v >= peak_val:
            if in_dd:
                periods.append(_period(dates, peak_idx, bottom_idx, i, peak_val, bottom_val))
                in_dd = False
            peak_val, peak_idx = v, i
            bottom_idx, bottom_val = i, v
        else:
            if not in_dd:
                in_dd, bottom_idx, bottom_val = True, i, v
            if v < bottom_val:
                bottom_idx, bottom_val = i, v
    if in_dd:
        periods.append(_period(dates, peak_idx, bottom_idx, None, peak_val, bottom_val))
    periods.sort(key=lambda p: p["depth"], reverse=True)
    return periods


def _period(dates, peak_idx, bottom_idx, rec_idx, peak_val, bottom_val) -> dict:
    start = dates[peak_idx] if peak_idx >= 0 else dates[0]
    bottom = dates[bottom_idx]
    recovery = dates[rec_idx] if rec_idx is not None else None
    end = recovery if recovery is not None else dates[-1]
    depth = peak_val - bottom_val
    return {
        "start": start,
        "bottom": bottom,
        "recovery": recovery,
        "depth": float(depth),
        "depth_pct": float(depth / peak_val) if peak_val > 0 else 0.0,
        "duration_days": int((end - start).days),
        "recovery_days": int((recovery - bottom).days) if recovery is not None else None,
    }


# ----------------------------------------------------------------- streaks
def streak_lengths(pnl: Iterable[float], winners: bool) -> list[int]:
    """Lengths of every consecutive run of winners (or losers). Break-even trades end a run."""
    runs, cur = [], 0
    for x in pnl:
        hit = x > 0 if winners else x < 0
        if hit:
            cur += 1
        else:
            if cur:
                runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return runs


def max_consecutive(pnl: Iterable[float], winners: bool) -> int:
    runs = streak_lengths(pnl, winners)
    return max(runs) if runs else 0


# ----------------------------------------------------------------- aggregation
def daily_frame(trades: pd.DataFrame, days: list, starting_balance: float) -> pd.DataFrame:
    """One row per trading day (including flat days) with equity and drawdown columns."""
    idx = pd.Index(pd.to_datetime(days).date, name="date")
    if len(trades):
        g = trades.groupby("date")
        agg = pd.DataFrame(
            {
                "net_pnl": g["net_pnl"].sum(),
                "gross_pnl": g["gross_pnl"].sum(),
                "trades": g["net_pnl"].size(),
                "wins": g["net_pnl"].apply(lambda s: int((s > 0).sum())),
                "max_contracts": g["quantity"].max(),
            }
        )
        df = agg.reindex(idx).fillna(0.0)
    else:
        df = pd.DataFrame(
            0.0, index=idx, columns=["net_pnl", "gross_pnl", "trades", "wins", "max_contracts"]
        )
    df["equity"] = starting_balance + df["net_pnl"].cumsum()
    peak = np.maximum.accumulate(np.concatenate([[starting_balance], df["equity"].to_numpy()]))[1:]
    df["drawdown"] = peak - df["equity"]
    df["drawdown_pct"] = np.where(peak > 0, df["drawdown"] / peak, 0.0)
    df["return"] = df["net_pnl"] / (df["equity"] - df["net_pnl"])
    return df.reset_index()


def compute_metrics(trades: pd.DataFrame, daily: pd.DataFrame, starting_balance: float) -> dict:
    """The full KPI set shown on the dashboard. Safe for empty trade sets."""
    pnl = trades["net_pnl"].to_numpy(dtype=float) if len(trades) else np.array([])
    gross = trades["gross_pnl"].to_numpy(dtype=float) if len(trades) else np.array([])
    n = len(pnl)
    wins = int((pnl > 0).sum())
    losses = int((pnl < 0).sum())
    avg_w, avg_l = average_winner(pnl), average_loser(pnl)
    eq = daily["equity"].to_numpy(dtype=float)
    dd_abs, dd_pct = max_drawdown(np.concatenate([[starting_balance], eq]))
    periods = drawdown_periods(list(daily["date"]), eq, starting_balance) if len(daily) else []
    net = float(pnl.sum())
    ndays = max(len(daily), 1)
    years = ndays / TRADING_DAYS
    end_eq = starting_balance + net
    cagr = (end_eq / starting_balance) ** (1 / years) - 1 if end_eq > 0 and years > 0 else -1.0
    rets = daily["return"].to_numpy(dtype=float) if len(daily) else np.array([])
    hold = trades["duration_minutes"].to_numpy(dtype=float) if n else np.array([])
    return {
        "net_profit": net,
        "gross_profit": gross_profit(pnl),
        "gross_loss": gross_loss(pnl),
        "total_trades": n,
        "winning_trades": wins,
        "losing_trades": losses,
        "win_rate": win_rate(pnl),
        "profit_factor": profit_factor(pnl),
        "expectancy": expectancy(pnl),
        "average_winner": avg_w,
        "average_loser": avg_l,
        "win_loss_ratio": (avg_w / abs(avg_l)) if avg_l else None,
        "sharpe": sharpe_ratio(rets),
        "sortino": sortino_ratio(rets),
        "calmar": (cagr / dd_pct) if dd_pct > 0 else None,
        "recovery_factor": (net / dd_abs) if dd_abs > 0 else None,
        "max_drawdown": dd_abs,
        "max_drawdown_pct": dd_pct,
        "average_drawdown": float(np.mean([p["depth"] for p in periods])) if periods else 0.0,
        "longest_drawdown_days": max([p["duration_days"] for p in periods], default=0),
        "max_consecutive_wins": max_consecutive(pnl, True),
        "max_consecutive_losses": max_consecutive(pnl, False),
        "largest_winner": float(pnl.max()) if n else 0.0,
        "largest_loser": float(pnl.min()) if n else 0.0,
        "average_holding_minutes": float(hold.mean()) if n else 0.0,
        "total_fees": float(trades["fees"].sum()) if n else 0.0,
        "slippage_cost": float(trades["slippage"].sum()) if n else 0.0,
        "gross_pnl_total": float(gross.sum()),
        "cagr": float(cagr),
        "return_pct": net / starting_balance,
        "trading_days": int(ndays),
        "avg_r": float(trades["r_multiple"].mean()) if n else 0.0,
        "ending_balance": end_eq,
    }
