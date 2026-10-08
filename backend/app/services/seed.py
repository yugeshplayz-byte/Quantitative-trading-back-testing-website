"""Deterministic demo content created on first start (when the database is empty)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import BacktestRow, PresetRow
from ..models.config import (BacktestConfig, ExecutionConfig, ManagementConfig, RiskConfig, StopConfig,
                             TargetConfig, TradingConfig)
from ..models.prop import PropFirmRules
from .store import create_backtest


def demo_configs() -> dict[str, BacktestConfig]:
    v1 = BacktestConfig(strategy="mnq_trend", symbol="MNQ", name="MNQ Trend V1", params={"fast": 5, "slow": 21})
    v2 = BacktestConfig(
        strategy="mnq_trend", symbol="MNQ", name="MNQ Trend V2", params={"fast": 5, "slow": 34, "min_er": 0.2},
        stop=StopConfig(type="atr", value=1.25), target=TargetConfig(type="risk_reward", value=3.0),
        management=ManagementConfig(breakeven=True, breakeven_trigger_r=1.0, trailing_stop=True, trail_atr_mult=2.0))
    mr = BacktestConfig(
        strategy="mes_mean_reversion", symbol="MES", name="MES Mean Reversion",
        params={"z_entry": 3.2, "lookback": 45}, stop=StopConfig(type="atr", value=1.5),
        target=TargetConfig(type="risk_reward", value=1.5), risk=RiskConfig(risk_dollars=100))
    orb = BacktestConfig(
        strategy="orb", symbol="MNQ", name="MNQ Opening Range Breakout", params={"or_minutes": 30},
        stop=StopConfig(type="structure", value=2), target=TargetConfig(type="risk_reward", value=2.0),
        trading=TradingConfig(max_trades_per_day=2))
    cons = v1.model_copy(deep=True, update={"name": "Conservative Prop"})
    cons.risk = RiskConfig(risk_dollars=75, daily_loss_limit=600, consecutive_loss_limit=2)
    cons.trading = TradingConfig(max_trades_per_day=3, max_contracts=5)
    aggr = v1.model_copy(deep=True, update={"name": "Aggressive Prop"})
    aggr.risk = RiskConfig(risk_dollars=250, daily_loss_limit=1500, consecutive_loss_limit=4)
    aggr.trading = TradingConfig(max_trades_per_day=6, max_contracts=15)
    return {"v1": v1, "v2": v2, "mr": mr, "orb": orb, "cons": cons, "aggr": aggr}


def seed_presets(session: Session) -> None:
    c = demo_configs()
    cons_rules = PropFirmRules(name="Conservative 50K", starting_balance=50000, profit_target=3000, max_drawdown=2000,
                               daily_loss_limit=600, max_contracts=5, drawdown_type="eod_trailing")
    aggr_rules = PropFirmRules(name="Aggressive 50K", starting_balance=50000, profit_target=3000, max_drawdown=2500,
                               daily_loss_limit=1500, max_contracts=15, drawdown_type="eod_trailing")
    items = [
        ("MNQ Trend V1", "EMA 5/21 trend follower, 1 ATR stop, 3R target.", c["v1"], None),
        ("MNQ Trend V2", "Slower EMA pair with breakeven and ATR trailing stop.", c["v2"], None),
        ("MES Mean Reversion", "VWAP z-score fade on MES.", c["mr"], None),
        ("Conservative Prop", "MNQ Trend V1 at $75 risk with tight daily limits.", c["cons"], cons_rules),
        ("Aggressive Prop", "MNQ Trend V1 at $250 risk, more trades per day.", c["aggr"], aggr_rules),
    ]
    for name, desc, cfg, rules in items:
        session.add(PresetRow(name=name, description=desc, config=cfg.model_dump(mode="json"),
                              prop_rules=rules.model_dump(mode="json") if rules else None))
    session.commit()


def seed_if_empty(session: Session) -> bool:
    if session.scalar(select(func.count()).select_from(BacktestRow)):
        return False
    c = demo_configs()
    for key, ver, notes in (("v1", "v1", "Baseline trend system."), ("v2", "v2", "V1 with breakeven + trailing management."),
                            ("mr", "v1", "Marginal edge - a useful contrast for robustness checks."),
                            ("orb", "v1", "Opening range breakout, max 2 trades per day.")):
        create_backtest(session, c[key], c[key].name, notes=notes, version=ver, tags=["demo"])
    if not session.scalar(select(func.count()).select_from(PresetRow)):
        seed_presets(session)
    return True
