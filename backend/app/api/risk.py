from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..models.prop import PropFirmRules
from ..services import prop as PR
from ..services import risk as RK
from ..services.store import Bundle, load_bundle
from ..utils import clean
from .deps import SessionDep, get_bundle

router = APIRouter()


class SizeRequest(BaseModel):
    symbol: str = "MNQ"
    account_balance: float = Field(50_000, gt=0)
    risk_dollars: float | None = Field(150, gt=0)
    risk_pct: float | None = Field(None, gt=0, le=20)
    stop_points: float = Field(25, gt=0)
    win_rate: float | None = Field(None, ge=0, le=1)
    avg_win_r: float | None = Field(None, gt=0)
    max_contracts: int = 100


@router.post("/risk/position-size")
def position_size(req: SizeRequest):
    return clean(RK.position_size(req.symbol, req.account_balance, req.risk_dollars, req.risk_pct, req.stop_points,
                                  req.win_rate, req.avg_win_r, req.max_contracts))


class SizingCompareRequest(BaseModel):
    backtest_id: str = "BT-000001"
    balance: float = 50_000
    fixed_risk: float = 150
    pct_risk: float = 0.5
    fixed_contracts: int = 2


@router.post("/risk/sizing-comparison")
def sizing(req: SizingCompareRequest, session=SessionDep):
    b = load_bundle(session, req.backtest_id)
    return clean(RK.sizing_comparison(b, req.balance, req.fixed_risk, req.pct_risk, req.fixed_contracts))


@router.get("/backtests/{bid}/losing-streaks")
def losing_streaks(b: Bundle = Depends(get_bundle)):
    return clean(RK.losing_streak_report(b))


class RiskOptRequest(BaseModel):
    backtest_id: str = "BT-000001"
    account_size: float = 50_000
    max_drawdown: float = 2_500
    risks: list[float] | None = None
    simulations: int = Field(1500, ge=200, le=8000)


@router.post("/risk/optimizer")
def risk_optimizer(req: RiskOptRequest, session=SessionDep):
    """Generic account view of the risk-per-trade sweep (uses a plain trailing-drawdown rule set)."""
    b = load_bundle(session, req.backtest_id)
    rules = PropFirmRules(name="Risk sweep", starting_balance=req.account_size, max_drawdown=req.max_drawdown,
                          profit_target=req.account_size * 0.06, daily_loss_limit=req.max_drawdown * 0.5,
                          drawdown_type="eod_trailing")
    return clean(PR.risk_optimizer(session, b, rules, req.risks, req.simulations, 9))
