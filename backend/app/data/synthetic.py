"""Deterministic synthetic intraday futures data.

This stands in for real market data so the whole platform works out of the box. It is fully
seeded: the same (symbol, seed, model) always yields identical bars.

TWO MARKET MODELS (selected by `BacktestConfig.data_model`):

* ``random_walk`` (the DEFAULT): honest baseline with NO exploitable structure. Returns are
  uncorrelated, fat-tailed (Student-t, 5 d.o.f.), with a U-shaped intraday volatility profile and
  volatility clustering (calm / normal / turbulent days). Because nothing here is predictable,
  a sound backtester should report that strategies have no edge, and costs make them lose.
  This is the data the demo backtests run on.

* ``structured``: an ENGINEERED market - trending days with momentum, ranging days with
  mean-reversion, drift on bull/bear days. It exists purely to VALIDATE the platform (does it
  find an edge that is known to exist?). Profits on this model say nothing about real markets.

MNQ/NQ share one underlying and MES/ES another (~0.9 correlated).

To use real data later, implement `load_bars(...)` returning the same columns (`BAR_COLUMNS`);
nothing else in the platform needs to change. The generator's own day label (`gen_regime`) is
never shown to strategies - market regimes are re-derived causally from price (backtesting/market.py).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.signal import lfilter

from ..backtesting.instruments import get_instrument

BARS_PER_DAY = 78
EPOCH_START = "2022-01-03"
EPOCH_END = "2025-12-31"
BAR_COLUMNS = ["ts", "date", "open", "high", "low", "close", "volume", "gen_regime", "tod", "day_id"]
DATA_MODELS = ("random_walk", "structured")  # synthetic generators ("real" is handled by data/real.py)
REGIMES = ["Trending", "Ranging", "Bull", "Bear", "Neutral", "High Volatility", "Low Volatility"]

# structured model: (vol multiplier, AR(1) coefficient per bar, drift in bar-sigmas, weight)
_STRUCT_PARAMS = {
    "Trending": (1.00, 0.30, 0.000, 0.15),
    "Ranging": (0.80, -0.15, 0.000, 0.20),
    "Bull": (0.90, 0.06, 0.045, 0.14),
    "Bear": (1.20, 0.06, -0.055, 0.10),
    "Neutral": (1.00, 0.00, 0.000, 0.18),
    "High Volatility": (1.90, 0.10, 0.000, 0.11),
    "Low Volatility": (0.55, -0.05, 0.000, 0.10),
}
_STRUCT_KAPPA = {"Ranging": 0.06, "Low Volatility": 0.05}  # mean reversion toward the day's open
# random-walk model: volatility states only
_RW_STATES = {"Normal": (1.0, 0.60), "Turbulent": (1.8, 0.20), "Calm": (0.6, 0.20)}
_TAIL_DOF = 5
_U_SHAPE = None


def _u_shape() -> np.ndarray:
    """Intraday volatility profile: heavy at the open and the close, quiet at lunch."""
    global _U_SHAPE
    if _U_SHAPE is None:
        x = np.linspace(0, 1, BARS_PER_DAY)
        prof = 0.55 + 1.6 * np.exp(-x / 0.07) + 0.9 * np.exp(-(1 - x) / 0.10)
        _U_SHAPE = prof / np.sqrt((prof**2).mean())
    return _U_SHAPE


def trading_days(start: str = EPOCH_START, end: str = EPOCH_END) -> pd.DatetimeIndex:
    """Weekdays (no holiday calendar in the synthetic data)."""
    return pd.bdate_range(start, end)


def _sticky_path(rng: np.random.Generator, names: list[str], weights: np.ndarray, n: int, stay: float) -> list[str]:
    path, cur = [], int(rng.choice(len(names), p=weights))
    for _ in range(n):
        if rng.random() > stay:
            cur = int(rng.choice(len(names), p=weights))
        path.append(names[cur])
    return path


@lru_cache(maxsize=8)
def _day_states(seed: int, n_days: int, model: str) -> tuple[str, ...]:
    rng = np.random.default_rng(seed + 101)
    if model == "structured":
        names = list(_STRUCT_PARAMS)
        w = np.array([_STRUCT_PARAMS[k][3] for k in names])
        return tuple(_sticky_path(rng, names, w / w.sum(), n_days, 0.58))
    names = list(_RW_STATES)
    w = np.array([_RW_STATES[k][1] for k in names])
    return tuple(_sticky_path(rng, names, w / w.sum(), n_days, 0.80))


@lru_cache(maxsize=4)
def _shared_noise(seed: int, n_days: int) -> tuple[np.ndarray, np.ndarray]:
    mkt = np.random.default_rng(seed + 202).standard_normal((n_days, BARS_PER_DAY))
    chi2 = np.random.default_rng(seed + 808).chisquare(_TAIL_DOF, (n_days, BARS_PER_DAY))
    tail = np.sqrt((_TAIL_DOF - 2) / chi2)  # Student-t scaling with unit variance
    return mkt, tail


@lru_cache(maxsize=16)
def generate_5m_bars(symbol: str, seed: int = 42, model: str = "random_walk") -> pd.DataFrame:
    if model not in DATA_MODELS:
        raise ValueError(f"Unknown data model {model!r}; choose from {DATA_MODELS}")
    inst = get_instrument(symbol)
    days = trading_days()
    n_days = len(days)
    states = _day_states(seed, n_days, model)
    mkt, tail = _shared_noise(seed, n_days)
    idio_seed = 303 if inst.group == "nasdaq" else 404
    idio = np.random.default_rng(seed + idio_seed).standard_normal((n_days, BARS_PER_DAY))
    rho = 1.0 if inst.group == "nasdaq" else 0.9
    eps = (rho * mkt + np.sqrt(1 - rho**2) * idio) * tail
    gap_rng = np.random.default_rng(seed + 505)
    wick_rng = np.random.default_rng(seed + 606)
    vol_rng = np.random.default_rng(seed + 707)
    dir_rng = np.random.default_rng(seed + 909)

    bar_sigma = inst.daily_vol / np.sqrt(BARS_PER_DAY)
    profile = _u_shape()
    tick = inst.tick_size
    shape = (n_days, BARS_PER_DAY)
    opens, highs, lows, closes, vols = (np.empty(shape) for _ in range(5))

    last_close = inst.start_price
    for d in range(n_days):
        st = states[d]
        if model == "structured":
            vol_mult, phi, drift, _ = _STRUCT_PARAMS[st]
            kappa = _STRUCT_KAPPA.get(st, 0.0)
            if st == "Trending":
                drift = 0.09 * (1.0 if dir_rng.random() < 0.5 else -1.0)  # direction independent of the shocks
        else:
            vol_mult, phi, drift, kappa = _RW_STATES[st][0], 0.0, 0.0, 0.0
        sigma = bar_sigma * vol_mult * profile
        x = sigma * eps[d] + drift * bar_sigma * vol_mult
        gap = gap_rng.normal(0, inst.daily_vol * 0.35)
        o_first = last_close * np.exp(gap)
        if kappa == 0.0:
            r = lfilter([1.0], [1.0, -phi], x) if phi else x
            logp = np.log(o_first) + np.concatenate([[0.0], np.cumsum(r)[:-1]])
        else:
            anchor = np.log(o_first)
            lp, r_prev = anchor, 0.0
            r = np.empty(BARS_PER_DAY)
            logp = np.empty(BARS_PER_DAY)
            for k in range(BARS_PER_DAY):
                logp[k] = lp
                r_k = phi * r_prev + x[k] - kappa * (lp - anchor)
                r[k] = r_k
                lp += r_k
                r_prev = r_k
        o = np.exp(logp)
        c = np.exp(logp + r)
        wick = np.abs(wick_rng.standard_normal((2, BARS_PER_DAY))) * sigma * 0.35
        opens[d], closes[d] = o, c
        highs[d] = np.maximum(o, c) * np.exp(wick[0])
        lows[d] = np.minimum(o, c) * np.exp(-wick[1])
        vols[d] = (900.0 * profile * vol_mult * np.exp(vol_rng.normal(0, 0.25, BARS_PER_DAY))
                   * (1 + 4 * np.abs(r) / bar_sigma))
        last_close = c[-1]

    def q(a: np.ndarray) -> np.ndarray:
        return np.round(a / tick) * tick

    o, h, l, c = q(opens), q(highs), q(lows), q(closes)
    h = np.maximum.reduce([h, o, c])
    l = np.minimum.reduce([l, o, c])

    tod = np.tile(np.arange(BARS_PER_DAY) * 5, n_days)  # minutes since 09:30
    day_dates = np.repeat(days.values, BARS_PER_DAY)
    ts = pd.to_datetime(day_dates) + pd.to_timedelta(9 * 60 + 30 + tod, unit="m")
    df = pd.DataFrame({
        "ts": ts, "date": pd.to_datetime(day_dates).date, "open": o.ravel(), "high": h.ravel(),
        "low": l.ravel(), "close": c.ravel(), "volume": np.round(vols.ravel()).astype(int),
        "gen_regime": np.repeat(np.array(states), BARS_PER_DAY), "tod": tod,
        "day_id": np.repeat(np.arange(n_days), BARS_PER_DAY),
    })
    return df[BAR_COLUMNS]


def load_bars(symbol: str, seed: int = 42, timeframe: str = "5m", model: str = "random_walk") -> pd.DataFrame:
    """OHLCV bars for a backtest: synthetic ('random_walk' / 'structured') or REAL CSV data ('real')."""
    if model == "real":
        from .real import load_real_bars

        return load_real_bars(symbol, timeframe)  # cached by file signature, seed is irrelevant
    return _load_synthetic(symbol, seed, timeframe, model)


@lru_cache(maxsize=16)
def _load_synthetic(symbol: str, seed: int, timeframe: str, model: str) -> pd.DataFrame:
    df = generate_5m_bars(symbol, seed, model)
    if timeframe == "5m":
        return df
    if timeframe == "15m":
        grp = df.groupby(["day_id", df["tod"] // 15], sort=True)
        out = grp.agg(ts=("ts", "first"), date=("date", "first"), open=("open", "first"), high=("high", "max"),
                      low=("low", "min"), close=("close", "last"), volume=("volume", "sum"),
                      gen_regime=("gen_regime", "first"), tod=("tod", "first")).reset_index()
        return out[BAR_COLUMNS]
    raise ValueError(f"Unsupported timeframe {timeframe!r}")
