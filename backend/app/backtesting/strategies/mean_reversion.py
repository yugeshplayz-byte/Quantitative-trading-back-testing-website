"""VWAP z-score mean-reversion strategy."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ...models.config import ParameterSpec
from ..market import MarketData
from .base import BaseStrategy, Signals, allowed_window


class MeanReversionStrategy(BaseStrategy):
    key = "mes_mean_reversion"
    name = "VWAP Mean Reversion"
    description = (
        "Fades stretched moves away from VWAP (z-score of price vs VWAP) once price turns, "
        "targeting a return to VWAP. Avoids the highest-volatility conditions."
    )
    default_symbol = "MES"
    parameters = [
        ParameterSpec(key="lookback", label="Z-score lookback (bars)", default=30, min=15, max=60, step=5),
        ParameterSpec(key="z_entry", label="Entry z-score", default=2.0, min=1.2, max=3.0, step=0.2),
        ParameterSpec(key="max_atr_pct", label="Skip above ATR percentile (100 = off)", default=100, min=50, max=100, step=5),
        ParameterSpec(key="max_er", label="Skip if efficiency ratio above (1 = off)", default=1.0, min=0.1, max=1.0, step=0.05),
        ParameterSpec(key="start_after", label="No entries first N min", default=30, min=0, max=60, step=5),
        ParameterSpec(key="end_before", label="No entries last N min", default=45, min=0, max=120, step=15),
    ]

    def compute_signals(self, md: MarketData, params: dict[str, float]) -> Signals:
        df = md.df
        c = df["close"]
        dev = c - pd.Series(md.vwap, index=df.index)
        lb = int(params["lookback"])
        sd = dev.rolling(lb, min_periods=lb).std()
        z = (dev / sd.replace(0, np.nan)).fillna(0.0).to_numpy()
        turn_up = (c > df["open"]).to_numpy()
        turn_dn = (c < df["open"]).to_numpy()
        zin = params["z_entry"]
        ok = allowed_window(df["tod"].to_numpy(), params["start_after"], params["end_before"])
        ok &= np.asarray(md.atr_pct) <= params["max_atr_pct"]
        ok &= md.er <= params["max_er"]
        long_s = (z < -zin) & turn_up & ok
        short_s = (z > zin) & turn_dn & ok
        side = np.zeros(len(df), dtype=np.int8)
        side[long_s] = 1
        side[short_s] = -1
        extreme = np.abs(z) >= 1.5 * zin
        setup = np.where(side != 0, np.where(extreme, "Band Extreme", "VWAP Fade"), "")
        atr_pct = np.asarray(md.atr_pct)
        conf = np.clip(50 + 25 * np.clip((np.abs(z) - zin) / max(zin, 0.1), 0, 1) + 25 * (1 - atr_pct / 100), 0, 100)
        return Signals(
            side=side.tolist(),
            setup=setup.tolist(),
            confidence=np.round(conf, 1).tolist(),
            exit_long=(z >= 0).tolist(),
            exit_short=(z <= 0).tolist(),
            entry_reason={
                "VWAP Fade|1": f"Price stretched below VWAP (z < -{zin:g}); bullish bar",
                "VWAP Fade|-1": f"Price stretched above VWAP (z > {zin:g}); bearish bar",
                "Band Extreme|1": f"Extreme stretch below VWAP (|z| >= {1.5 * zin:g}); bullish bar",
                "Band Extreme|-1": f"Extreme stretch above VWAP (|z| >= {1.5 * zin:g}); bearish bar",
            },
            exit_reason="Reverted to VWAP",
        )
