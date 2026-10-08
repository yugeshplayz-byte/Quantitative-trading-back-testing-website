from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..db import BacktestRow, PresetRow, utcnow
from ..models.config import BacktestConfig, StrategyPreset
from ..models.experiment import ExperimentUpdate
from ..services import research as RS
from ..services.store import code_for, list_backtests, load_bundle, parse_id, refresh_bundle
from ..utils import clean
from .deps import SessionDep

router = APIRouter()


# ------------------------------------------------------------------ saved strategies (presets)
def _preset_out(r: PresetRow) -> dict:
    return {"id": r.id, "name": r.name, "description": r.description, "config": r.config,
            "prop_rules": r.prop_rules, "created_at": r.created_at.isoformat()}


@router.get("/strategies")
def strategies(session=SessionDep):
    return clean([_preset_out(r) for r in session.scalars(select(PresetRow).order_by(PresetRow.id))])


@router.post("/strategies")
def save_strategy(p: StrategyPreset, session=SessionDep):
    row = session.scalar(select(PresetRow).where(PresetRow.name == p.name))
    data = dict(description=p.description, config=p.config.model_dump(mode="json"),
                prop_rules=p.prop_rules.model_dump(mode="json") if p.prop_rules else None)
    if row is None:
        row = PresetRow(name=p.name, created_at=utcnow(), **data)
        session.add(row)
    else:
        for k, v in data.items():
            setattr(row, k, v)
    session.commit()
    session.refresh(row)
    return clean(_preset_out(row))


@router.delete("/strategies/{sid}")
def delete_strategy(sid: int, session=SessionDep):
    row = session.get(PresetRow, sid)
    if row is None:
        raise HTTPException(404, "Saved strategy not found")
    session.delete(row)
    session.commit()
    return {"deleted": sid}


# ------------------------------------------------------------------ experiments
@router.get("/experiments")
def experiments(session=SessionDep):
    out = []
    for e in list_backtests(session):
        cfg = BacktestConfig.model_validate(session.get(BacktestRow, parse_id(e["id"])).config)
        out.append({**e, "dataset": e["dataset"], "parameters": cfg.params,
                    "risk_settings": cfg.risk.model_dump()})
    return clean(out)


def _patch(session, int_id: int, u: ExperimentUpdate):
    row = session.get(BacktestRow, int_id)
    if row is None:
        raise HTTPException(404, f"Experiment {code_for(int_id)} not found")
    if u.name is not None:
        row.name = u.name
    if u.notes is not None:
        row.notes = u.notes
    if u.tags is not None:
        row.tags = u.tags
    if u.favorite is not None:
        row.favorite = u.favorite
    if u.version is not None:
        row.version = u.version
    session.commit()
    refresh_bundle(session, int_id)
    return clean(load_bundle(session, code_for(int_id)).summary())


@router.post("/experiments")
def upsert_experiment(u: ExperimentUpdate, session=SessionDep):
    """Update the metadata (name/tags/notes/favourite/version) of an existing backtest experiment."""
    if not u.backtest_id:
        raise HTTPException(422, "backtest_id is required (run a backtest first to create an experiment)")
    return _patch(session, parse_id(u.backtest_id), u)


@router.patch("/experiments/{bid}")
def patch_experiment(bid: str, u: ExperimentUpdate, session=SessionDep):
    return _patch(session, parse_id(bid), u)


# ------------------------------------------------------------------ research
class CompareRequest(BaseModel):
    backtest_ids: list[str] = Field(min_length=1, max_length=8)


@router.post("/research/compare")
def compare(req: CompareRequest, session=SessionDep):
    return clean(RS.compare(session, req.backtest_ids))


class CombineRequest(BaseModel):
    weights: dict[str, float]


@router.post("/research/combine")
def combine(req: CombineRequest, session=SessionDep):
    if not req.weights or any(w < 0 for w in req.weights.values()) or sum(req.weights.values()) <= 0:
        raise HTTPException(422, "Provide at least one positive weight")
    return clean(RS.combine(session, req.weights))


class CorrRequest(BaseModel):
    backtest_ids: list[str] = Field(min_length=1, max_length=8)
    kind: str = "returns"  # returns | daily_pnl | drawdowns | signals | instruments


@router.post("/research/correlation")
def correlation(req: CorrRequest, session=SessionDep):
    return clean(RS.correlation(session, req.backtest_ids, req.kind))
