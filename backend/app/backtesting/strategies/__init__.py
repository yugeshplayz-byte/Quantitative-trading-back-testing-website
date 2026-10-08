"""Strategy registry. Register new strategies here."""
from __future__ import annotations

from .base import BaseStrategy
from .mean_reversion import MeanReversionStrategy
from .orb import OpeningRangeBreakout
from .trend import TrendStrategy

STRATEGIES: dict[str, BaseStrategy] = {
    s.key: s for s in (TrendStrategy(), MeanReversionStrategy(), OpeningRangeBreakout())
}


def get_strategy(key: str) -> BaseStrategy:
    try:
        return STRATEGIES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown strategy {key!r}; available: {sorted(STRATEGIES)}") from exc
