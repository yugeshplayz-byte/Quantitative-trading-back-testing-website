"""Risk of ruin (closed-form Brownian-motion approximation + seeded simulation check).

Model: per-trade P&L X is +W with probability p and -L otherwise (dollars, after optional
scaling to a different risk per trade). Cumulative P&L is approximated by Brownian motion with
drift mu = E[X] and variance sigma^2 = Var[X] per trade. For a barrier at drawdown D:

  * infinite horizon:   P(ruin)        = exp(-2 * mu * D / sigma^2)         (mu > 0; else 1)
  * n-trade horizon:    P(hit by n)    = Phi((-D - mu n)/(sigma sqrt n))
                                         + exp(-2 mu D / sigma^2) * Phi((-D + mu n)/(sigma sqrt n))

This ignores the discreteness of trade outcomes and path-dependent sizing, so treat it as an
approximation (the Monte Carlo cross-check uses the exact Bernoulli process).
"""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm


def risk_of_ruin(
    account_size: float,
    allowed_drawdown: float,
    risk_per_trade: float | None,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    n_trades: int,
    seed: int = 11,
    sims: int = 4000,
) -> dict:
    W, L = abs(avg_win), abs(avg_loss)
    scale = (risk_per_trade / L) if (risk_per_trade and L > 0) else 1.0
    W, L = W * scale, L * scale
    p = min(max(win_rate, 0.0), 1.0)
    mu = p * W - (1 - p) * L
    var = p * (1 - p) * (W + L) ** 2
    D = allowed_drawdown if allowed_drawdown > 0 else account_size
    sigma = math.sqrt(var) if var > 0 else 0.0

    if sigma == 0:
        ror_inf = 0.0 if mu > 0 else 1.0
        p_dd = ror_inf
    else:
        ror_inf = 1.0 if mu <= 0 else math.exp(-2 * mu * D / var)
        sq = sigma * math.sqrt(n_trades)
        if mu > 0:
            p_dd = float(norm.cdf((-D - mu * n_trades) / sq) + ror_inf * norm.cdf((-D + mu * n_trades) / sq))
        else:
            # negative drift: the barrier is hit with certainty as n grows; use the same first-passage form
            p_dd = float(norm.cdf((-D - mu * n_trades) / sq)
                         + math.exp(min(-2 * mu * D / var, 700)) * norm.cdf((-D + mu * n_trades) / sq))
            p_dd = min(p_dd, 1.0)

    rng = np.random.default_rng(seed)
    wins = rng.random((sims, n_trades)) < p
    steps = np.where(wins, W, -L)
    cum = np.cumsum(steps, axis=1)
    mc_hit = float((cum.min(axis=1) <= -D).mean())
    return {
        "risk_of_ruin": min(max(ror_inf, 0.0), 1.0),
        "drawdown_probability": min(max(p_dd, 0.0), 1.0),
        "survival_probability": 1.0 - min(max(p_dd, 0.0), 1.0),
        "monte_carlo_drawdown_probability": mc_hit,
        "monte_carlo_survival_probability": 1.0 - mc_hit,
        "expectancy_per_trade": mu,
        "std_per_trade": sigma,
        "scale_applied": scale,
        "edge_ratio": (mu / sigma) if sigma > 0 else None,
        "kelly_fraction": ((p * W - (1 - p) * L) / W) if W > 0 else None,
    }
