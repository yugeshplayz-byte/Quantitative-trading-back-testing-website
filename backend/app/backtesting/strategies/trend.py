"""EMA-cross / pullback trend-following strategy with a VWAP filter."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ...models.config import ParameterSpec
from ..market import MarketData
from .base import BaseStrategy, Signals, allowed_window


class TrendStrategy(BaseStrategy):
    key = "mnq_trend"
    name = "Trend Follower (EMA + VWAP)"
    description = (
        "Trades EMA crosses and pullbacks to the fast EMA in the direction of the trend, "
        "filtered by VWAP. Exits on an opposite EMA cross, stop, target or end of day."
    )
    default_symbol = "MNQ"
    parameters = [
        ParameterSpec(key="fast", label="Fast EMA", default=5, min=3, max=21, step=2),
        ParameterSpec(key="slow", label="Slow EMA", default=21, min=15, max=60, step=5),
        ParameterSpec(key="vwap_filter", label="VWAP filter (0/1)", default=1, min=0, max=1, step=1),
        ParameterSpec(key="min_er", label="Min efficiency ratio", default=0.15, min=0.0, max=0.5, step=0.05),
        ParameterSpec(key="start_after", label="No entries first N min", default=15, min=0, max=60, step=5),
        ParameterSpec(key="end_before", label="No entries last N min", default=60, min=0, max=120, step=15),
    ]

    def compute_signals(self, md: MarketData, params: dict[str, float]) -> Signals:
        df = md.df
        c, o, lo = df["close"], df["open"], df["low"]
        hi = df["high"]
        fast, slow = int(params["fast"]), int(params["slow"])
        if fast >= slow:
            slow = fast + 1
        g = df["day_id"]
        ef = c.ewm(span=fast, adjust=False).mean()
        es = c.ewm(span=slow, adjust=False).mean()
        ef_p, es_p = ef.shift(1), es.shift(1)
        cross_up = ((ef > es) & (ef_p <= es_p)).to_numpy()
        cross_dn = ((ef < es) & (ef_p >= es_p)).to_numpy()
        vwap = pd.Series(md.vwap, index=df.index)
        use_vwap = params["vwap_filter"] >= 0.5
        above = (c > vwap).to_numpy() if use_vwap else np.ones(len(df), bool)
        below = (c < vwap).to_numpy() if use_vwap else np.ones(len(df), bool)
        slope = es.diff(3).to_numpy()
        up_trend = ((ef > es) & (es.diff(3) > 0)).to_numpy()
        dn_trend = ((ef < es) & (es.diff(3) < 0)).to_numpy()
        pull_long = up_trend & (lo <= ef).to_numpy() & (c > ef).to_numpy() & (c > o).to_numpy() & above
        pull_short = dn_trend & (hi >= ef).to_numpy() & (c < ef).to_numpy() & (c < o).to_numpy() & below
        ok = allowed_window(df["tod"].to_numpy(), params["start_after"], params["end_before"])
        ok &= md.er >= params["min_er"]  # skip choppy, directionless tape
        long_x, short_x = cross_up & above & ok, cross_dn & below & ok
        long_p, short_p = pull_long & ok & ~long_x, pull_short & ok & ~short_x

        side = np.zeros(len(df), dtype=np.int8)
        side[long_p | long_x] = 1
        side[short_p | short_x] = -1
        setup = np.where(long_x | short_x, "EMA Cross", np.where(long_p | short_p, "Pullback", ""))

        atr = np.asarray(md.atr)
        strength = np.clip(np.abs(ef - es).to_numpy() / atr, 0, 1.5) / 1.5 * 60
        vdist = np.clip(np.abs(c.to_numpy() - md.vwap) / atr, 0, 2) / 2 * 25
        volfit = 15 * (1 - np.abs(np.asarray(md.atr_pct) - 50) / 50)
        conf = np.clip(strength + vdist + volfit, 0, 100)
        del slope, g
        return Signals(
            side=side.tolist(),
            setup=setup.tolist(),
            confidence=np.round(conf, 1).tolist(),
            exit_long=cross_dn.tolist(),
            exit_short=cross_up.tolist(),
            entry_reason={
                "EMA Cross|1": f"EMA{fast} crossed above EMA{slow}; price above VWAP",
                "EMA Cross|-1": f"EMA{fast} crossed below EMA{slow}; price below VWAP",
                "Pullback|1": f"Pullback to EMA{fast} in an uptrend, closed back above",
                "Pullback|-1": f"Pullback to EMA{fast} in a downtrend, closed back below",
            },
            exit_reason="Opposite EMA cross",
        )
