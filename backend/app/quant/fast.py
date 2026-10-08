"""Vectorised metric kernel for loops (stress tests, outlier removal, optimisation grids).

Matches `metrics.compute_metrics` for the shared fields but works on raw arrays, ~100x faster
than building DataFrames.
"""
from __future__ import annotations

import numpy as np

from . import metrics as M


def daily_pnl(net: np.ndarray, day_idx: np.ndarray, n_days: int) -> np.ndarray:
    return np.bincount(day_idx, weights=net, minlength=n_days).astype(float)


def fast_metrics(net: np.ndarray, day_idx: np.ndarray, n_days: int, bal: float) -> dict:
    net = np.asarray(net, dtype=float)
    d = daily_pnl(net, day_idx, n_days) if len(net) else np.zeros(n_days)
    eq = bal + np.cumsum(d)
    prev = np.concatenate([[bal], eq[:-1]])
    rets = d / prev
    dd, dd_pct = M.max_drawdown(np.concatenate([[bal], eq]))
    years = max(n_days, 1) / M.TRADING_DAYS
    end = bal + net.sum()
    cagr = (end / bal) ** (1 / years) - 1 if end > 0 else -1.0
    return {
        "trades": int(len(net)),
        "net_profit": float(net.sum()),
        "profit_factor": M.profit_factor(net),
        "win_rate": M.win_rate(net),
        "expectancy": M.expectancy(net),
        "sharpe": M.sharpe_ratio(rets),
        "sortino": M.sortino_ratio(rets),
        "max_drawdown": dd,
        "max_drawdown_pct": dd_pct,
        "calmar": (cagr / dd_pct) if dd_pct > 0 else 0.0,
        "cagr": cagr,
    }


def day_index(dates: list, days: list) -> np.ndarray:
    lookup = {d: i for i, d in enumerate(days)}
    return np.fromiter((lookup[d] for d in dates), dtype=int, count=len(dates))
