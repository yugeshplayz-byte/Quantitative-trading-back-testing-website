"""Strategy comparison, weighted combinations and correlation matrices."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..backtesting.market import get_market_data
from ..models.prop import PropFirmRules
from ..quant import metrics as M
from .prop import pass_probability_quick
from .store import Bundle, load_bundle


def _daily_pnl(b: Bundle) -> pd.Series:
    d = b.daily()
    return pd.Series(d["net_pnl"].to_numpy(), index=pd.to_datetime(d["date"]), name=b.id)


def _align(series: list[pd.Series]) -> pd.DataFrame:
    return pd.concat(series, axis=1).sort_index().fillna(0.0)


def compare(session: Session, ids: list[str]) -> dict:
    bundles = [load_bundle(session, i) for i in ids]
    pnl = _align([_daily_pnl(b) for b in bundles])
    rows, curves = [], {"dates": [d.strftime("%Y-%m-%d") for d in pnl.index]}
    for b in bundles:
        m = b.metrics
        rules = PropFirmRules(starting_balance=b.cfg.starting_balance)
        rows.append({
            "id": b.id, "name": b.name, "strategy": b.cfg.strategy, "symbol": b.cfg.symbol,
            "net_profit": m["net_profit"], "sharpe": m["sharpe"], "sortino": m["sortino"],
            "profit_factor": m["profit_factor"], "max_drawdown": m["max_drawdown"],
            "max_drawdown_pct": m["max_drawdown_pct"], "win_rate": m["win_rate"], "expectancy": m["expectancy"],
            "trades": m["total_trades"], "calmar": m["calmar"],
            "prop_pass_probability": pass_probability_quick(b, rules)})
        curves[b.id] = (b.cfg.starting_balance + pnl[b.id].cumsum()).round(2).tolist()
    return {"rows": rows, "curves": curves, "names": {b.id: b.name for b in bundles}}


def combine(session: Session, weights: dict[str, float]) -> dict:
    ids = list(weights)
    bundles = {i: load_bundle(session, i) for i in ids}
    total_w = sum(weights.values()) or 1.0
    w = {i: weights[i] / total_w for i in ids}
    pnl = _align([_daily_pnl(bundles[i]) for i in ids])
    bal = float(np.mean([bundles[i].cfg.starting_balance for i in ids]))
    combined = sum(pnl[i] * w[i] for i in ids)
    eq = bal + combined.cumsum()
    rets = combined / (eq - combined)
    dd, dd_pct = M.max_drawdown(np.concatenate([[bal], eq.to_numpy()]))
    comp = {
        "net_profit": float(combined.sum()), "return_pct": float(combined.sum() / bal),
        "sharpe": M.sharpe_ratio(rets.to_numpy()), "sortino": M.sortino_ratio(rets.to_numpy()),
        "max_drawdown": dd, "max_drawdown_pct": dd_pct}
    indiv = {}
    for i in ids:
        s = pnl[i] * w[i]
        e = bal + s.cumsum()
        r = s / (e - s)
        d, p = M.max_drawdown(np.concatenate([[bal], e.to_numpy()]))
        indiv[i] = {"name": bundles[i].name, "weight": w[i], "net_profit": float(s.sum()),
                    "sharpe": M.sharpe_ratio(r.to_numpy()), "max_drawdown": d}
    corr = pnl.corr().fillna(0.0)
    return {"combined": comp, "individual": indiv, "weights": w,
            "curve": {"dates": [d.strftime("%Y-%m-%d") for d in pnl.index], "combined": eq.round(2).tolist(),
                      **{i: (bal + (pnl[i] * w[i]).cumsum()).round(2).tolist() for i in ids}},
            "correlation": {"labels": ids, "values": corr.round(4).values.tolist()},
            "avg_pairwise_correlation": float(corr.values[np.triu_indices(len(ids), 1)].mean()) if len(ids) > 1 else 0.0}


def correlation(session: Session, ids: list[str], kind: str) -> dict:
    bundles = [load_bundle(session, i) for i in ids]
    if kind == "instruments":
        from ..data.real import RealDataError

        frames = {}
        for sym in ("MNQ", "NQ", "MES", "ES"):
            try:
                md = get_market_data(sym, bundles[0].cfg.seed if bundles else 42, "5m",
                                     bundles[0].cfg.data_model if bundles else "random_walk")
            except RealDataError:
                continue  # real data is only available for the symbols you supplied
            d = md.df.groupby("date")["close"].last()
            d.index = pd.to_datetime(d.index)
            frames[sym] = d.pct_change()
        if len(frames) < 2:
            raise ValueError("Instrument correlation needs data for at least two instruments.")
        df = pd.DataFrame(frames).dropna()
        labels = list(df.columns)
    else:
        series = []
        for b in bundles:
            d = b.daily()
            idx = pd.to_datetime(d["date"])
            if kind == "returns":
                s = pd.Series(d["return"].to_numpy(), index=idx)
            elif kind == "daily_pnl":
                s = pd.Series(d["net_pnl"].to_numpy(), index=idx)
            elif kind == "drawdowns":
                s = pd.Series(d["drawdown"].to_numpy(), index=idx)
            elif kind == "signals":  # net long-minus-short trade count per day
                t = b.df.assign(sign=np.where(b.df["direction"] == "Long", 1, -1))
                s = t.groupby("date")["sign"].sum()
                s.index = pd.to_datetime(s.index)
                s = s.reindex(idx).fillna(0.0)
            else:
                raise KeyError(kind)
            series.append(s.rename(b.id))
        df = _align(series)
        labels = [f"{b.id} {b.name}" for b in bundles]
        df.columns = labels
    corr = df.corr().fillna(0.0)
    return {"kind": kind, "labels": labels, "values": corr.round(4).values.tolist(), "observations": int(len(df))}
