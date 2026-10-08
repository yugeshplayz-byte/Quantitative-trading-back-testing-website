"""Deterministic synthetic intraday futures data.

This stands in for real market data so the whole platform works out of the box.
The generator is fully seeded: the same (symbol, seed) always yields identical bars.

Model: 5-minute RTH bars (09:30-16:00 ET, 78 bars/day) built from a daily Markov chain of
market regimes. Each regime sets volatility, intraday autocorrelation (momentum vs. mean-reversion)
and drift, so trend strategies have a genuine edge on trending days and mean-reversion
strategies on ranging days - which makes regime analysis meaningful. MNQ/NQ share one
underlying and MES/ES another; the two underlyings are ~0.9 correlated.

To use real data later, implement `load_bars(symbol, ...)` returning the same columns
(see `BAR_COLUMNS`) - nothing else in the platform needs to change.
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
BAR_COLUMNS = ["ts", "date", "open", "high", "low", "close", "volume", "regime", "tod", "day_id"]

REGIMES = ["Trending", "Ranging", "Bull", "Bear", "Neutral", "High Volatility", "Low Volatility"]
# (vol multiplier, AR(1) coefficient per 5m bar, drift in units of bar sigma, weight)
_REGIME_PARAMS = {
    "Trending": (1.00, 0.30, 0.000, 0.15),
    "Ranging": (0.80, -0.15, 0.000, 0.20),
    "Bull": (0.90, 0.06, 0.045, 0.14),
    "Bear": (1.20, 0.06, -0.055, 0.10),
    "Neutral": (1.00, 0.00, 0.000, 0.18),
    "High Volatility": (1.90, 0.10, 0.000, 0.11),
    "Low Volatility": (0.55, -0.05, 0.000, 0.10),
}
_REGIME_KAPPA = {"Ranging": 0.06, "Low Volatility": 0.05}
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


@lru_cache(maxsize=4)
def _regime_path(seed: int, n_days: int) -> tuple[str, ...]:
    rng = np.random.default_rng(seed + 101)
    names = list(_REGIME_PARAMS)
    weights = np.array([_REGIME_PARAMS[n][3] for n in names])
    weights = weights / weights.sum()
    path, cur = [], int(rng.choice(len(names), p=weights))
    for _ in range(n_days):
        if rng.random() > 0.58:  # regimes are sticky: ~58% chance to persist a day
            cur = int(rng.choice(len(names), p=weights))
        path.append(names[cur])
    return tuple(path)


@lru_cache(maxsize=4)
def _market_factor(seed: int, n_days: int) -> np.ndarray:
    return np.random.default_rng(seed + 202).standard_normal((n_days, BARS_PER_DAY))


@lru_cache(maxsize=16)
def generate_5m_bars(symbol: str, seed: int = 42) -> pd.DataFrame:
    inst = get_instrument(symbol)
    days = trading_days()
    n_days = len(days)
    regimes = _regime_path(seed, n_days)
    mkt = _market_factor(seed, n_days)
    idio_seed = 303 if inst.group == "nasdaq" else 404
    idio = np.random.default_rng(seed + idio_seed).standard_normal((n_days, BARS_PER_DAY))
    rho = 1.0 if inst.group == "nasdaq" else 0.9
    eps = rho * mkt + np.sqrt(1 - rho**2) * idio
    gap_rng = np.random.default_rng(seed + 505)
    wick_rng = np.random.default_rng(seed + 606)
    vol_rng = np.random.default_rng(seed + 707)

    bar_sigma = inst.daily_vol / np.sqrt(BARS_PER_DAY)
    profile = _u_shape()
    tick = inst.tick_size

    opens = np.empty((n_days, BARS_PER_DAY))
    highs = np.empty_like(opens)
    lows = np.empty_like(opens)
    closes = np.empty_like(opens)
    vols = np.empty_like(opens)

    # price level follows a log random walk (shared by symbols of the same group via the same factor)
    last_close = inst.start_price
    for d in range(n_days):
        vol_mult, phi, drift, _ = _REGIME_PARAMS[regimes[d]]
        sigma = bar_sigma * vol_mult * profile
        # trending days pick a direction (shared factor sign keeps both symbols aligned)
        dir_sign = 1.0
        if regimes[d] == "Trending":
            dir_sign = 1.0 if mkt[d].sum() >= 0 else -1.0
            drift_d = 0.09 * dir_sign
        else:
            drift_d = drift
        x = sigma * eps[d] + drift_d * bar_sigma * vol_mult
        gap = gap_rng.normal(0, inst.daily_vol * 0.35)
        o_first = last_close * np.exp(gap)
        kappa = _REGIME_KAPPA.get(regimes[d], 0.0)
        if kappa == 0.0:
            r = lfilter([1.0], [1.0, -phi], x)
            logp = np.log(o_first) + np.concatenate([[0.0], np.cumsum(r)[:-1]])
        else:
            # Ornstein-Uhlenbeck pull toward the day's opening level: genuine intraday mean reversion
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
        h = np.maximum(o, c) * np.exp(wick[0])
        l = np.minimum(o, c) * np.exp(-wick[1])
        opens[d], closes[d], highs[d], lows[d] = o, c, h, l
        base_vol = 900.0 * profile * vol_mult
        vols[d] = base_vol * np.exp(vol_rng.normal(0, 0.25, BARS_PER_DAY)) * (1 + 40 * np.abs(r) / bar_sigma / 10)
        last_close = c[-1]

    def q(a: np.ndarray) -> np.ndarray:
        return np.round(a / tick) * tick

    o, h, l, c = q(opens), q(highs), q(lows), q(closes)
    h = np.maximum.reduce([h, o, c])
    l = np.minimum.reduce([l, o, c])

    tod = np.tile(np.arange(BARS_PER_DAY) * 5, n_days)  # minutes since 09:30
    day_dates = np.repeat(days.values, BARS_PER_DAY)
    ts = pd.to_datetime(day_dates) + pd.to_timedelta(9 * 60 + 30 + tod, unit="m")
    df = pd.DataFrame(
        {
            "ts": ts,
            "date": pd.to_datetime(day_dates).date,
            "open": o.ravel(),
            "high": h.ravel(),
            "low": l.ravel(),
            "close": c.ravel(),
            "volume": np.round(vols.ravel()).astype(int),
            "regime": np.repeat(np.array(regimes), BARS_PER_DAY),
            "tod": tod,
            "day_id": np.repeat(np.arange(n_days), BARS_PER_DAY),
        }
    )
    return df[BAR_COLUMNS]


@lru_cache(maxsize=16)
def load_bars(symbol: str, seed: int = 42, timeframe: str = "5m") -> pd.DataFrame:
    """Return OHLCV bars for the whole synthetic epoch. Replace this to plug in real data."""
    df = generate_5m_bars(symbol, seed)
    if timeframe == "5m":
        return df
    if timeframe == "15m":
        grp = df.groupby(["day_id", df["tod"] // 15], sort=True)
        out = grp.agg(
            ts=("ts", "first"),
            date=("date", "first"),
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
            regime=("regime", "first"),
            tod=("tod", "first"),
        ).reset_index()
        return out[["ts", "date", "open", "high", "low", "close", "volume", "regime", "tod", "day_id"]]
    raise ValueError(f"Unsupported timeframe {timeframe!r}")


def bars_for_range(symbol: str, start, end, seed: int = 42, timeframe: str = "5m") -> pd.DataFrame:
    df = load_bars(symbol, seed, timeframe)
    mask = (df["date"] >= start) & (df["date"] <= end)
    return df[mask].reset_index(drop=True)
