"""Market data container with the common indicators every strategy/engine needs.

EVERY indicator here is causal: the value at bar i uses only bars <= i (trailing windows,
expanding/EWM statistics, per-day cumulative sums). `tests/test_no_lookahead.py` verifies this by
truncating the data and checking that nothing computed for earlier bars changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd

from ..data.synthetic import load_bars

ATR_LEN = 14
ATR_RANK_WINDOW = 2340  # ~30 trading days of 5m bars
REGIME_ER_BARS = 78  # one 5m session of history for the trend/range test


@dataclass
class MarketData:
    symbol: str
    seed: int
    timeframe: str
    data_model: str
    bar_minutes: int
    df: pd.DataFrame
    ts: np.ndarray  # datetime64[ns]
    o: list[float]
    h: list[float]
    l: list[float]
    c: list[float]
    day_id: list[int]
    tod: list[int]
    regime: list[str]
    atr: list[float]
    atr_pct: list[float]
    is_last: list[bool]
    swing_low: list[float]
    swing_high: list[float]
    vwap: np.ndarray
    er: np.ndarray  # Kaufman efficiency ratio (24 bars): ~0 choppy, ~1 one-directional
    cache: dict = field(default_factory=dict)

    def index_range(self, start, end) -> tuple[int, int]:
        """Bar index range [lo, hi) covering start..end inclusive (dates)."""
        lo = int(np.searchsorted(self.ts, np.datetime64(pd.Timestamp(start), "ns"), side="left"))
        hi = int(np.searchsorted(self.ts, np.datetime64(pd.Timestamp(end) + pd.Timedelta(days=1), "ns"), side="left"))
        return lo, hi

    def stamp(self, i: int, offset_min: float = 0.0) -> str:
        t = pd.Timestamp(self.ts[i]) + pd.Timedelta(minutes=float(offset_min))
        return t.strftime("%Y-%m-%dT%H:%M:%S")


def causal_regime(df: pd.DataFrame, atr_pct: pd.Series, bar_minutes: int) -> np.ndarray:
    """Classify each bar using ONLY trailing information (never a hindsight label).

    Priority: High/Low Volatility (ATR percentile >= 80 / <= 20), then Trending / Ranging by the
    efficiency ratio over the last session, otherwise Bull / Bear / Neutral by price vs a slow EMA
    and that EMA's one-session slope.
    """
    c = df["close"]
    n = max(REGIME_ER_BARS * 5 // bar_minutes, 10)
    er = (c.diff(n).abs() / c.diff().abs().rolling(n, min_periods=n).sum()).fillna(0.0)
    ema = c.ewm(span=n * 5, adjust=False).mean()
    slope = ema - ema.shift(n)
    ap = atr_pct.to_numpy()
    cond = [ap >= 80, ap <= 20, er.to_numpy() >= 0.16, er.to_numpy() <= 0.05,
            ((c > ema) & (slope > 0)).to_numpy(), ((c < ema) & (slope < 0)).to_numpy()]
    labels = ["High Volatility", "Low Volatility", "Trending", "Ranging", "Bull", "Bear"]
    return np.select(cond, labels, default="Neutral")


def build_market_data(df: pd.DataFrame, symbol: str, seed: int, timeframe: str, data_model: str) -> MarketData:
    """Compute indicators for ANY bar frame (also used by tests on truncated data)."""
    df = df.reset_index(drop=True)
    bar_minutes = 5 if timeframe == "5m" else 15
    c = df["close"]
    pc = c.shift(1).fillna(df["open"])
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / ATR_LEN, adjust=False, min_periods=ATR_LEN).mean()
    atr = atr.fillna(tr.expanding().mean())  # warm-up uses only past bars (never back-fills from the future)
    window = ATR_RANK_WINDOW * 5 // bar_minutes
    atr_pct = (atr.rolling(window, min_periods=100).rank(pct=True) * 100).fillna(50.0)
    typical = (df["high"] + df["low"] + c) / 3
    pv = typical * df["volume"]
    g = df["day_id"]
    vwap = (pv.groupby(g).cumsum() / df["volume"].groupby(g).cumsum()).to_numpy()
    is_last = (g.shift(-1) != g).fillna(True).to_numpy()
    er_n = 24
    er = (c.diff(er_n).abs() / c.diff().abs().rolling(er_n, min_periods=er_n).sum()).fillna(0.0).to_numpy()
    return MarketData(
        symbol=symbol, seed=seed, timeframe=timeframe, data_model=data_model, bar_minutes=bar_minutes, df=df,
        ts=df["ts"].to_numpy(dtype="datetime64[ns]"), o=df["open"].tolist(), h=df["high"].tolist(),
        l=df["low"].tolist(), c=c.tolist(), day_id=df["day_id"].tolist(), tod=df["tod"].tolist(),
        regime=causal_regime(df, atr_pct, bar_minutes).tolist(), atr=atr.tolist(), atr_pct=atr_pct.tolist(),
        is_last=is_last.tolist(), swing_low=df["low"].rolling(10, min_periods=1).min().tolist(),
        swing_high=df["high"].rolling(10, min_periods=1).max().tolist(), vwap=vwap, er=er)


@lru_cache(maxsize=12)
def get_market_data(symbol: str, seed: int, timeframe: str, data_model: str = "random_walk") -> MarketData:
    return build_market_data(load_bars(symbol, seed, timeframe, data_model), symbol, seed, timeframe, data_model)
