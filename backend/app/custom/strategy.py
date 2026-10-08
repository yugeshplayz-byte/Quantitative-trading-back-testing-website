"""Adapter that makes pasted user code look like any other strategy to the engine."""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from ..backtesting.market import MarketData
from ..backtesting.strategies.base import BaseStrategy, Signals
from ..models.config import ParameterSpec
from .runner import run_worker


def bars_frame(md: MarketData) -> pd.DataFrame:
    """The DataFrame handed to user code: OHLCV + tod (minutes since 09:30), day_id, atr, vwap."""
    hit = md.cache.get("__bars_frame__")
    if hit is None:
        df = md.df[["ts", "date", "open", "high", "low", "close", "volume", "tod", "day_id"]].copy()
        df["atr"] = np.asarray(md.atr)
        df["vwap"] = md.vwap
        md.cache["__bars_frame__"] = hit = df
    return hit


class CustomStrategy(BaseStrategy):
    def __init__(self, sid: int, name: str, description: str, code: str, parameters: list[dict]):
        self.key = f"custom:{sid}"
        self.name = name
        self.description = description
        self.code = code
        self.code_hash = hashlib.sha1(code.encode("utf-8")).hexdigest()[:12]
        self.parameters = [ParameterSpec(**p) for p in parameters]
        self.default_symbol = "MNQ"
        self.last_lookahead: dict | None = None

    def _ckey(self, params: dict, train_end: int) -> tuple:
        return (self.key, self.code_hash, tuple(sorted(params.items())), train_end)

    def signals(self, md: MarketData, params: dict[str, float], train_end: int = 0) -> Signals:
        ck = self._ckey(params, train_end)
        hit = md.cache.get(ck)
        if hit is None:
            self.prefetch(md, [params], train_end)
            hit = md.cache[ck]
        return hit

    def prefetch(self, md: MarketData, param_sets: list[dict], train_end: int,
                 check_lookahead: bool = False) -> dict | None:
        """Compute signals for several parameter sets in ONE sandbox process and cache them."""
        todo = [p for p in param_sets if self._ckey(p, train_end) not in md.cache]
        if not todo and not check_lookahead:
            return self.last_lookahead
        todo = todo or param_sets[:1]
        res = run_worker(self.code, bars_frame(md), "run", train_end, len(md.df), todo, check_lookahead)
        for r in res["results"]:
            md.cache[self._ckey(r["params"], train_end)] = Signals(
                side=r["side"], setup=r["setup"], confidence=r["confidence"],
                exit_long=r["exit_long"], exit_short=r["exit_short"],
                entry_reason={}, exit_reason="Model exit signal")
        if check_lookahead:
            self.last_lookahead = res.get("lookahead")
        return self.last_lookahead

    def compute_signals(self, md: MarketData, params: dict[str, float]) -> Signals:  # pragma: no cover
        return self.signals(md, params)
