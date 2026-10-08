"""Real market data from CSV files, with data-quality validation.

Put one or more CSV files per symbol in `REAL_DATA_DIR` (default backend/data/real), named so the
file stem starts with the symbol: `MNQ.csv`, `MNQ_1m.csv`, `MNQ_2023.csv` ... Required columns
(case-insensitive): a timestamp column (`timestamp`, `datetime`, `time` or `date_time`; or separate
`date` + `time` columns), `open`, `high`, `low`, `close`; optional `volume`.

Conventions (all explicit, never silently guessed):
* Timestamps without a UTC offset are interpreted in `REAL_DATA_TZ` (default America/New_York) and
  converted to US/Eastern wall-clock time. Timestamps WITH an offset are converted to Eastern.
* A bar's timestamp is its START time unless `REAL_DATA_BAR_LABEL=end` (then bars are shifted back).
* Only regular trading hours (09:30-16:00 ET) are kept; 1-minute and 5-minute sources are resampled
  to the requested timeframe. A 15-minute source can only serve a 15-minute backtest.
* Duplicate timestamps are dropped, rows with impossible OHLC are dropped, and EVERYTHING dropped or
  suspicious is reported in the quality report - nothing is repaired silently.

Futures caveat: continuous contracts have roll gaps between contract months. Use back-adjusted data
or expect spurious overnight jumps (the engine never holds overnight, but ATR/VWAP warm-up is affected).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import get_settings

BAR_COLUMNS = ["ts", "date", "open", "high", "low", "close", "volume", "gen_regime", "tod", "day_id"]
SESSION_OPEN_MIN = 9 * 60 + 30
SESSION_CLOSE_MIN = 16 * 60
_TS_NAMES = ("timestamp", "datetime", "date_time", "time")


class RealDataError(ValueError):
    """Raised for unusable files; the message tells the user exactly what to fix."""


@dataclass
class QualityReport:
    symbol: str
    files: list[str]
    source_bar_minutes: int
    rows_read: int
    bars: int
    days: int
    start: str
    end: str
    issues: list[dict] = field(default_factory=list)  # {severity, message}
    median_bars_per_day: float = 0.0

    def add(self, severity: str, message: str) -> None:
        self.issues.append({"severity": severity, "message": message})

    def as_dict(self) -> dict:
        return {"symbol": self.symbol, "files": self.files, "source_bar_minutes": self.source_bar_minutes,
                "rows_read": self.rows_read, "bars": self.bars, "days": self.days, "start": self.start,
                "end": self.end, "median_bars_per_day": self.median_bars_per_day, "issues": self.issues,
                "ok": not any(i["severity"] == "error" for i in self.issues)}


def data_dir() -> Path:
    return Path(get_settings().real_data_dir).expanduser().resolve()


def dataset_files(symbol: str) -> list[Path]:
    d = data_dir()
    if not d.exists():
        return []
    sym = symbol.upper()
    return sorted(p for p in d.glob("*.csv") if p.stem.upper() == sym or p.stem.upper().startswith(sym + "_"))


def signature(symbol: str) -> tuple:
    """Changes whenever the underlying files change - used to invalidate caches."""
    return tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in dataset_files(symbol))


def _timestamps(df: pd.DataFrame, report_issue) -> pd.Series:
    cols = {c.lower().strip(): c for c in df.columns}
    s = get_settings()
    if "date" in cols and "time" in cols and not any(n in cols for n in ("timestamp", "datetime", "date_time")):
        raw = df[cols["date"]].astype(str).str.strip() + " " + df[cols["time"]].astype(str).str.strip()
    else:
        name = next((cols[n] for n in _TS_NAMES if n in cols), None)
        if name is None:
            raise RealDataError("No timestamp column found. Name one of: timestamp, datetime, date_time, time "
                                "(or provide separate date and time columns).")
        raw = df[name]
    try:
        ts = pd.to_datetime(raw, errors="raise", utc=False)
    except Exception as exc:  # noqa: BLE001
        raise RealDataError(f"Could not parse timestamps ({exc}). Use an ISO format like 2024-03-18 09:30:00.") from exc
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("America/New_York").dt.tz_localize(None)
        report_issue("info", "Timestamps carried a UTC offset and were converted to US/Eastern.")
    elif s.real_data_tz != "America/New_York":
        ts = ts.dt.tz_localize(s.real_data_tz, ambiguous="NaT", nonexistent="NaT")
        ts = ts.dt.tz_convert("America/New_York").dt.tz_localize(None)
        report_issue("info", f"Naive timestamps were interpreted as {s.real_data_tz} and converted to US/Eastern.")
    return ts


def _load_raw(symbol: str, report: QualityReport) -> pd.DataFrame:
    files = dataset_files(symbol)
    if not files:
        raise RealDataError(f"No real data found for {symbol}. Put a CSV named {symbol}.csv (or {symbol}_1m.csv) in "
                            f"{data_dir()} - see docs/REAL_DATA.md.")
    frames, has_volume = [], True
    for p in files:
        raw = pd.read_csv(p)
        report.files.append(p.name)
        report.rows_read += len(raw)
        cols = {c.lower().strip(): c for c in raw.columns}
        missing = [c for c in ("open", "high", "low", "close") if c not in cols]
        if missing:
            raise RealDataError(f"{p.name}: missing required column(s) {missing}. Found: {list(raw.columns)}")
        has_volume = has_volume and "volume" in cols
        f = pd.DataFrame({
            "ts": _timestamps(raw, report.add), "open": pd.to_numeric(raw[cols["open"]], errors="coerce"),
            "high": pd.to_numeric(raw[cols["high"]], errors="coerce"), "low": pd.to_numeric(raw[cols["low"]], errors="coerce"),
            "close": pd.to_numeric(raw[cols["close"]], errors="coerce"),
            "volume": pd.to_numeric(raw[cols["volume"]], errors="coerce") if "volume" in cols else 1.0})
        frames.append(f)
    df = pd.concat(frames, ignore_index=True)
    if not has_volume:
        report.add("warning", "No volume column: VWAP falls back to an equal-weighted average price.")
    return df


def _clean(df: pd.DataFrame, report: QualityReport) -> pd.DataFrame:
    n0 = len(df)
    df = df.dropna(subset=["ts", "open", "high", "low", "close"])
    if len(df) < n0:
        report.add("warning", f"Dropped {n0 - len(df)} rows with unparsable timestamps or prices.")
    if not df["ts"].is_monotonic_increasing:
        report.add("warning", "Timestamps were not in ascending order; rows were sorted.")
        df = df.sort_values("ts")
    dup = int(df["ts"].duplicated().sum())
    if dup:
        report.add("warning", f"Dropped {dup} duplicate timestamps (kept the first).")
        df = df[~df["ts"].duplicated(keep="first")]
    bad = (df["high"] < df[["open", "close"]].max(axis=1) - 1e-9) | (df["low"] > df[["open", "close"]].min(axis=1) + 1e-9) \
        | (df["high"] < df["low"]) | (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    if bad.any():
        report.add("warning", f"Dropped {int(bad.sum())} bars with impossible OHLC values (high below open/close, low above, or non-positive).")
        df = df[~bad]
    df = df.copy()
    df["volume"] = df["volume"].fillna(0.0)
    return df.reset_index(drop=True)


def _source_minutes(ts: pd.Series) -> int:
    d = ts.diff().dropna()
    d = d[(d > pd.Timedelta(0)) & (d <= pd.Timedelta(minutes=60))]
    if d.empty:
        raise RealDataError("Cannot infer the bar size from the timestamps (need at least two bars on one day).")
    m = int(round(d.median().total_seconds() / 60))
    if m not in (1, 5, 15):
        raise RealDataError(f"Source bars look like {m}-minute bars; supported source sizes are 1, 5 and 15 minutes.")
    return m


def _load_uncached(symbol: str, timeframe: str) -> tuple[pd.DataFrame, QualityReport]:
    report = QualityReport(symbol=symbol, files=[], source_bar_minutes=0, rows_read=0, bars=0, days=0, start="", end="")
    df = _clean(_load_raw(symbol, report), report)
    if df.empty:
        raise RealDataError(f"{symbol}: no usable rows after cleaning.")
    src = _source_minutes(df["ts"])
    report.source_bar_minutes = src
    want = 5 if timeframe == "5m" else 15
    if src > want:
        raise RealDataError(f"{symbol} data is {src}-minute bars but a {timeframe} backtest was requested; "
                            f"provide finer data or choose a {src}-minute-or-coarser timeframe.")
    if get_settings().real_data_bar_label == "end":
        df["ts"] = df["ts"] - pd.Timedelta(minutes=src)
        report.add("info", "Bar timestamps treated as bar END times and shifted back to bar start.")
    minutes = df["ts"].dt.hour * 60 + df["ts"].dt.minute
    rth = (minutes >= SESSION_OPEN_MIN) & (minutes < SESSION_CLOSE_MIN) & (df["ts"].dt.dayofweek < 5)
    dropped = int((~rth).sum())
    if dropped:
        report.add("info", f"Kept regular trading hours only (09:30-16:00 ET, Mon-Fri); ignored {dropped} bars outside it.")
    df = df[rth].copy()
    if df.empty:
        raise RealDataError(f"{symbol}: no bars fall inside regular trading hours 09:30-16:00 US/Eastern. "
                            "Check the timezone (REAL_DATA_TZ) and whether timestamps are bar start or end (REAL_DATA_BAR_LABEL).")
    if want != src:
        agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        df = df.set_index("ts").resample(f"{want}min").agg(agg)
        df = df.dropna(subset=["open"]).reset_index()
        report.add("info", f"Resampled {src}-minute bars to {want}-minute bars.")
    minute_of_day = df["ts"].dt.hour * 60 + df["ts"].dt.minute
    df["tod"] = (minute_of_day - SESSION_OPEN_MIN).astype(int)
    df["date"] = df["ts"].dt.date
    df["day_id"] = pd.factorize(df["date"])[0]
    df["gen_regime"] = "real"
    # zero volume breaks VWAP; keep the bar but make its weight tiny and say so
    zero = int((df["volume"] <= 0).sum())
    if zero:
        report.add("warning", f"{zero} bars have zero volume; they get a minimal weight in VWAP.")
        df.loc[df["volume"] <= 0, "volume"] = 1.0
    df["volume"] = df["volume"].round().astype(int)
    df = df[BAR_COLUMNS].reset_index(drop=True)

    expected = (SESSION_CLOSE_MIN - SESSION_OPEN_MIN) // want
    per_day = df.groupby("day_id").size()
    report.median_bars_per_day = float(per_day.median())
    short = per_day[per_day < 0.8 * expected]
    if len(short):
        days = df.groupby("day_id")["date"].first()[short.index]
        report.add("warning", f"{len(short)} days have under 80% of the expected {expected} bars (holiday early closes or "
                              f"missing data), e.g. {', '.join(str(d) for d in list(days)[:5])}. Missing bars distort ATR/VWAP.")
    gaps = df.groupby("day_id").apply(lambda g: g["tod"].diff().max(), include_groups=False)
    big = gaps[gaps > 4 * want]
    if len(big):
        report.add("warning", f"{len(big)} days contain intraday gaps of more than {4 * want} minutes (missing bars).")
    day_close = df.groupby("day_id")["close"].last()
    day_open = df.groupby("day_id")["open"].first()
    jump = (day_open.iloc[1:].to_numpy() / day_close.iloc[:-1].to_numpy() - 1.0)
    big_jumps = int((np.abs(jump) > 0.04).sum())
    if big_jumps:
        report.add("warning", f"{big_jumps} overnight jumps exceed 4% - possible contract rolls on non-adjusted data. "
                              "Use back-adjusted continuous contracts for realistic ATR/VWAP.")
    span_days = (pd.Timestamp(df["date"].iloc[-1]) - pd.Timestamp(df["date"].iloc[0])).days
    if span_days < 365:
        report.add("warning", f"Only {span_days} calendar days of data: too short to judge a strategy across market regimes.")
    report.bars, report.days = len(df), int(df["day_id"].nunique())
    report.start, report.end = str(df["date"].iloc[0]), str(df["date"].iloc[-1])
    if report.days < 30:
        report.add("error", "Fewer than 30 trading days of data - not enough to run meaningful backtests.")
    return df, report


@lru_cache(maxsize=12)
def _load_cached(symbol: str, timeframe: str, sig: tuple) -> tuple[pd.DataFrame, QualityReport]:
    return _load_uncached(symbol, timeframe)


def load_real_bars(symbol: str, timeframe: str = "5m") -> pd.DataFrame:
    return _load_cached(symbol, timeframe, signature(symbol))[0]


def quality_report(symbol: str, timeframe: str = "5m") -> dict:
    try:
        return _load_cached(symbol, timeframe, signature(symbol))[1].as_dict()
    except RealDataError as exc:
        return {"symbol": symbol, "files": [p.name for p in dataset_files(symbol)], "ok": False,
                "issues": [{"severity": "error", "message": str(exc)}], "bars": 0, "days": 0, "start": None, "end": None}


def list_datasets() -> list[dict]:
    from ..backtesting.instruments import INSTRUMENTS

    out = []
    for sym in INSTRUMENTS:
        if dataset_files(sym):
            out.append(quality_report(sym, "5m"))
    return out


def load_events() -> pd.DataFrame | None:
    """Optional user-supplied event calendar: events.csv with columns date,event[,time]."""
    p = data_dir() / "events.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    cols = {c.lower().strip(): c for c in df.columns}
    if "date" not in cols or "event" not in cols:
        raise RealDataError("events.csv needs columns: date,event (and optionally time as HH:MM ET).")
    out = pd.DataFrame({"date": pd.to_datetime(df[cols["date"]]).dt.date, "event": df[cols["event"]].astype(str),
                        "time": df[cols["time"]].astype(str) if "time" in cols else "08:30"})
    return out.sort_values(["date", "event"]).reset_index(drop=True)
