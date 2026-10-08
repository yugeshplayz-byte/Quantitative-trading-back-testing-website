"""Configuration models for backtests, risk and execution."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ParameterSpec(BaseModel):
    key: str
    label: str
    default: float
    min: float
    max: float
    step: float


class Strategy(BaseModel):
    """A strategy available in the library (a Python class registered in backtesting/strategies)."""

    key: str
    name: str
    description: str
    default_symbol: str
    parameters: list[ParameterSpec]


class TradingConfig(BaseModel):
    long_enabled: bool = True
    short_enabled: bool = True
    max_trades_per_day: int = Field(4, ge=1, le=50)
    max_contracts: int = Field(10, ge=1, le=200)
    entry_delay_bars: int = Field(0, ge=0, le=10)
    exit_delay_bars: int = Field(0, ge=0, le=10)


class RiskConfig(BaseModel):
    sizing_mode: Literal["fixed_contracts", "fixed_dollar", "percent"] = "fixed_dollar"
    contracts: int = Field(2, ge=1)
    risk_dollars: float = Field(150.0, gt=0)
    risk_pct: float = Field(0.5, gt=0, le=20)
    daily_loss_limit: float | None = 1000.0
    max_drawdown: float | None = None
    consecutive_loss_limit: int | None = 3


class StopConfig(BaseModel):
    type: Literal["fixed_point", "fixed_dollar", "atr", "structure"] = "atr"
    value: float = Field(1.5, gt=0)  # points | dollars per contract | ATR multiple | buffer (ticks)


class TargetConfig(BaseModel):
    type: Literal["fixed_point", "risk_reward", "atr"] = "risk_reward"
    value: float = Field(2.0, gt=0)


class ManagementConfig(BaseModel):
    breakeven: bool = False
    breakeven_trigger_r: float = Field(1.0, gt=0)
    trailing_stop: bool = False
    trail_atr_mult: float = Field(1.5, gt=0)
    partial_profit: bool = False
    partial_pct: float = Field(0.5, gt=0, lt=1)
    partial_at_r: float = Field(1.0, gt=0)
    scale_in: bool = False
    scale_in_at_r: float = Field(0.75, gt=0)
    scale_out: bool = False


class ExecutionConfig(BaseModel):
    commission_per_side: float = Field(0.35, ge=0)  # $ per contract per side
    exchange_fee_per_side: float = Field(0.37, ge=0)  # $ per contract per side
    slippage_ticks: float = Field(1.0, ge=0)  # per market-type fill
    spread_ticks: float = Field(0.5, ge=0)  # full spread; half crossed per market fill
    latency_ms: int = Field(0, ge=0, le=5000)  # extra adverse slip: 1 tick per 500ms, entries only
    # Resting limit orders (targets, partials) fill only if price trades THROUGH the level by this many
    # ticks - merely touching it is not assumed to get filled (queue position). 0 = optimistic touch fills.
    limit_through_ticks: float = Field(1.0, ge=0, le=10)


class BacktestConfig(BaseModel):
    strategy: str = "mnq_trend"
    symbol: Literal["MNQ", "NQ", "MES", "ES"] = "MNQ"
    start_date: date = date(2023, 1, 2)
    end_date: date = date(2024, 12, 31)
    starting_balance: float = Field(50_000.0, gt=0)
    timeframe: Literal["5m", "15m"] = "5m"
    session: Literal["RTH", "ETH"] = "RTH"
    params: dict[str, float] = Field(default_factory=dict)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    stop: StopConfig = Field(default_factory=StopConfig)
    target: TargetConfig = Field(default_factory=TargetConfig)
    management: ManagementConfig = Field(default_factory=ManagementConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    seed: int = 42  # seeds the (synthetic) market-data generator
    # "random_walk": no exploitable structure (honest default). "structured": engineered edge, validation only.
    # "real": your own CSV data in backend/data/real (see docs/REAL_DATA.md).
    data_model: Literal["random_walk", "structured", "real"] = "random_walk"
    name: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class StrategyPreset(BaseModel):
    id: int | None = None
    name: str
    description: str = ""
    config: BacktestConfig
    prop_rules: "PropFirmRules | None" = None
    created_at: datetime | None = None


from .prop import PropFirmRules  # noqa: E402  (resolve forward reference)

StrategyPreset.model_rebuild()
