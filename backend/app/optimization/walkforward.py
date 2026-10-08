"""Rolling walk-forward analysis.

For each window: optimise parameters on the TRAIN period (grid search on `metric`), then run the
chosen parameters on the following TEST period (out-of-sample). OOS segments are stitched into one
curve using only days not already covered by an earlier window.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..backtesting.market import get_market_data
from ..backtesting.runner import run_config, trades_frame
from ..models.config import BacktestConfig
from ..quant.fast import day_index, fast_metrics
from .grid import (HIGHER_IS_BETTER, apply_param, default_axis, metric_value, metrics_from_output, prefetch_custom,
                   run_metrics)

REPORT_KEYS = ["net_profit", "sharpe", "sortino", "profit_factor", "win_rate", "expectancy", "max_drawdown", "trades"]


def _add_months(d: date, m: int) -> date:
    y, mo = divmod(d.month - 1 + m, 12)
    return date(d.year + y, mo + 1, min(d.day, 28))


def _pick(m: dict) -> dict:
    return {k: (float(m[k]) if m[k] is not None and math.isfinite(m[k]) else 0.0) for k in REPORT_KEYS}


def walk_forward(cfg: BacktestConfig, train_months: int, test_months: int, step_months: int, metric: str,
                 param_x: str | None, param_y: str | None,
                 xs: list[float] | None = None, ys: list[float] | None = None) -> dict:
    if metric not in HIGHER_IS_BETTER or metric == "prop_pass_probability":
        metric = "sharpe"
    md = get_market_data(cfg.symbol, cfg.seed, cfg.timeframe)
    # default axes: the strategy's first two parameters, 3 values each
    from .grid import parameter_catalog

    names = [p["key"] for p in parameter_catalog(cfg) if p["group"] == "strategy"]
    px = param_x or (names[0] if names else "stop.value")
    py = param_y or (names[1] if len(names) > 1 else "target.value")
    xs = xs or default_axis(cfg, px, 3)
    ys = ys or default_axis(cfg, py, 3)
    combos = [(x, y) for x in xs for y in ys]
    prefetch_custom(cfg, [{px: x, py: y} for x, y in combos if "." not in px and "." not in py])

    windows, stitched_net, stitched_dates = [], [], []
    covered_to: date | None = None
    start = cfg.start_date
    k = 0
    while True:
        tr_s, tr_e = start, _add_months(start, train_months) - timedelta(days=1)
        te_s = tr_e + timedelta(days=1)
        te_e = _add_months(te_s, test_months) - timedelta(days=1)
        if te_e > cfg.end_date:
            break
        tlo, thi = md.index_range(tr_s, tr_e)
        olo, ohi = md.index_range(te_s, te_e)
        best, best_v, best_m = None, -math.inf, None
        for x, y in combos:
            c = apply_param(apply_param(cfg, px, x), py, y)
            m = run_metrics(c, tlo, thi)
            v = metric_value(m, metric)
            if not math.isfinite(v):
                continue
            score = v if HIGHER_IS_BETTER[metric] else -v
            if score > best_v:
                best, best_v, best_m = (x, y), score, m
        if best is None:
            start = _add_months(start, step_months)
            continue
        c_best = apply_param(apply_param(cfg, px, best[0]), py, best[1])
        out = run_config(c_best, olo, ohi)
        oos_m = metrics_from_output(out, c_best)
        is_pick, oos_pick = _pick(best_m), _pick(oos_m)
        isv, oosv = metric_value(best_m, metric), metric_value(oos_m, metric)
        deg = None
        if math.isfinite(isv) and isv != 0 and math.isfinite(oosv):
            deg = (isv - oosv) / abs(isv) if HIGHER_IS_BETTER[metric] else (oosv - isv) / abs(isv)
        windows.append({
            "index": k + 1, "train_start": str(tr_s), "train_end": str(tr_e), "test_start": str(te_s),
            "test_end": str(te_e), "params": {px: best[0], py: best[1]}, "is_metrics": is_pick,
            "oos_metrics": oos_pick, "degradation": deg, "train_days": int(thi - tlo),
        })
        # stitch only days after previous coverage
        for t in out.trades:
            d = t["date"]
            if covered_to is None or d > covered_to:
                stitched_net.append(t["net_pnl"])
                stitched_dates.append(d)
        covered_to = te_e
        k += 1
        start = _add_months(start, step_months)
        if k >= 40:
            break

    agg = _aggregate(windows, stitched_net, stitched_dates, cfg, md, metric)
    return {"param_x": px, "param_y": py, "metric": metric, "windows": windows, **agg}


def _aggregate(windows: list[dict], net: list[float], dates: list, cfg: BacktestConfig, md, metric: str) -> dict:
    if not windows:
        return {"aggregate": None, "oos_curve": [], "consistency": 0.0}
    is_avg = {k: float(np.mean([w["is_metrics"][k] for w in windows])) for k in REPORT_KEYS}
    oos_avg = {k: float(np.mean([w["oos_metrics"][k] for w in windows])) for k in REPORT_KEYS}
    # stitched OOS performance over all covered days
    first, last = pd.Timestamp(windows[0]["test_start"]).date(), pd.Timestamp(windows[-1]["test_end"]).date()
    days = list(pd.bdate_range(first, last).date)
    idx = day_index(dates, days) if dates else np.array([], dtype=int)
    st = fast_metrics(np.array(net), idx, len(days), cfg.starting_balance)
    daily = np.bincount(idx, weights=np.array(net), minlength=len(days)) if dates else np.zeros(len(days))
    curve = [{"date": str(d), "equity": float(cfg.starting_balance + c)} for d, c in zip(days, np.cumsum(daily))]
    # fair comparison across unequal window lengths: net profit per trading day
    is_days = float(np.mean([w["train_days"] for w in windows])) / (78 if cfg.timeframe == "5m" else 26)
    oos_days = len(days) / max(len(windows), 1)
    is_per_day = is_avg["net_profit"] / max(is_days, 1)
    oos_per_day = oos_avg["net_profit"] / max(oos_days, 1)
    deg = {}
    for key in ("sharpe", "sortino", "profit_factor", "win_rate", "expectancy"):
        iv, ov = is_avg[key], oos_avg[key]
        deg[key] = (ov - iv) / abs(iv) if iv else None
    deg["net_profit_per_day"] = (oos_per_day - is_per_day) / abs(is_per_day) if is_per_day else None
    deg["max_drawdown"] = (oos_avg["max_drawdown"] - is_avg["max_drawdown"]) / abs(is_avg["max_drawdown"]) if is_avg["max_drawdown"] else None
    consistency = float(np.mean([w["oos_metrics"]["net_profit"] > 0 for w in windows]))
    return {
        "aggregate": {"is": {**is_avg, "net_profit_per_day": is_per_day},
                      "oos": {**oos_avg, "net_profit_per_day": oos_per_day},
                      "degradation": deg, "stitched_oos": {k: float(v) for k, v in st.items()}},
        "oos_curve": curve, "consistency": consistency,
        "profitable_windows": int(sum(w["oos_metrics"]["net_profit"] > 0 for w in windows)),
    }
