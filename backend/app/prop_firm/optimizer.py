"""Risk-per-trade optimiser (generic account metrics + prop-firm outcomes)."""
from __future__ import annotations

import numpy as np

from ..models.prop import PropFirmRules
from . import montecarlo as pm
from .days import DayPool

DEFAULT_RISKS = [50, 75, 100, 125, 150, 175, 200, 250, 300, 400, 500]


def optimize_risk(
    pool: DayPool,
    rules: PropFirmRules,
    base_risk: float,
    risks: list[float] | None = None,
    sims: int = 1500,
    seed: int = 9,
    account_days: int = 60,
    contract_risk: float | None = None,
) -> dict:
    """`contract_risk` = typical $ risked by ONE contract in the backtest. Risk budgets below it cannot be
    traded with whole contracts (the engine would skip or oversize trades), so those rows are flagged and
    excluded from the 'best zone' - scaling P&L down linearly there would be fiction."""
    risks = risks or DEFAULT_RISKS
    rows = []
    for r in risks:
        scale = r / base_risk if base_risk > 0 else 1.0
        ev = pm.simulate(pool, rules, sims, rules.max_evaluation_days, scale, seed, "evaluation")
        evs = pm.evaluation_summary(ev, rules)
        fund = pm.simulate(pool, rules, sims, 126, scale, seed + 1, "funded", payouts=True)
        pay = pm.payout_summary(fund, rules)
        surv = pm.survival_summary(fund)
        # generic account stats over `account_days` days (no prop rules)
        rng = np.random.default_rng(seed + 2)
        idx = rng.integers(0, len(pool), size=(sims, account_days))
        paths = np.cumsum(pool.pnl[idx] * scale, axis=1)
        peak = np.maximum.accumulate(np.concatenate([np.zeros((sims, 1)), paths], axis=1), axis=1)[:, 1:]
        max_dd = (peak - paths).max(axis=1)
        pass_p = evs["pass_probability"]
        ev_per_attempt = pass_p * pay["expected_total_payouts"]
        rows.append({
            "risk_per_trade": r,
            "risk_scale": scale,
            "expected_return": float(paths[:, -1].mean()),
            "max_drawdown": float(np.median(max_dd)),
            "p95_max_drawdown": float(np.percentile(max_dd, 95)),
            "failure_probability": evs["fail_probability"],
            "pass_probability": pass_p,
            "median_days_to_pass": evs["median_days_to_pass"],
            "expected_payouts": pay["expected_total_payouts"],
            "payout_probability": pay["prob_first_payout"],
            "funded_survival_90d": next(m["survival"] for m in surv["marks"] if m["calendar_days"] == 90),
            "score": ev_per_attempt,
            "achievable": contract_risk is None or r >= contract_risk / 2,
            "oversized": contract_risk is not None and r < contract_risk,
        })
    ok = [x for x in rows if x["achievable"]] or rows
    scores = np.array([x["score"] for x in ok])
    best = ok[int(scores.argmax())]
    thresh = 0.9 * scores.max() if scores.max() > 0 else np.inf
    zone = [x["risk_per_trade"] for x in ok if x["score"] >= thresh]
    return {
        "rows": rows,
        "best_risk": best["risk_per_trade"] if scores.max() > 0 else None,
        "best_zone": [min(zone), max(zone)] if zone else None,
        "contract_risk": contract_risk,
        "note": ("No risk level has a positive expected payout - this strategy does not clear the prop rules profitably."
                 if scores.max() <= 0 else
                 "Results assume the backtest's future resembles its past. Rows flagged 'not achievable' risk less than "
                 "half the cost of one contract and are not tradable; 'oversized' rows risk more than budgeted per trade."),
        "score_definition": "Expected payout per evaluation attempt = P(pass) x E[trader payouts | funded 126 days]",
        "base_risk": base_risk,
    }
