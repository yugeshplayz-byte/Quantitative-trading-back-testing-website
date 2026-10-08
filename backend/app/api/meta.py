from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..backtesting.instruments import INSTRUMENTS
from ..backtesting.strategies import STRATEGIES
from ..config import get_settings, git_commit
from ..db import CustomStrategyRow, get_session
from ..prop_firm.optimizer import DEFAULT_RISKS
from ..data.events import EVENT_TYPES
from ..data.synthetic import REGIMES
from ..models.config import BacktestConfig
from ..utils import clean

router = APIRouter()
VERSION = "0.1.0"


@router.get("/health")
def health():
    return {"status": "ok", "version": VERSION}


@router.get("/meta")
def meta(session: Session = Depends(get_session)):
    s = get_settings()
    customs = session.scalars(select(CustomStrategyRow).order_by(CustomStrategyRow.id)).all()
    return clean({
        "version": VERSION, "git_commit": git_commit(), "environment": s.environment,
        "instruments": [vars(i) for i in INSTRUMENTS.values()],
        "strategies": [st.info() for st in STRATEGIES.values()] + [
            {"key": f"custom:{c.id}", "name": c.name, "description": c.description or "Custom Python strategy",
             "default_symbol": "MNQ", "custom": True,
             "parameters": [{"key": k, **v} for k, v in (c.params or {}).items()]} for c in customs],
        "regimes": REGIMES, "event_types": EVENT_TYPES, "risk_levels": DEFAULT_RISKS,
        "timeframes": ["5m", "15m"], "sessions": ["RTH", "ETH"],
        "default_config": BacktestConfig().model_dump(mode="json"),
        "custom_code": {"enabled": s.enable_custom_code, "token_required": bool(s.custom_code_token)},
        "data_source": {"kind": "synthetic", "note": "Deterministic synthetic futures data (seeded). "
                        "Results illustrate platform features - they are NOT evidence of live profitability."},
        "caveats": CAVEATS,
    })


CAVEATS = [
    "Data: the demo market is synthetic. The default 'random_walk' model has no exploitable edge by design; "
    "the 'structured' model is engineered for platform validation only. Neither says anything about real markets.",
    "Fills: signals execute on the next bar's open; stops fill before targets when both trade in one bar; limit "
    "targets fill only when price trades through them; fees and slippage are charged on every fill. Real fills can be worse.",
    "Costs are assumptions (commission, exchange fee, slippage, spread). Check them against your broker and the stress tests.",
    "Optimisation grids and the 'best' parameters are IN-SAMPLE. Picking the best of many variants is selection bias; "
    "only walk-forward / out-of-sample results are evidence.",
    "Monte Carlo and prop-firm simulations resample the trades or days this backtest already produced; they cannot prove "
    "the edge is real and assume the future resembles the past.",
    "A profit is only meaningful if it is statistically distinguishable from luck - see the p-value and 95% interval on expectancy.",
    "Custom strategies: the lookahead check is a strong hint, not proof. Train ML models only on data before the test window.",
]
