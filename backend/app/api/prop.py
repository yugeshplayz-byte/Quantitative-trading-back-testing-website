from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..models.prop import PropFirmRules
from ..services import prop as PR
from ..services.store import load_bundle
from ..utils import clean
from .deps import SessionDep

router = APIRouter(prefix="/prop-firm")


class PropRequest(BaseModel):
    backtest_id: str = "BT-000001"
    rules: PropFirmRules = Field(default_factory=PropFirmRules)
    simulations: int = Field(2000, ge=100, le=20000)
    risk_per_trade: float | None = Field(None, gt=0)
    seed: int = 5
    block_size: int = Field(1, ge=1, le=20)


class SimulateRequest(BaseModel):
    backtest_id: str = "BT-000001"
    rules: PropFirmRules = Field(default_factory=PropFirmRules)
    start_day: int = Field(0, ge=0)


class PayoutRequest(PropRequest):
    horizon_days: int = Field(180, ge=20, le=600)


class OptimizerRequest(BaseModel):
    backtest_id: str = "BT-000001"
    rules: PropFirmRules = Field(default_factory=PropFirmRules)
    risks: list[float] | None = None
    simulations: int = Field(1500, ge=200, le=8000)
    seed: int = 9


@router.get("/templates")
def templates():
    return PR.TEMPLATES


@router.post("/simulate")
def simulate(req: SimulateRequest, session=SessionDep):
    return clean(PR.simulate_single(load_bundle(session, req.backtest_id), req.rules, req.start_day))


@router.post("/monte-carlo")
def monte_carlo(req: PropRequest, session=SessionDep):
    b = load_bundle(session, req.backtest_id)
    return clean(PR.evaluation_mc(session, b, req.rules, req.simulations, req.risk_per_trade, req.seed, req.block_size))


@router.post("/survival")
def survival(req: PropRequest, session=SessionDep):
    b = load_bundle(session, req.backtest_id)
    return clean(PR.survival(session, b, req.rules, req.simulations, req.risk_per_trade, req.seed, req.block_size))


@router.post("/payouts")
def payouts(req: PayoutRequest, session=SessionDep):
    b = load_bundle(session, req.backtest_id)
    return clean(PR.payouts(session, b, req.rules, req.simulations, req.horizon_days, req.risk_per_trade, req.seed,
                            req.block_size))


@router.post("/optimizer")
def optimizer(req: OptimizerRequest, session=SessionDep):
    b = load_bundle(session, req.backtest_id)
    return clean(PR.risk_optimizer(session, b, req.rules, req.risks, req.simulations, req.seed))
