"""Prop-firm services built on a stored backtest's day records."""
from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from ..models.prop import PropFirmRules
from ..prop_firm import montecarlo as pm
from ..prop_firm.optimizer import DEFAULT_RISKS, optimize_risk
from ..prop_firm.rules import evaluate_challenge
from .store import Bundle, cached, req_hash

TEMPLATES = [
    {"name": "Generic 25K static", "rules": {"starting_balance": 25000, "profit_target": 1500, "max_drawdown": 1500,
     "daily_loss_limit": 750, "max_contracts": 5, "drawdown_type": "static", "min_trading_days": 3,
     "consistency_pct": None}},
    {"name": "Generic 50K EOD trailing", "rules": {"starting_balance": 50000, "profit_target": 3000,
     "max_drawdown": 2000, "daily_loss_limit": 1000, "max_contracts": 10, "drawdown_type": "eod_trailing",
     "min_trading_days": 5, "consistency_pct": 50}},
    {"name": "Generic 100K intraday trailing", "rules": {"starting_balance": 100000, "profit_target": 6000,
     "max_drawdown": 3000, "daily_loss_limit": 2000, "max_contracts": 15, "drawdown_type": "intraday_trailing",
     "min_trading_days": 5, "consistency_pct": None}},
    {"name": "Generic 150K EOD trailing", "rules": {"starting_balance": 150000, "profit_target": 9000,
     "max_drawdown": 4500, "daily_loss_limit": None, "max_contracts": 15, "drawdown_type": "eod_trailing",
     "min_trading_days": 5, "consistency_pct": 40}},
]


def scale_for(b: Bundle, risk_per_trade: float | None) -> float:
    return (risk_per_trade / b.avg_risk) if risk_per_trade and b.avg_risk > 0 else 1.0


def simulate_single(b: Bundle, rules: PropFirmRules, start_day: int = 0) -> dict:
    res = evaluate_challenge(b.pool, rules, start_day)
    return res.model_dump()


def evaluation_mc(session: Session, b: Bundle, rules: PropFirmRules, sims: int, risk: float | None,
                  seed: int, block: int) -> dict:
    key = f"{b.id}:propmc:{req_hash([rules.model_dump(), sims, risk, seed, block])}"
    def go():
        r = pm.simulate(b.pool, rules, sims, rules.max_evaluation_days, scale_for(b, risk), seed, "evaluation", block)
        return {"summary": pm.evaluation_summary(r, rules), "risk_per_trade": risk or b.avg_risk,
                "base_risk": b.avg_risk}
    return cached(session, key, go)


def survival(session: Session, b: Bundle, rules: PropFirmRules, sims: int, risk: float | None, seed: int,
             block: int) -> dict:
    key = f"{b.id}:propsurv:{req_hash([rules.model_dump(), sims, risk, seed, block])}"
    def go():
        r = pm.simulate(b.pool, rules, sims, 262, scale_for(b, risk), seed, "funded", block)
        return pm.survival_summary(r)
    return cached(session, key, go)


def payouts(session: Session, b: Bundle, rules: PropFirmRules, sims: int, horizon: int, risk: float | None,
            seed: int, block: int) -> dict:
    key = f"{b.id}:proppay:{req_hash([rules.model_dump(), sims, horizon, risk, seed, block])}"
    def go():
        r = pm.simulate(b.pool, rules, sims, horizon, scale_for(b, risk), seed, "funded", block, payouts=True)
        return {**pm.payout_summary(r, rules), "survival": pm.survival_summary(r)}
    return cached(session, key, go)


def risk_optimizer(session: Session, b: Bundle, rules: PropFirmRules, risks: list[float] | None, sims: int,
                   seed: int) -> dict:
    key = f"{b.id}:propopt:{req_hash([rules.model_dump(), risks, sims, seed])}"
    def go():
        return optimize_risk(b.pool, rules, b.avg_risk, risks or DEFAULT_RISKS, sims, seed,
                             contract_risk=b.contract_risk)
    return cached(session, key, go)


def pass_probability_quick(b: Bundle, rules: PropFirmRules, sims: int = 600) -> float:
    r = pm.simulate(b.pool, rules, sims, rules.max_evaluation_days, 1.0, 3, "evaluation")
    return float(np.mean(r["status"] == pm.PASSED))
