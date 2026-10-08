"""Trade-level and result models."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from .config import BacktestConfig


class TradeEvent(BaseModel):
    """Notable intra-trade event drawn on the trade chart (scale in/out, breakeven, trail)."""

    time: str
    price: float
    kind: Literal["scale_in", "scale_out", "breakeven", "trail"]
    quantity: int = 0


class Trade(BaseModel):
    id: str
    symbol: str
    date: date
    entry_time: str  # ISO timestamp (US/Eastern wall clock, naive)
    exit_time: str
    direction: Literal["Long", "Short"]
    entry_price: float
    exit_price: float
    quantity: int
    stop: float
    target: float | None
    gross_pnl: float
    fees: float
    slippage: float
    net_pnl: float
    r_multiple: float
    risk_dollars: float
    mae: float  # dollars, positive magnitude
    mfe: float  # dollars, positive magnitude
    mae_points: float
    mfe_points: float
    duration_minutes: float
    regime: str
    setup: str
    confidence: float
    atr_percentile: float
    entry_reason: str
    exit_reason: str
    entry_bar: int = 0
    exit_bar: int = 0
    events: list[TradeEvent] = Field(default_factory=list)


class DailyPerformance(BaseModel):
    date: date
    net_pnl: float
    gross_pnl: float
    trades: int
    wins: int
    equity: float
    drawdown: float
    drawdown_pct: float
    max_contracts: int = 0


class DrawdownPeriod(BaseModel):
    start: date
    bottom: date
    recovery: date | None
    depth: float
    depth_pct: float
    duration_days: int
    recovery_days: int | None


class BacktestResult(BaseModel):
    id: str  # BT-000001
    name: str
    config: BacktestConfig
    metrics: dict[str, float | int | None]
    created_at: datetime
    git_commit: str
    trade_count: int
    tags: list[str] = Field(default_factory=list)
    favorite: bool = False
    notes: str = ""
    version: str = "v1"
