"""Trade explorer: filtering, sorting, pagination, CSV export and the single-trade chart."""
from __future__ import annotations

import pandas as pd

from ..quant.analysis import TIME_BUCKETS, WEEKDAYS
from .store import Bundle

TABLE_COLUMNS = ["id", "symbol", "date", "entry_time", "exit_time", "direction", "entry_price", "exit_price",
                 "quantity", "stop", "target", "gross_pnl", "fees", "slippage", "net_pnl", "r_multiple", "mae",
                 "mfe", "duration_minutes", "regime", "setup", "confidence", "exit_reason"]
SORTABLE = set(TABLE_COLUMNS)


def filter_trades(df: pd.DataFrame, q: dict) -> pd.DataFrame:
    if df.empty:
        return df
    m = pd.Series(True, index=df.index)
    if q.get("date_from"):
        m &= df["date"] >= pd.Timestamp(q["date_from"]).date()
    if q.get("date_to"):
        m &= df["date"] <= pd.Timestamp(q["date_to"]).date()
    res = q.get("result")
    if res == "winner":
        m &= df["net_pnl"] > 0
    elif res == "loser":
        m &= df["net_pnl"] < 0
    if q.get("direction") in ("Long", "Short"):
        m &= df["direction"] == q["direction"]
    for col in ("symbol", "setup", "regime", "exit_reason"):
        if q.get(col):
            m &= df[col] == q[col]
    if q.get("time_of_day"):
        mins = df["entry_dt"].dt.hour * 60 + df["entry_dt"].dt.minute - (9 * 60 + 30)
        for lo, hi, lab in TIME_BUCKETS:
            if lab == q["time_of_day"]:
                m &= (mins >= lo) & (mins < hi)
    if q.get("day_of_week") in WEEKDAYS:
        m &= df["entry_dt"].dt.dayofweek == WEEKDAYS.index(q["day_of_week"])
    for key, col, op in (("min_profit", "net_pnl", ">="), ("max_profit", "net_pnl", "<="),
                         ("min_duration", "duration_minutes", ">="), ("max_duration", "duration_minutes", "<=")):
        if q.get(key) not in (None, ""):
            v = float(q[key])
            m &= (df[col] >= v) if op == ">=" else (df[col] <= v)
    if q.get("min_loss") not in (None, ""):  # losses at least this large (positive number of dollars)
        m &= df["net_pnl"] <= -abs(float(q["min_loss"]))
    if q.get("max_loss") not in (None, ""):
        m &= (df["net_pnl"] >= -abs(float(q["max_loss"])))
    return df[m]


def page(df: pd.DataFrame, sort_by: str, sort_dir: str, page_no: int, page_size: int) -> dict:
    if sort_by not in SORTABLE:
        sort_by = "entry_time"
    d = df.sort_values(sort_by, ascending=(sort_dir != "desc"), kind="stable")
    total = len(d)
    start = (page_no - 1) * page_size
    rows = d.iloc[start : start + page_size][TABLE_COLUMNS].copy()
    rows["date"] = rows["date"].astype(str)
    return {"total": total, "page": page_no, "page_size": page_size, "rows": rows.to_dict("records"),
            "summary": {"net_pnl": float(d["net_pnl"].sum()) if total else 0.0,
                        "winners": int((d["net_pnl"] > 0).sum()) if total else 0}}


def to_csv(df: pd.DataFrame) -> str:
    out = df[TABLE_COLUMNS].copy()
    out["date"] = out["date"].astype(str)
    return out.to_csv(index=False)


def facets(df: pd.DataFrame) -> dict:
    def uniq(c): return sorted(df[c].unique().tolist()) if len(df) else []
    return {"symbols": uniq("symbol"), "setups": uniq("setup"), "regimes": uniq("regime"),
            "exit_reasons": uniq("exit_reason"), "time_buckets": [b[2] for b in TIME_BUCKETS], "weekdays": WEEKDAYS}


def trade_chart(b: Bundle, trade_id: str, before: int = 40, after: int = 24) -> dict:
    from ..backtesting.market import get_market_data

    row = b.df[b.df["id"] == trade_id]
    if row.empty:
        raise KeyError(trade_id)
    trade = next(t for t in b.trades if t["id"] == trade_id)
    md = get_market_data(b.cfg.symbol, b.cfg.seed, b.cfg.timeframe)
    i0, i1 = max(trade["entry_bar"] - before, 0), min(trade["exit_bar"] + after, len(md.df) - 1)
    key = "__emas__"
    if key not in md.cache:
        c = md.df["close"]
        md.cache[key] = (c.ewm(span=9, adjust=False).mean().to_numpy(), c.ewm(span=21, adjust=False).mean().to_numpy())
    e9, e21 = md.cache[key]
    sl = md.df.iloc[i0 : i1 + 1]
    bars = [{"t": md.stamp(i), "o": float(sl["open"].iat[k]), "h": float(sl["high"].iat[k]),
             "l": float(sl["low"].iat[k]), "c": float(sl["close"].iat[k]), "v": int(sl["volume"].iat[k]),
             "vwap": round(float(md.vwap[i]), 2), "ema9": round(float(e9[i]), 2), "ema21": round(float(e21[i]), 2),
             "atr": round(float(md.atr[i]), 2)}
            for k, i in enumerate(range(i0, i1 + 1))]
    stop_path = [{"t": trade["entry_time"], "price": trade["stop"]}]
    for ev in sorted(trade["events"], key=lambda e: e["time"]):
        if ev["kind"] in ("breakeven", "trail"):
            stop_path.append({"t": ev["time"], "price": ev["price"]})
    stop_path.append({"t": trade["exit_time"], "price": stop_path[-1]["price"]})
    t = dict(trade)
    t["date"] = str(t["date"])
    return {"trade": t, "bars": bars, "stop_path": stop_path,
            "levels": {"entry": trade["entry_price"], "exit": trade["exit_price"], "stop": trade["stop"],
                       "target": trade["target"]},
            "events": trade["events"]}
