from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..models.prop import PropFirmRules
from ..models.simulation import MonteCarloConfig, ParameterOptimizationRequest, WalkForwardRequest
from ..quant.ruin import risk_of_ruin
from ..services import analysis as AN
from ..services.store import load_bundle
from ..utils import clean
from .deps import SessionDep

router = APIRouter()


@router.post("/monte-carlo")
def monte_carlo(cfg: MonteCarloConfig, session=SessionDep):
    b = load_bundle(session, cfg.backtest_id)
    return clean(AN.monte_carlo(session, b, cfg))


class RuinRequest(BaseModel):
    account_size: float = Field(50_000, gt=0)
    allowed_drawdown: float = Field(2_500, gt=0)
    risk_per_trade: float | None = Field(None, gt=0)
    win_rate: float = Field(0.4, ge=0, le=1)
    avg_win: float = Field(300, gt=0)
    avg_loss: float = Field(100, gt=0)
    n_trades: int = Field(250, ge=1, le=20000)


@router.post("/risk-of-ruin")
def ruin(req: RuinRequest):
    r = risk_of_ruin(req.account_size, req.allowed_drawdown, req.risk_per_trade, req.win_rate, req.avg_win,
                     req.avg_loss, req.n_trades)
    # sensitivity curve: ruin vs risk per trade
    base = req.avg_loss
    curve = []
    for mult in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0):
        rr = risk_of_ruin(req.account_size, req.allowed_drawdown, base * mult, req.win_rate, req.avg_win,
                          req.avg_loss, req.n_trades, sims=800)
        curve.append({"risk_per_trade": base * mult, "risk_of_ruin": rr["risk_of_ruin"],
                      "drawdown_probability": rr["drawdown_probability"]})
    return clean({"result": r, "request": req.model_dump(), "sensitivity": curve})


class StressRequest(BaseModel):
    backtest_id: str = "BT-000001"
    runs: int = Field(300, ge=20, le=2000)


@router.post("/stress-test")
def stress(req: StressRequest, session=SessionDep):
    return clean(AN.stress(session, load_bundle(session, req.backtest_id), req.runs))


@router.post("/optimization")
def optimization(req: ParameterOptimizationRequest, session=SessionDep):
    b = load_bundle(session, req.backtest_id)
    prop = PropFirmRules(starting_balance=b.cfg.starting_balance) if req.metric == "prop_pass_probability" else None
    return clean(AN.optimization(session, b, req.param_x, req.param_y, req.metric, req.x_values, req.y_values, prop))


@router.post("/walk-forward")
def walk_forward(req: WalkForwardRequest, session=SessionDep):
    b = load_bundle(session, req.backtest_id)
    return clean(AN.walk_forward(session, b, req.train_months, req.test_months, req.step_months, req.metric,
                                 req.param_x, req.param_y, req.x_values, req.y_values))
