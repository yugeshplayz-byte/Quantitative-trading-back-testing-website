"""Opening-range breakout strategy."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ...models.config import ParameterSpec
from ..market import MarketData
from .base import BaseStrategy, Signals


class OpeningRangeBreakout(BaseStrategy):
    key = "orb"
    name = "Opening Range Breakout"
    description = (
        "Trades the first close beyond the opening range (high/low of the first N minutes), "
        "at most once per direction per day, until noon."
    )
    default_symbol = "MNQ"
    parameters = [
        ParameterSpec(key="or_minutes", label="Opening range (min)", default=30, min=15, max=60, step=15),
        ParameterSpec(key="buffer_ticks", label="Breakout buffer (ticks)", default=2, min=0, max=10, step=1),
        ParameterSpec(key="latest_entry", label="Latest entry (min from open)", default=150, min=60, max=300, step=30),
        ParameterSpec(key="max_or_atr", label="Max range / ATR", default=9, min=3, max=20, step=1),
    ]

    def compute_signals(self, md: MarketData, params: dict[str, float]) -> Signals:
        df = md.df
        orm = int(params["or_minutes"])
        in_or = (df["tod"] < orm).to_numpy()
        g = df["day_id"]
        or_high = df["high"].where(in_or).groupby(g).transform("max")
        or_low = df["low"].where(in_or).groupby(g).transform("min")
        tick = 0.25
        buf = params["buffer_ticks"] * tick
        after = (df["tod"] >= orm).to_numpy() & (df["tod"] <= params["latest_entry"]).to_numpy()
        width_ok = ((or_high - or_low).to_numpy() <= params["max_or_atr"] * np.asarray(md.atr))
        c = df["close"]
        brk_up = (c > or_high + buf).to_numpy() & after & width_ok
        brk_dn = (c < or_low - buf).to_numpy() & after & width_ok
        first_up = brk_up & (pd.Series(brk_up).groupby(g.to_numpy()).cumsum().to_numpy() == 1)
        first_dn = brk_dn & (pd.Series(brk_dn).groupby(g.to_numpy()).cumsum().to_numpy() == 1)
        side = np.zeros(len(df), dtype=np.int8)
        # if both fire on the same bar (cannot), long wins; otherwise take whichever occurs first
        side[first_up] = 1
        side[first_dn & ~first_up] = -1
        atr = np.asarray(md.atr)
        width = (or_high - or_low).to_numpy()
        conf = np.clip(80 - 40 * np.clip(width / (atr * params["max_or_atr"]), 0, 1)
                       + 20 * np.clip(np.abs(c.to_numpy() - (or_high + or_low).to_numpy() / 2) / np.maximum(width, 0.25) - 0.5, 0, 1), 0, 100)
        setup = np.where(side != 0, "ORB Breakout", "")
        none = [False] * len(df)
        return Signals(
            side=side.tolist(),
            setup=setup.tolist(),
            confidence=np.round(conf, 1).tolist(),
            exit_long=none,
            exit_short=none,
            entry_reason={
                "ORB Breakout|1": f"Closed above the {orm}-minute opening range high",
                "ORB Breakout|-1": f"Closed below the {orm}-minute opening range low",
            },
            exit_reason="Signal exit",
        )
