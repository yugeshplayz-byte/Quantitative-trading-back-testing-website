"""Robustness stress tests applied to a finished trade list.

* Slippage: re-prices every market-type fill with N ticks of slippage. Entries are always market
  fills; exits are market fills unless the exit was a resting-limit "Target".
* Commission: scales the fee column.
* Missed trades: removes a random subset (seeded) many times and reports the distribution.
* Outliers: removes the best N trades and recomputes everything.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .fast import day_index, fast_metrics

SLIPPAGE_TICKS = [0, 1, 2, 3, 4, 5, 8]
COMMISSION_MULTIPLIERS = [1.0, 1.25, 1.5, 1.75, 2.0]
MISSED_LEVELS = [0.01, 0.05, 0.10, 0.20]


def _prep(df: pd.DataFrame, days: list) -> tuple[np.ndarray, np.ndarray, int]:
    return df["net_pnl"].to_numpy(dtype=float), day_index(list(df["date"]), days), len(days)


def _pick(m: dict) -> dict:
    keys = ("net_profit", "profit_factor", "sharpe", "sortino", "max_drawdown", "win_rate", "expectancy", "trades")
    return {k: m[k] for k in keys}


def baseline(df: pd.DataFrame, days: list, bal: float) -> dict:
    net, idx, n = _prep(df, days)
    return _pick(fast_metrics(net, idx, n, bal))


def slippage_test(df: pd.DataFrame, days: list, bal: float, tick_value: float, base_ticks: float) -> list[dict]:
    net, idx, n = _prep(df, days)
    qty = df["quantity"].to_numpy(dtype=float)
    market_exit = (df["exit_reason"] != "Target").to_numpy(dtype=float)
    fills = 1.0 + market_exit
    out = []
    for ticks in SLIPPAGE_TICKS:
        adj = net - (ticks - base_ticks) * tick_value * qty * fills
        out.append({"ticks": ticks, **_pick(fast_metrics(adj, idx, n, bal))})
    return out


def commission_test(df: pd.DataFrame, days: list, bal: float) -> list[dict]:
    net, idx, n = _prep(df, days)
    fees = df["fees"].to_numpy(dtype=float)
    out = []
    for m in COMMISSION_MULTIPLIERS:
        adj = net - (m - 1.0) * fees
        out.append({"multiplier": m, "label": "Current" if m == 1.0 else f"+{int(round((m - 1) * 100))}%",
                    **_pick(fast_metrics(adj, idx, n, bal))})
    return out


def missed_trades_test(df: pd.DataFrame, days: list, bal: float, runs: int = 300, seed: int = 21) -> list[dict]:
    net, idx, n = _prep(df, days)
    rng = np.random.default_rng(seed)
    out = []
    for lvl in MISSED_LEVELS:
        keep_n = max(1, int(round(len(net) * (1 - lvl))))
        rows = []
        for _ in range(runs):
            keep = np.sort(rng.choice(len(net), size=keep_n, replace=False))
            rows.append(fast_metrics(net[keep], idx[keep], n, bal))
        def agg(key: str) -> dict:
            v = np.array([r[key] for r in rows], dtype=float)
            v = v[np.isfinite(v)]
            return {"mean": float(v.mean()), "p5": float(np.percentile(v, 5)), "p95": float(np.percentile(v, 95))}
        out.append({
            "removed_pct": lvl * 100, "runs": runs,
            "net_profit": agg("net_profit"), "max_drawdown": agg("max_drawdown"),
            "sharpe": agg("sharpe"), "profit_factor": agg("profit_factor"),
            "prob_profitable": float(np.mean([r["net_profit"] > 0 for r in rows])),
        })
    return out


def outlier_test(df: pd.DataFrame, days: list, bal: float) -> dict:
    net, idx, n = _prep(df, days)
    order = np.argsort(-net)
    total = float(net.sum())
    cases = [("None", 0), ("Best trade", 1), ("Top 5", 5), ("Top 10", 10),
             ("Top 1%", max(1, int(round(len(net) * 0.01)))), ("Top 5%", max(1, int(round(len(net) * 0.05))))]
    rows = []
    for label, k in cases:
        keep = np.ones(len(net), dtype=bool)
        keep[order[:k]] = False
        m = _pick(fast_metrics(net[keep], idx[keep], n, bal))
        rows.append({"label": label, "removed": k, **m})
    gp = float(net[net > 0].sum())
    share10 = float(net[order[:10]].clip(min=0).sum() / gp) if gp > 0 else 0.0
    share5pct = rows[-1]
    top1 = rows[-2]
    dependent = (rows[-1]["net_profit"] <= 0) or (share10 > 0.5)
    warn, severity = None, None
    if total > 0 and (top1["net_profit"] <= 0 or share10 > 0.5):
        severity = "high"
        warn = (f"Net profit turns negative after removing the top 1% of trades." if top1["net_profit"] <= 0
                else f"The 10 best trades supply {share10:.0%} of gross profit - high outlier dependence.")
    elif total > 0 and rows[-1]["net_profit"] <= 0:
        severity = "medium"
        warn = ("Net profit turns negative after removing the top 5% of trades. Common for low-win-rate trend "
                "systems, but results rely on a small set of large winners.")
    return {"rows": rows, "top10_share_of_gross_profit": share10, "dependent": bool(dependent),
            "warning": warn, "severity": severity, "net_profit_after_top5pct": share5pct["net_profit"]}
