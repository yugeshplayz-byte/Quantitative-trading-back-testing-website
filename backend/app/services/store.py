"""Backtest persistence, in-memory bundles and the on-disk analysis cache."""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..backtesting.market import get_market_data
from ..backtesting.runner import days_between, run_config, trades_frame
from ..backtesting.strategies import get_strategy
from ..config import git_commit
from ..db import AnalysisCache, BacktestRow, utcnow
from ..models.config import BacktestConfig
from ..prop_firm.days import DayPool, build_day_pool
from ..quant.metrics import compute_metrics, daily_frame
from ..utils import clean

_BUNDLES: "OrderedDict[int, Bundle]" = OrderedDict()
MAX_BUNDLES = 12


def code_for(int_id: int) -> str:
    return f"BT-{int_id:06d}"


def parse_id(code: str) -> int:
    try:
        return int(code.upper().replace("BT-", ""))
    except ValueError as exc:
        raise KeyError(f"Invalid backtest id {code!r}") from exc


@dataclass
class Bundle:
    int_id: int
    name: str
    cfg: BacktestConfig
    trades: list[dict]
    df: pd.DataFrame
    days: list[date]
    metrics: dict
    created_at: datetime
    git_commit: str
    tags: list[str]
    favorite: bool
    notes: str
    version: str
    meta: dict
    _pool: DayPool | None = field(default=None, repr=False)

    @property
    def id(self) -> str:
        return code_for(self.int_id)

    @property
    def pool(self) -> DayPool:
        if self._pool is None:
            self._pool = build_day_pool(self.df, self.days)
        return self._pool

    @property
    def avg_risk(self) -> float:
        r = float(self.df["risk_dollars"].mean()) if len(self.df) else 0.0
        return r if r > 0 else 100.0

    def daily(self) -> pd.DataFrame:
        return daily_frame(self.df, self.days, self.cfg.starting_balance)

    def summary(self) -> dict:
        return {"id": self.id, "name": self.name, "strategy": self.cfg.strategy, "symbol": self.cfg.symbol,
                "version": self.version, "start_date": str(self.cfg.start_date), "end_date": str(self.cfg.end_date),
                "created_at": self.created_at.isoformat(), "tags": self.tags, "favorite": self.favorite,
                "notes": self.notes, "git_commit": self.git_commit, "seed": self.cfg.seed,
                "trade_count": len(self.trades), "metrics": self.metrics, "meta": self.meta,
                "config": self.cfg.model_dump(mode="json")}


def _restore_trades(raw: list[dict]) -> list[dict]:
    out = []
    for t in raw:
        t = dict(t)
        t["date"] = date.fromisoformat(t["date"]) if isinstance(t["date"], str) else t["date"]
        out.append(t)
    return out


def _bundle_from_row(row: BacktestRow) -> Bundle:
    cfg = BacktestConfig.model_validate(row.config)
    trades = _restore_trades(row.trades)
    md = get_market_data(cfg.symbol, cfg.seed, cfg.timeframe)
    lo, hi = md.index_range(cfg.start_date, cfg.end_date)
    return Bundle(
        int_id=row.id, name=row.name, cfg=cfg, trades=trades, df=trades_frame(trades),
        days=days_between(md, lo, hi), metrics=row.metrics, created_at=row.created_at,
        git_commit=row.git_commit, tags=list(row.tags or []), favorite=bool(row.favorite), notes=row.notes or "",
        version=row.version, meta=dict(row.meta or {}))


def load_bundle(session: Session, code: str) -> Bundle:
    int_id = parse_id(code)
    hit = _BUNDLES.get(int_id)
    if hit is not None:
        _BUNDLES.move_to_end(int_id)
        return hit
    row = session.get(BacktestRow, int_id)
    if row is None:
        raise KeyError(f"Backtest {code} not found")
    b = _bundle_from_row(row)
    _BUNDLES[int_id] = b
    while len(_BUNDLES) > MAX_BUNDLES:
        _BUNDLES.popitem(last=False)
    return b


def refresh_bundle(session: Session, int_id: int) -> Bundle:
    _BUNDLES.pop(int_id, None)
    return load_bundle(session, code_for(int_id))


def create_backtest(session: Session, cfg: BacktestConfig, name: str | None = None, notes: str = "",
                    version: str = "v1", tags: list[str] | None = None, check_lookahead: bool = True) -> Bundle:
    strat = get_strategy(cfg.strategy)
    meta: dict = {}
    md = get_market_data(cfg.symbol, cfg.seed, cfg.timeframe)
    if cfg.strategy.startswith("custom:"):
        lo, _ = md.index_range(cfg.start_date, cfg.end_date)
        la = strat.prefetch(md, [strat.resolve_params(cfg.params)], lo, check_lookahead=check_lookahead)
        if la:
            meta["lookahead"] = la
    out = run_config(cfg)
    tdf = trades_frame(out.trades)
    daily = daily_frame(tdf, out.days, cfg.starting_balance)
    metrics = clean(compute_metrics(tdf, daily, cfg.starting_balance))
    row = BacktestRow(
        name=name or cfg.name or f"{strat.name} {cfg.symbol}", strategy=cfg.strategy, version=version,
        dataset=f"{cfg.symbol} {cfg.timeframe} synthetic seed={cfg.seed}",
        config=cfg.model_dump(mode="json"), metrics=metrics, trades=clean(out.trades),
        notes=notes or cfg.notes or "", tags=tags or cfg.tags, favorite=False, meta=meta,
        git_commit=git_commit(), created_at=utcnow())
    session.add(row)
    session.commit()
    session.refresh(row)
    b = _bundle_from_row(row)
    _BUNDLES[row.id] = b
    return b


def delete_backtest(session: Session, int_id: int) -> bool:
    row = session.get(BacktestRow, int_id)
    if row is None:
        return False
    session.delete(row)
    session.execute(delete(AnalysisCache).where(AnalysisCache.key.like(f"{code_for(int_id)}:%")))
    session.commit()
    _BUNDLES.pop(int_id, None)
    return True


def list_backtests(session: Session) -> list[dict]:
    rows = session.scalars(select(BacktestRow).order_by(BacktestRow.id)).all()
    return [{"id": code_for(r.id), "name": r.name, "strategy": r.strategy, "symbol": r.config.get("symbol"),
             "version": r.version, "start_date": r.config.get("start_date"), "end_date": r.config.get("end_date"),
             "created_at": r.created_at.isoformat(), "tags": r.tags or [], "favorite": bool(r.favorite),
             "notes": r.notes or "", "git_commit": r.git_commit, "seed": r.config.get("seed"),
             "trade_count": len(r.trades), "metrics": r.metrics, "meta": r.meta or {},
             "dataset": r.dataset} for r in rows]


# ------------------------------------------------------------------ analysis cache
def req_hash(payload) -> str:
    return hashlib.sha1(json.dumps(clean(payload), sort_keys=True).encode()).hexdigest()[:12]


def cached(session: Session, key: str, compute: Callable[[], dict]) -> dict:
    row = session.get(AnalysisCache, key)
    if row is not None:
        return row.payload
    payload = clean(compute())
    session.merge(AnalysisCache(key=key, payload=payload, created_at=utcnow()))
    session.commit()
    return payload


def cache_peek(session: Session, key: str) -> dict | None:
    row = session.get(AnalysisCache, key)
    return row.payload if row is not None else None


def count_optimization_trials(session: Session, strategy: str) -> int:
    """Total parameter trials recorded so far for a strategy (grid cells + walk-forward searches)."""
    total = 0
    rows = session.scalars(select(AnalysisCache).where(AnalysisCache.key.like("%:opt:%"))).all()
    for r in rows:
        if r.payload.get("strategy") == strategy:
            total += int(r.payload.get("runs", 0))
    n_bt = len(session.scalars(select(BacktestRow.id).where(BacktestRow.strategy == strategy)).all())
    return total + n_bt
