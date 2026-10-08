"""Futures contract specifications (CME equity index futures)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    tick_size: float
    tick_value: float  # $ per tick per contract
    point_value: float  # $ per point per contract
    start_price: float  # price level of the synthetic series on its first bar
    daily_vol: float  # annualised-equivalent typical daily move used by the synthetic generator
    group: str  # instruments in the same group share one underlying (e.g. MNQ & NQ)


INSTRUMENTS: dict[str, Instrument] = {
    "MNQ": Instrument("MNQ", "Micro E-mini Nasdaq-100", 0.25, 0.50, 2.0, 15500.0, 0.0090, "nasdaq"),
    "NQ": Instrument("NQ", "E-mini Nasdaq-100", 0.25, 5.00, 20.0, 15500.0, 0.0090, "nasdaq"),
    "MES": Instrument("MES", "Micro E-mini S&P 500", 0.25, 1.25, 5.0, 4000.0, 0.0070, "sp500"),
    "ES": Instrument("ES", "E-mini S&P 500", 0.25, 12.50, 50.0, 4000.0, 0.0070, "sp500"),
}


def get_instrument(symbol: str) -> Instrument:
    try:
        return INSTRUMENTS[symbol]
    except KeyError as exc:
        raise ValueError(f"Unsupported symbol {symbol!r}; choose from {sorted(INSTRUMENTS)}") from exc
