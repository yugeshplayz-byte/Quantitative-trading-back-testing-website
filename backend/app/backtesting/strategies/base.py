"""Strategy interface.

A strategy turns market data into *signals*; the engine (engine.py) handles order execution,
sizing, stops, targets, fees and slippage. To add your own strategy:

1. subclass `BaseStrategy`, set `key`, `name`, `parameters`;
2. implement `compute_signals(md, params) -> Signals` (vectorised numpy is fine);
3. register it in `strategies/__init__.py`.

A signal on bar *i* is decided at that bar's CLOSE and executed at the next bar's open.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from ...models.config import ParameterSpec, Strategy
from ..market import MarketData


@dataclass
class Signals:
    side: list[int]  # +1 long, -1 short, 0 none
    setup: list[str]
    confidence: list[float]
    exit_long: list[bool]  # close an open long at next open
    exit_short: list[bool]
    entry_reason: dict[str, str] = field(default_factory=dict)  # (setup, side) -> text
    exit_reason: str = "Signal exit"


def allowed_window(tod: np.ndarray, start_after: float, end_before: float, session_minutes: int = 390) -> np.ndarray:
    return (tod >= start_after) & (tod <= session_minutes - end_before)


class BaseStrategy(ABC):
    key: str = ""
    name: str = ""
    description: str = ""
    default_symbol: str = "MNQ"
    parameters: list[ParameterSpec] = []

    def defaults(self) -> dict[str, float]:
        return {p.key: p.default for p in self.parameters}

    def resolve_params(self, overrides: dict[str, float] | None) -> dict[str, float]:
        merged = self.defaults()
        for k, v in (overrides or {}).items():
            if k in merged:
                merged[k] = float(v)
        return merged

    def signals(self, md: MarketData, params: dict[str, float], train_end: int = 0) -> Signals:
        """`train_end` = first bar index of the test window; only ML/custom strategies use it."""
        cache_key = (self.key, tuple(sorted(params.items())))
        hit = md.cache.get(cache_key)
        if hit is None:
            hit = self.compute_signals(md, params)
            if len(md.cache) > 400:
                md.cache.clear()
            md.cache[cache_key] = hit
        return hit

    @abstractmethod
    def compute_signals(self, md: MarketData, params: dict[str, float]) -> Signals: ...

    def info(self) -> Strategy:
        return Strategy(
            key=self.key,
            name=self.name,
            description=self.description,
            default_symbol=self.default_symbol,
            parameters=self.parameters,
        )
