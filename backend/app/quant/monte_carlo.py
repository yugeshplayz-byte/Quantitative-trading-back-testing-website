"""Monte Carlo equity simulation (reshuffle, bootstrap, block bootstrap).

All randomness comes from `numpy.random.default_rng(seed)`, so identical inputs give identical
results. Trade P&L is optionally rescaled to a different risk per trade:
    scaled_pnl = pnl * (risk_per_trade / base_risk)
where base_risk is the backtest's average initial risk in dollars.
"""
from __future__ import annotations

import math

import numpy as np

from ..models.simulation import MonteCarloConfig


def sample_indices(n_hist: int, n_trades: int, sims: int, method: str, block: int, rng: np.random.Generator) -> np.ndarray:
    if method == "shuffle":
        reps = math.ceil(n_trades / n_hist)
        perms = [rng.random((sims, n_hist)).argsort(axis=1) for _ in range(reps)]
        return np.concatenate(perms, axis=1)[:, :n_trades]
    if method == "bootstrap":
        return rng.integers(0, n_hist, size=(sims, n_trades))
    if method == "block_bootstrap":
        nb = math.ceil(n_trades / block)
        starts = rng.integers(0, n_hist, size=(sims, nb))
        idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n_hist  # circular blocks
        return idx.reshape(sims, nb * block)[:, :n_trades]
    raise ValueError(f"Unknown method {method!r}")


def longest_losing_streak(x: np.ndarray) -> np.ndarray:
    """Longest run of losing trades per simulation (rows)."""
    cur = np.zeros(x.shape[0], dtype=np.int32)
    best = np.zeros(x.shape[0], dtype=np.int32)
    for t in range(x.shape[1]):
        cur = np.where(x[:, t] < 0, cur + 1, 0)
        best = np.maximum(best, cur)
    return best


def _downsample(n_steps: int, max_points: int = 120) -> np.ndarray:
    if n_steps + 1 <= max_points:
        return np.arange(n_steps + 1)
    return np.unique(np.linspace(0, n_steps, max_points).round().astype(int))


def _hist(x: np.ndarray, bins: int = 40) -> dict:
    counts, edges = np.histogram(x, bins=bins)
    return {"centers": ((edges[:-1] + edges[1:]) / 2).round(2).tolist(), "counts": counts.tolist()}


def run_monte_carlo(pnl: np.ndarray, base_risk: float, cfg: MonteCarloConfig) -> dict:
    pnl = np.asarray(pnl, dtype=float)
    if len(pnl) < 5:
        raise ValueError("Need at least 5 trades to run a Monte Carlo simulation")
    rng = np.random.default_rng(cfg.seed)
    scale = (cfg.risk_per_trade / base_risk) if (cfg.risk_per_trade and base_risk > 0) else 1.0
    idx = sample_indices(len(pnl), cfg.trades, cfg.simulations, cfg.method, cfg.block_size, rng)
    draws = pnl[idx] * scale
    start = cfg.starting_balance
    paths = start + np.concatenate([np.zeros((cfg.simulations, 1)), np.cumsum(draws, axis=1)], axis=1)
    ending = paths[:, -1]
    peak = np.maximum.accumulate(paths, axis=1)
    max_dd = (peak - paths).max(axis=1)
    streak = longest_losing_streak(draws)
    ruin_dd = cfg.ruin_drawdown if cfg.ruin_drawdown else 0.2 * start
    target = cfg.target_profit if cfg.target_profit else 0.1 * start
    ruined = paths.min(axis=1) <= start - ruin_dd
    hit_target = paths.max(axis=1) >= start + target

    q = [5, 25, 50, 75, 95]
    cols = _downsample(cfg.trades)
    fan_all = np.percentile(paths[:, cols], q, axis=0)
    fan = {"steps": cols.tolist(), **{f"p{k}": fan_all[i].round(2).tolist() for i, k in enumerate(q)}}
    sample = [paths[i, cols].round(2).tolist() for i in range(min(40, cfg.simulations))]
    s_counts = np.bincount(streak)
    summary = {
        "median_ending_balance": float(np.median(ending)),
        "p5_ending_balance": float(np.percentile(ending, 5)),
        "p95_ending_balance": float(np.percentile(ending, 95)),
        "mean_ending_balance": float(ending.mean()),
        "median_return_pct": float((np.median(ending) / start - 1) * 100),
        "median_max_drawdown": float(np.median(max_dd)),
        "p95_max_drawdown": float(np.percentile(max_dd, 95)),
        "prob_profit": float((ending > start).mean()),
        "prob_ruin": float(ruined.mean()),
        "prob_hit_target": float(hit_target.mean()),
        "expected_longest_losing_streak": float(streak.mean()),
        "p95_longest_losing_streak": float(np.percentile(streak, 95)),
        "ruin_level": float(start - ruin_dd),
        "target_level": float(start + target),
        "risk_scale": float(scale),
        "historical_trades": int(len(pnl)),
    }
    return {
        "summary": summary,
        "fan": fan,
        "sample_paths": sample,
        "ending_hist": _hist(ending),
        "drawdown_hist": _hist(max_dd),
        "streak_dist": {"lengths": list(range(len(s_counts))),
                        "probability": (s_counts / s_counts.sum()).round(5).tolist()},
    }
