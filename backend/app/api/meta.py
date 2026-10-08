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
    })
