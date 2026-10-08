"""Prop-firm rule engine models. Rules are fully configurable - no firm's rules are hardcoded."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DrawdownType = Literal["static", "eod_trailing", "intraday_trailing"]
ChallengeStatus = Literal["PASS", "FAIL", "ACTIVE"]
FailureType = Literal["drawdown", "daily_loss", "contracts", "hours", "other", "none"]


class PayoutRules(BaseModel):
    threshold: float = 2_000.0  # profit above starting balance required before a request
    min_balance: float = 0.0  # balance that must remain after withdrawal, expressed as profit over start
    max_withdrawal: float = 5_000.0
    frequency_days: int = 14  # minimum trading days between payouts
    profit_split: float = Field(0.9, ge=0, le=1)


class PropFirmRules(BaseModel):
    name: str = "Generic 50K evaluation"
    starting_balance: float = 50_000.0
    profit_target: float = 3_000.0
    max_drawdown: float = 2_500.0
    daily_loss_limit: float | None = 1_100.0
    max_contracts: int = 10
    drawdown_type: DrawdownType = "eod_trailing"
    trailing_locks_at_start: bool = True  # trailing floor stops rising once it reaches the starting balance
    min_trading_days: int = 5
    consistency_pct: float | None = 50.0  # best day may not exceed this % of total profit
    min_profitable_days: int = 0
    min_profitable_day_amount: float = 0.0
    trading_start: str = "09:30"
    trading_end: str = "16:00"
    liquidation_time: str = "15:55"
    max_evaluation_days: int = 90
    payout: PayoutRules = Field(default_factory=PayoutRules)


class PropSimulationResult(BaseModel):
    status: ChallengeStatus
    failure_type: FailureType = "none"
    reason: str
    days_traded: int
    trading_days_elapsed: int
    final_balance: float
    peak_balance: float
    max_drawdown_used: float
    profit: float
    best_day: float
    equity_path: list[dict]
    checks: list[dict]
