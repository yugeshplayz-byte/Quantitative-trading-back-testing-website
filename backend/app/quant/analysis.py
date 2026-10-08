"""Descriptive analytics over a trade DataFrame (see backtesting.runner.trades_frame)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from ..data.events import EVENT_TYPES, event_calendar
from . import metrics as M

TIME_BUCKETS = [(0, 30, "9:30-10:00"), (30, 90, "10:00-11:00"), (90, 150, "11:00-12:00"),
                (150, 210, "12:00-1:00"), (210, 270, "1:00-2:00"), (270, 330, "2:00-3:00"),
                (330, 391, "3:00-4:00")]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
ATR_BUCKETS = [(0, 20, "0-20%"), (20, 40, "20-40%"), (40, 60, "40-60%"), (60, 80, "60-80%"), (80, 100.01, "80-100%")]


def _f(x):
    """JSON-safe float."""
    if x is None:
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def subset_metrics(df: pd.DataFrame, days: list, starting_balance: float) -> dict:
    """Compact metric block for any subset of trades (used by every comparison table)."""
    if len(df) == 0:
        return {"trades": 0, "net_pnl": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "expectancy": 0.0,
                "avg_winner": 0.0, "avg_loser": 0.0, "sharpe": 0.0, "max_drawdown": 0.0,
                "gross_profit": 0.0, "gross_loss": 0.0, "avg_r": 0.0}
    pnl = df["net_pnl"].to_numpy(dtype=float)
    daily = M.daily_frame(df, days, starting_balance)
    dd, _ = M.max_drawdown(np.concatenate([[starting_balance], daily["equity"].to_numpy()]))
    return {
        "trades": int(len(pnl)),
        "net_pnl": _f(pnl.sum()),
        "gross_profit": _f(M.gross_profit(pnl)),
        "gross_loss": _f(M.gross_loss(pnl)),
        "win_rate": _f(M.win_rate(pnl)),
        "profit_factor": _f(M.profit_factor(pnl)),
        "expectancy": _f(M.expectancy(pnl)),
        "avg_winner": _f(M.average_winner(pnl)),
        "avg_loser": _f(M.average_loser(pnl)),
        "sharpe": _f(M.sharpe_ratio(daily["return"].to_numpy())),
        "max_drawdown": _f(dd),
        "avg_r": _f(df["r_multiple"].mean()),
    }


def _group(df: pd.DataFrame, keys: pd.Series, labels: list[str], days: list, bal: float) -> list[dict]:
    out = []
    for lab in labels:
        sub = df[keys == lab]
        out.append({"label": lab, **subset_metrics(sub, days, bal)})
    return out


# ------------------------------------------------------------------ equity
def equity_curves(df: pd.DataFrame, days: list, bal: float) -> dict:
    daily = M.daily_frame(df, days, bal)
    out = {"dates": [str(d) for d in daily["date"]]}
    out["net_equity"] = daily["equity"].round(2).tolist()
    out["cumulative_pnl"] = (daily["equity"] - bal).round(2).tolist()
    gross = bal + daily["gross_pnl"].cumsum()
    out["gross_equity"] = gross.round(2).tolist()
    for side, key in (("Long", "long_equity"), ("Short", "short_equity")):
        d = M.daily_frame(df[df["direction"] == side], days, bal)
        out[key] = d["equity"].round(2).tolist()
    return out


def drawdown_series(df: pd.DataFrame, days: list, bal: float) -> dict:
    daily = M.daily_frame(df, days, bal)
    periods = M.drawdown_periods(list(daily["date"]), daily["equity"].to_numpy(), bal)
    for p in periods:
        p["start"], p["bottom"] = str(p["start"]), str(p["bottom"])
        p["recovery"] = str(p["recovery"]) if p["recovery"] is not None else None
    # underwater run lengths (days spent below a prior peak at each date)
    peak = np.maximum.accumulate(np.concatenate([[bal], daily["equity"].to_numpy()]))[1:]
    under = daily["equity"].to_numpy() < peak
    run, runs = 0, []
    for u in under:
        run = run + 1 if u else 0
        runs.append(run)
    return {
        "dates": [str(d) for d in daily["date"]],
        "drawdown": daily["drawdown"].round(2).tolist(),
        "drawdown_pct": (daily["drawdown_pct"] * 100).round(3).tolist(),
        "days_underwater": runs,
        "periods": periods[:10],
        "period_count": len(periods),
    }


# ------------------------------------------------------------------ calendar
def calendar_analytics(df: pd.DataFrame, days: list, bal: float) -> dict:
    daily = M.daily_frame(df, days, bal)
    daily["date_ts"] = pd.to_datetime(daily["date"])
    dly = [
        {"date": str(r.date), "net_pnl": _f(r.net_pnl), "trades": int(r.trades),
         "win_rate": _f(r.wins / r.trades) if r.trades else None}
        for r in daily.itertuples()
    ]
    wk = daily.groupby(daily["date_ts"].dt.to_period("W-FRI")).agg(
        net_pnl=("net_pnl", "sum"), trades=("trades", "sum"), wins=("wins", "sum"))
    weekly = [{"period": str(k.start_time.date()), "net_pnl": _f(v.net_pnl), "trades": int(v.trades),
               "win_rate": _f(v.wins / v.trades) if v.trades else None} for k, v in wk.iterrows()]
    mo = daily.groupby(daily["date_ts"].dt.to_period("M")).agg(
        net_pnl=("net_pnl", "sum"), trades=("trades", "sum"), wins=("wins", "sum"))
    equity_start = bal + daily["net_pnl"].cumsum().shift(1).fillna(0.0)
    first_eq = equity_start.groupby(daily["date_ts"].dt.to_period("M")).first()
    monthly, matrix = [], {}
    for k, v in mo.iterrows():
        ret = v.net_pnl / first_eq[k]
        monthly.append({"period": str(k), "net_pnl": _f(v.net_pnl), "trades": int(v.trades),
                        "win_rate": _f(v.wins / v.trades) if v.trades else None, "return_pct": _f(ret * 100)})
        matrix.setdefault(str(k.year), {})[k.month] = _f(ret * 100)
    years = sorted(matrix)
    mat = [{"year": y, "months": [matrix[y].get(m) for m in range(1, 13)],
            "total": _f(sum(v for v in matrix[y].values() if v is not None))} for y in years]
    return {"daily": dly, "weekly": weekly, "monthly": monthly, "monthly_matrix": mat}


# ------------------------------------------------------------------ time analysis
def _entry_minutes(df: pd.DataFrame) -> pd.Series:
    t = df["entry_dt"]
    return (t.dt.hour * 60 + t.dt.minute - (9 * 60 + 30)).astype(int)


def time_analytics(df: pd.DataFrame, days: list, bal: float) -> dict:
    if len(df) == 0:
        return {"time_of_day": [], "day_of_week": [], "heatmap": {"rows": [], "cols": [], "values": []}}
    mins = _entry_minutes(df)
    buckets = []
    for lo, hi, lab in TIME_BUCKETS:
        sub = df[(mins >= lo) & (mins < hi)]
        buckets.append({"label": lab, **subset_metrics(sub, days, bal)})
    dow = df["entry_dt"].dt.dayofweek
    by_dow = []
    for i, name in enumerate(WEEKDAYS):
        by_dow.append({"label": name, **subset_metrics(df[dow == i], days, bal)})
    half = (mins // 30).clip(0, 12)
    rows = [f"{9 + (30 * h + 30) // 60}:{(30 * h + 30) % 60:02d}" for h in range(13)]
    values = [[_f(df[(half == h) & (dow == d)]["net_pnl"].sum()) for d in range(5)] for h in range(13)]
    counts = [[int(((half == h) & (dow == d)).sum()) for d in range(5)] for h in range(13)]
    return {"time_of_day": buckets, "day_of_week": by_dow,
            "heatmap": {"rows": rows, "cols": WEEKDAYS, "values": values, "counts": counts}}


def long_short(df: pd.DataFrame, days: list, bal: float) -> dict:
    return {"rows": _group(df, df["direction"], ["Long", "Short"], days, bal)}


# ------------------------------------------------------------------ MFE / MAE
def mfe_mae(df: pd.DataFrame) -> dict:
    if len(df) == 0:
        return {"points": [], "stats": {}}
    win = df["net_pnl"] > 0
    pts = [
        {"id": r.id, "mae": _f(r.mae), "mfe": _f(r.mfe), "net_pnl": _f(r.net_pnl), "r": _f(r.r_multiple),
         "winner": bool(r.net_pnl > 0), "direction": r.direction, "regime": r.regime, "setup": r.setup}
        for r in df.itertuples()
    ]
    cap = (df.loc[win, "net_pnl"] / df.loc[win, "mfe"].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    st = {
        "avg_mfe": _f(df["mfe"].mean()), "avg_mae": _f(df["mae"].mean()),
        "winner_mae": _f(df.loc[win, "mae"].mean()) if win.any() else None,
        "loser_mae": _f(df.loc[~win, "mae"].mean()) if (~win).any() else None,
        "winner_mfe": _f(df.loc[win, "mfe"].mean()) if win.any() else None,
        "loser_mfe": _f(df.loc[~win, "mfe"].mean()) if (~win).any() else None,
        "median_mfe": _f(df["mfe"].median()), "median_mae": _f(df["mae"].median()),
        "mfe_capture": _f(cap.mean()) if win.any() else None,
        "mae_mfe_corr": _f(np.corrcoef(df["mae"], df["mfe"])[0, 1]) if len(df) > 2 else None,
    }
    return {"points": pts, "stats": st}


# ------------------------------------------------------------------ distributions
def _hist(x: np.ndarray, bins: int = 30) -> dict:
    if len(x) == 0:
        return {"edges": [], "counts": [], "centers": []}
    counts, edges = np.histogram(x, bins=bins)
    return {"centers": ((edges[:-1] + edges[1:]) / 2).round(4).tolist(), "counts": counts.tolist(),
            "edges": edges.round(4).tolist()}


def describe(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return {k: None for k in ("mean", "median", "std", "skew", "kurtosis", "p5", "p95", "count")} | {"count": int(len(x))}
    return {"count": int(len(x)), "mean": _f(x.mean()), "median": _f(np.median(x)), "std": _f(x.std(ddof=1)),
            "skew": _f(stats.skew(x)), "kurtosis": _f(stats.kurtosis(x)),  # excess kurtosis
            "p5": _f(np.percentile(x, 5)), "p95": _f(np.percentile(x, 95))}


def distributions(df: pd.DataFrame, days: list, bal: float) -> dict:
    pnl = df["net_pnl"].to_numpy(dtype=float)
    daily = M.daily_frame(df, days, bal)
    series = {
        "trade_pnl": pnl, "winners": pnl[pnl > 0], "losers": pnl[pnl < 0],
        "r_multiples": df["r_multiple"].to_numpy(dtype=float),
        "holding_time": df["duration_minutes"].to_numpy(dtype=float),
        "daily_returns": (daily["return"].to_numpy(dtype=float) * 100),
    }
    return {k: {"hist": _hist(v), "stats": describe(v)} for k, v in series.items()}


# ------------------------------------------------------------------ streaks
def streaks(df: pd.DataFrame) -> dict:
    pnl = df["net_pnl"].to_numpy(dtype=float)
    def dist(runs: list[int]) -> list[dict]:
        if not runs:
            return []
        mx = max(runs)
        return [{"length": n, "count": runs.count(n)} for n in range(1, mx + 1)]
    wr, lr = M.streak_lengths(pnl, True), M.streak_lengths(pnl, False)
    return {
        "win_distribution": dist(wr), "loss_distribution": dist(lr),
        "longest_win": max(wr, default=0), "longest_loss": max(lr, default=0),
        "avg_win_streak": _f(np.mean(wr)) if wr else 0.0, "avg_loss_streak": _f(np.mean(lr)) if lr else 0.0,
        "current_streak": _current_streak(pnl),
    }


def _current_streak(pnl: np.ndarray) -> dict:
    if len(pnl) == 0:
        return {"type": "none", "length": 0}
    kind = pnl[-1] > 0
    n = 0
    for x in pnl[::-1]:
        if (x > 0) == kind and x != 0:
            n += 1
        else:
            break
    return {"type": "win" if kind else "loss", "length": n}


# ------------------------------------------------------------------ regimes / volatility / events
def regimes(df: pd.DataFrame, days: list, bal: float) -> dict:
    labels = ["Trending", "Ranging", "Bull", "Bear", "Neutral", "High Volatility", "Low Volatility"]
    return {"rows": _group(df, df["regime"], labels, days, bal)}


def volatility(df: pd.DataFrame, days: list, bal: float) -> dict:
    rows = []
    for lo, hi, lab in ATR_BUCKETS:
        sub = df[(df["atr_percentile"] >= lo) & (df["atr_percentile"] < hi)]
        rows.append({"label": lab, **subset_metrics(sub, days, bal)})
    return {"rows": rows}


NO_CALENDAR_NOTE = ("Event analysis is unavailable for real data until you supply an official event calendar: put "
                    "events.csv (columns date,event[,time]) in the real-data folder. The built-in calendar is a SAMPLE "
                    "and would give meaningless results on real prices.")


def events(df: pd.DataFrame, days: list, bal: float, cal: pd.DataFrame | None = None, note: str | None = None,
           use_sample: bool = True) -> dict:
    """Before = prior trading day; During = event day, first 90 min after max(release, RTH open);
    After = rest of the event day."""
    if cal is None:
        if not use_sample:
            return {"rows": [], "baseline": None, "note": NO_CALENDAR_NOTE}
        cal = event_calendar()
        note = note or SAMPLE_NOTE
    note = note or "Event dates supplied by you in events.csv."
    day_set = set(days)
    cal = cal[cal["date"].isin(day_set)]
    out = []
    if len(df) == 0:
        return {"rows": [], "note": note}
    tdf = df.copy()
    tdf["dt"] = tdf["entry_dt"]
    tdf["d"] = tdf["date"]
    ordered_days = sorted(day_set)
    prev = {d: ordered_days[i - 1] for i, d in enumerate(ordered_days) if i > 0}
    names = list(EVENT_TYPES) + [e for e in sorted(cal["event"].unique()) if e not in EVENT_TYPES]
    for ev in names:
        e = cal[cal["event"] == ev]
        phases = {"Before": [], "During": [], "After": []}
        for r in e.itertuples():
            hh, mm = (int(x) for x in r.time.split(":"))
            rel = max(hh * 60 + mm, 9 * 60 + 30)
            sameday = tdf[tdf["d"] == r.date]
            mins = sameday["dt"].dt.hour * 60 + sameday["dt"].dt.minute
            phases["During"].append(sameday[(mins >= rel) & (mins < rel + 90)])
            phases["After"].append(sameday[mins >= rel + 90])
            pd_ = prev.get(r.date)
            if pd_ is not None:
                phases["Before"].append(tdf[tdf["d"] == pd_])
        row = {"event": ev, "occurrences": int(len(e)), "phases": {}}
        for ph, frames in phases.items():
            sub = pd.concat(frames) if frames else df.iloc[0:0]
            row["phases"][ph] = subset_metrics(sub, days, bal)
        out.append(row)
    non_event_days = day_set - set(cal["date"])
    base = df[df["date"].isin(non_event_days)]
    return {"rows": out, "baseline": subset_metrics(base, days, bal), "note": note}


SAMPLE_NOTE = ("Event dates come from an approximate SAMPLE calendar (data/events.py), "
               "not an official release schedule.")
