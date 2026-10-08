from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..custom.runner import CustomCodeError
from ..custom.store import describe, save_custom
from ..custom.templates import TEMPLATES
from ..custom.validate import check_code
from ..db import CustomStrategyRow
from ..utils import clean
from .deps import SessionDep, require_custom_code

router = APIRouter(prefix="/custom-strategies")


class CodeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    code: str


def _out(r: CustomStrategyRow, with_code: bool = True) -> dict:
    d = {"id": r.id, "key": f"custom:{r.id}", "name": r.name, "description": r.description,
         "parameters": [{"key": k, **v} for k, v in (r.params or {}).items()],
         "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat()}
    if with_code:
        d["code"] = r.code
    return d


def _error(e: CustomCodeError) -> HTTPException:
    return HTTPException(400, {"message": e.message, "traceback": e.traceback, "problems": e.problems})


@router.get("/templates")
def templates():
    """Starter code; safe to expose (no execution)."""
    return TEMPLATES


@router.get("")
def list_custom(session=SessionDep, _: None = Depends(require_custom_code)):
    return clean([_out(r, False) for r in session.scalars(select(CustomStrategyRow).order_by(CustomStrategyRow.id))])


@router.get("/{sid}")
def get_custom(sid: int, session=SessionDep, _: None = Depends(require_custom_code)):
    row = session.get(CustomStrategyRow, sid)
    if row is None:
        raise HTTPException(404, "Custom strategy not found")
    return clean(_out(row))


@router.post("/validate")
def validate(req: CodeRequest, _: None = Depends(require_custom_code)):
    """Static checks + a smoke run in the sandbox. Returns detected parameters."""
    problems = check_code(req.code)
    if problems:
        return {"ok": False, "problems": problems}
    try:
        info = describe(req.code)
    except CustomCodeError as e:
        return {"ok": False, "problems": e.problems or [e.message], "traceback": e.traceback}
    return clean({"ok": True, **info})


@router.post("")
def save(req: CodeRequest, session=SessionDep, _: None = Depends(require_custom_code)):
    try:
        row = save_custom(session, req.name, req.description, req.code)
    except CustomCodeError as e:
        raise _error(e) from e
    return clean(_out(row))


@router.put("/{sid}")
def update(sid: int, req: CodeRequest, session=SessionDep, _: None = Depends(require_custom_code)):
    if session.get(CustomStrategyRow, sid) is None:
        raise HTTPException(404, "Custom strategy not found")
    try:
        row = save_custom(session, req.name, req.description, req.code, sid)
    except CustomCodeError as e:
        raise _error(e) from e
    return clean(_out(row))


@router.delete("/{sid}")
def delete(sid: int, session=SessionDep, _: None = Depends(require_custom_code)):
    row = session.get(CustomStrategyRow, sid)
    if row is None:
        raise HTTPException(404, "Custom strategy not found")
    session.delete(row)
    session.commit()
    return {"deleted": sid}
