"""Persistence + lookup for user strategies."""
from __future__ import annotations

from sqlalchemy import select

from ..backtesting.market import get_market_data
from ..db import CustomStrategyRow, SessionLocal, utcnow
from .runner import run_worker
from .strategy import CustomStrategy, bars_frame


def load_custom(sid: int) -> CustomStrategy:
    with SessionLocal() as s:
        row = s.get(CustomStrategyRow, sid)
        if row is None:
            raise ValueError(f"Custom strategy {sid} not found")
        specs = [{"key": k, **v} for k, v in (row.params or {}).items()]
        return CustomStrategy(row.id, row.name, row.description, row.code, specs)


def describe(code: str) -> dict:
    """Run the code once in the sandbox to get parameter specs and surface errors early."""
    md = get_market_data("MNQ", 42, "5m")
    lo, _ = md.index_range("2023-01-02", "2024-12-31")
    return run_worker(code, bars_frame(md), "describe", lo, len(md.df))


def save_custom(session, name: str, description: str, code: str, sid: int | None = None) -> CustomStrategyRow:
    info = describe(code)
    params = {p["key"]: {k: v for k, v in p.items() if k != "key"} for p in info["parameters"]}
    row = session.get(CustomStrategyRow, sid) if sid else None
    if row is None:
        row = session.scalar(select(CustomStrategyRow).where(CustomStrategyRow.name == name))
    if row is None:
        row = CustomStrategyRow(name=name, description=description, code=code, params=params)
        session.add(row)
    else:
        row.name, row.description, row.code, row.params, row.updated_at = name, description, code, params, utcnow()
    session.commit()
    session.refresh(row)
    return row
