from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models.config import BacktestConfig
from ..optimization.grid import parameter_catalog
from ..services import analysis as AN
from ..services import report as RP
from ..services import trades as TR
from ..services.store import Bundle, create_backtest, delete_backtest, list_backtests
from ..utils import clean
from .deps import SessionDep, check_custom_access, get_bundle

router = APIRouter()
ANALYTICS = {"equity", "drawdowns", "calendar", "time", "long-short", "mfe-mae", "distributions", "streaks",
             "regimes", "volatility", "events", "performance"}


class RunRequest(BaseModel):
    config: BacktestConfig
    name: str | None = None
    version: str = "v1"
    notes: str = ""
    tags: list[str] = Field(default_factory=list)


@router.post("/backtest/run")
def run_backtest(req: RunRequest, session: Session = SessionDep, x_admin_token: str | None = Header(default=None)):
    if req.config.strategy.startswith("custom:"):
        check_custom_access(x_admin_token)  # pasted code runs on the server: gated
    b = create_backtest(session, req.config, req.name, req.notes, req.version, req.tags)
    return clean(b.summary())


@router.get("/backtests")
def backtests(session: Session = SessionDep):
    return clean(list_backtests(session))


@router.get("/backtests/{bid}")
def backtest(b: Bundle = Depends(get_bundle)):
    return clean(b.summary())


@router.delete("/backtests/{bid}")
def remove(bid: str, session: Session = SessionDep):
    from ..services.store import parse_id

    if not delete_backtest(session, parse_id(bid)):
        raise HTTPException(404, f"Backtest {bid} not found")
    return {"deleted": bid}


@router.get("/backtests/{bid}/trades")
def trades(
    b: Bundle = Depends(get_bundle),
    date_from: str | None = None, date_to: str | None = None, result: str | None = None,
    direction: str | None = None, symbol: str | None = None, setup: str | None = None, regime: str | None = None,
    exit_reason: str | None = None, time_of_day: str | None = None, day_of_week: str | None = None,
    min_profit: float | None = None, max_profit: float | None = None, min_loss: float | None = None,
    max_loss: float | None = None, min_duration: float | None = None, max_duration: float | None = None,
    sort_by: str = "entry_time", sort_dir: str = "asc", page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=2000), format: str = "json",
):
    q = {k: v for k, v in locals().items() if k not in ("b", "page", "page_size", "sort_by", "sort_dir", "format")}
    df = TR.filter_trades(b.df, q)
    if format == "csv":
        d = df.sort_values(sort_by if sort_by in TR.SORTABLE else "entry_time", ascending=(sort_dir != "desc"))
        return Response(TR.to_csv(d), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{b.id}_trades.csv"'})
    return clean(TR.page(df, sort_by, sort_dir, page, page_size))


@router.get("/backtests/{bid}/facets")
def facets(b: Bundle = Depends(get_bundle)):
    return clean(TR.facets(b.df))


@router.get("/backtests/{bid}/trades/{tid}")
def one_trade(tid: str, b: Bundle = Depends(get_bundle)):
    t = next((t for t in b.trades if t["id"] == tid), None)
    if t is None:
        raise HTTPException(404, f"Trade {tid} not found")
    return clean(t)


@router.get("/backtests/{bid}/trades/{tid}/chart")
def trade_chart(tid: str, b: Bundle = Depends(get_bundle)):
    return clean(TR.trade_chart(b, tid))


@router.get("/backtests/{bid}/dashboard")
def dashboard(b: Bundle = Depends(get_bundle), session: Session = SessionDep):
    return clean(AN.dashboard(session, b))


@router.get("/backtests/{bid}/analytics/{kind}")
def analytics(kind: str, b: Bundle = Depends(get_bundle)):
    if kind not in ANALYTICS:
        raise HTTPException(404, f"Unknown analytics section {kind!r}")
    return clean(AN.analytics(b, kind))


@router.get("/backtests/{bid}/parameters")
def parameters(b: Bundle = Depends(get_bundle)):
    return clean({"parameters": parameter_catalog(b.cfg), "current": b.cfg.params})


@router.get("/backtests/{bid}/robustness")
def robustness(b: Bundle = Depends(get_bundle), session: Session = SessionDep):
    return clean(AN.robustness(session, b))


@router.get("/backtests/{bid}/report")
def report(b: Bundle = Depends(get_bundle), session: Session = SessionDep):
    return clean(RP.build_report(session, b))


@router.get("/backtests/{bid}/report.html")
def report_html(b: Bundle = Depends(get_bundle), session: Session = SessionDep):
    return HTMLResponse(RP.render_html(RP.build_report(session, b)),
                        headers={"Content-Disposition": f'attachment; filename="{b.id}_report.html"'})
