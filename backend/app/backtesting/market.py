"""Market data container with the common indicators every strategy/engine needs."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd

from ..data.synthetic import load_bars

ATR_LEN = 14
ATR_RANK_WINDOW = 2340  # ~30 trading days of 5m bars


@dataclass
class MarketData:
    symbol: str
    seed: int
    timeframe: str
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
        hi = int(
            np.searchsorted(
                self.ts, np.datetime64(pd.Timestamp(end) + pd.Timedelta(days=1), "ns"), side="left"
            )
        )
        return lo, hi

    def stamp(self, i: int, offset_min: float = 0.0) -> str:
        t = pd.Timestamp(self.ts[i]) + pd.Timedelta(minutes=float(offset_min))
        return t.strftime("%Y-%m-%dT%H:%M:%S")


@lru_cache(maxsize=12)
def get_market_data(symbol: str, seed: int, timeframe: str) -> MarketData:
    df = load_bars(symbol, seed, timeframe).reset_index(drop=True)
    c = df["close"]
    pc = c.shift(1).fillna(df["open"])
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / ATR_LEN, adjust=False, min_periods=ATR_LEN).mean().bfill()
    window = int(ATR_RANK_WINDOW * 5 / (5 if timeframe == "5m" else 15))
    atr_pct = (atr.rolling(window, min_periods=100).rank(pct=True) * 100).fillna(50.0)
    typical = (df["high"] + df["low"] + c) / 3
    pv = typical * df["volume"]
    g = df["day_id"]
    vwap = (pv.groupby(g).cumsum() / df["volume"].groupby(g).cumsum()).to_numpy()
    is_last = (g.shift(-1) != g).fillna(True).to_numpy()
    er_n = 24
    er = (c.diff(er_n).abs() / c.diff().abs().rolling(er_n, min_periods=er_n).sum()).fillna(0.0).to_numpy()
    swing_low = df["low"].rolling(10, min_periods=1).min()
    swing_high = df["high"].rolling(10, min_periods=1).max()
    return MarketData(
        symbol=symbol,
        seed=seed,
        timeframe=timeframe,
        bar_minutes=5 if timeframe == "5m" else 15,
        df=df,
        ts=df["ts"].to_numpy(dtype="datetime64[ns]"),
        o=df["open"].tolist(),
        h=df["high"].tolist(),
        l=df["low"].tolist(),
        c=c.tolist(),
        day_id=df["day_id"].tolist(),
        tod=df["tod"].tolist(),
        regime=df["regime"].tolist(),
        atr=atr.tolist(),
        atr_pct=atr_pct.tolist(),
        is_last=is_last.tolist(),
        swing_low=swing_low.tolist(),
        swing_high=swing_high.tolist(),
        vwap=vwap,
        er=er,
    )
