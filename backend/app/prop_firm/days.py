"""Collapse a trade list into per-day records used by the prop-firm engine.

For each trading day we keep the closed P&L, the worst/best intraday equity excursion (using each
trade's MAE/MFE on top of the running closed P&L), peak contracts and activity flags.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DayPool:
    dates: list
    pnl: np.ndarray
    low: np.ndarray  # worst intraday equity relative to the day's start (<= min(0, pnl))
    high: np.ndarray  # best intraday equity relative to the day's start (>= max(0, pnl))
    max_contracts: np.ndarray
    traded: np.ndarray  # bool
    last_exit_min: np.ndarray  # minutes after 09:30 of the last exit (0 if none)

    def __len__(self) -> int:
        return len(self.pnl)


def build_day_pool(df: pd.DataFrame, days: list) -> DayPool:
    n = len(days)
    pnl, low, high = np.zeros(n), np.zeros(n), np.zeros(n)
    maxc, traded, last_exit = np.zeros(n, dtype=int), np.zeros(n, dtype=bool), np.zeros(n)
    lookup = {d: i for i, d in enumerate(days)}
    if len(df):
        for d, g in df.sort_values("exit_dt").groupby("date"):
            i = lookup.get(d)
            if i is None:
                continue
            cum = 0.0
            lo, hi = 0.0, 0.0
            for r in g.itertuples():
                lo = min(lo, cum - r.mae)
                hi = max(hi, cum + r.mfe)
                cum += r.net_pnl
                lo, hi = min(lo, cum), max(hi, cum)
            pnl[i], low[i], high[i] = cum, lo, hi
            maxc[i] = int(g["quantity"].max())
            traded[i] = True
            ex = g["exit_dt"].max()
            last_exit[i] = ex.hour * 60 + ex.minute - (9 * 60 + 30)
    return DayPool(list(days), pnl, low, high, maxc, traded, last_exit)
