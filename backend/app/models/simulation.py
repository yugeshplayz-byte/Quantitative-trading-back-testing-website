"""Monte Carlo, optimisation and walk-forward models."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MonteCarloConfig(BaseModel):
    backtest_id: str = "BT-000001"
    simulations: int = Field(2000, ge=100, le=20000)
    trades: int = Field(250, ge=10, le=5000)
    starting_balance: float = Field(50_000.0, gt=0)
    risk_per_trade: float | None = Field(None, gt=0)  # $; None = keep the backtest's historical size
    seed: int = 7
    method: Literal["shuffle", "bootstrap", "block_bootstrap"] = "bootstrap"
    block_size: int = Field(5, ge=2, le=100)
    ruin_drawdown: float | None = Field(None, gt=0)  # $ loss from start that counts as ruin
    target_profit: float | None = Field(None, gt=0)


class MonteCarloResult(BaseModel):
    config: MonteCarloConfig
    summary: dict[str, float]
    fan: dict[str, list[float]]
    sample_paths: list[list[float]]
    ending_hist: dict[str, list[float]]
    drawdown_hist: dict[str, list[float]]
    streak_dist: dict[str, list[float]]


class ParameterOptimizationRequest(BaseModel):
    backtest_id: str = "BT-000001"
    param_x: str
    param_y: str
    x_values: list[float] | None = None
    y_values: list[float] | None = None
    metric: str = "sharpe"
    prop_rules_name: str | None = None


class ParameterOptimizationResult(BaseModel):
    param_x: str
    param_y: str
    x_values: list[float]
    y_values: list[float]
    metric: str
    grid: list[list[float | None]]
    trades_grid: list[list[int]]
    best: dict
    current: dict
    stability: dict
    runs: int


class WalkForwardRequest(BaseModel):
    backtest_id: str = "BT-000001"
    train_months: int = Field(6, ge=1, le=36)
    test_months: int = Field(2, ge=1, le=12)
    step_months: int = Field(2, ge=1, le=12)
    metric: str = "sharpe"
    param_x: str | None = None
    param_y: str | None = None
    x_values: list[float] | None = None
    y_values: list[float] | None = None


class WalkForwardWindow(BaseModel):
    index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    params: dict[str, float]
    is_metrics: dict[str, float]
    oos_metrics: dict[str, float]
    degradation: float | None
