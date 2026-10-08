"""High-level helpers: run a config, get trades + trading days + DataFrames."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..models.config import BacktestConfig
from ..quant.metrics import compute_metrics, daily_frame
from .engine import run_backtest
from .market import MarketData, get_market_data


@dataclass
class RunOutput:
    trades: list[dict]
    days: list
    md: MarketData
    lo: int
    hi: int


def days_between(md: MarketData, lo: int, hi: int) -> list:
    return list(pd.unique(md.df["date"].iloc[lo:hi]))


def run_config(cfg: BacktestConfig, lo: int | None = None, hi: int | None = None) -> RunOutput:
    md = get_market_data(cfg.symbol, cfg.seed, cfg.timeframe, cfg.data_model)
    if lo is None or hi is None:
        lo, hi = md.index_range(cfg.start_date, cfg.end_date)
    raw = run_backtest(md, cfg, lo, hi)
    trades = []
    for n, t in enumerate(raw, start=1):
        t["id"] = f"T-{n:06d}"
        trades.append(t)
    return RunOutput(trades=trades, days=days_between(md, lo, hi), md=md, lo=lo, hi=hi)


def trades_frame(trades: list[dict]) -> pd.DataFrame:
    cols = [
        "id", "symbol", "date", "entry_time", "exit_time", "direction", "entry_price", "exit_price",
        "quantity", "stop", "target", "gross_pnl", "fees", "slippage", "net_pnl", "r_multiple",
        "risk_dollars", "mae", "mfe", "mae_points", "mfe_points", "duration_minutes", "regime",
        "setup", "confidence", "atr_percentile", "entry_reason", "exit_reason", "entry_bar", "exit_bar",
    ]
    if not trades:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(trades)[cols].copy()
    df["entry_dt"] = pd.to_datetime(df["entry_time"])
    df["exit_dt"] = pd.to_datetime(df["exit_time"])
    return df


def quick_metrics(cfg: BacktestConfig, lo: int | None = None, hi: int | None = None) -> dict:
    """Run + summarise in one call (used by optimisation / walk-forward loops)."""
    out = run_config(cfg, lo, hi)
    tdf = trades_frame(out.trades)
    daily = daily_frame(tdf, out.days, cfg.starting_balance)
    return compute_metrics(tdf, daily, cfg.starting_balance)
