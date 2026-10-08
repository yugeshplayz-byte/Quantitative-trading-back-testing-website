"""Report assembly (JSON for the web view) and a self-contained HTML export."""
from __future__ import annotations

import html
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models.prop import PropFirmRules
from ..models.simulation import MonteCarloConfig
from ..quant.ruin import risk_of_ruin
from . import analysis as AN
from . import prop as PR
from . import risk as RK
from .store import Bundle


def build_report(session: Session, b: Bundle) -> dict:
    m = b.metrics
    bal = b.cfg.starting_balance
    rob = AN.robustness(session, b)
    rules = PropFirmRules(starting_balance=bal)
    mc = AN.monte_carlo(session, b, MonteCarloConfig(backtest_id=b.id, simulations=1000, starting_balance=bal,
                                                     trades=int(min(250, max(len(b.df), 20)))))
    st = AN.stress(session, b)
    pnl = b.df["net_pnl"]
    ror = risk_of_ruin(bal, rules.max_drawdown, None, m["win_rate"], m["average_winner"], abs(m["average_loser"] or 1),
                       250)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": b.summary(),
        "performance": m,
        "equity": AN.analytics(b, "equity"),
        "drawdowns": AN.analytics(b, "drawdowns"),
        "monthly": AN.analytics(b, "calendar")["monthly_matrix"],
        "time_analysis": AN.analytics(b, "time"),
        "mfe_mae": AN.analytics(b, "mfe-mae")["stats"],
        "distributions": {k: v["stats"] for k, v in AN.analytics(b, "distributions").items()},
        "monte_carlo": mc["summary"],
        "walk_forward": rob["inputs"]["walk_forward"],
        "parameter_stability": rob["inputs"]["grid"],
        "stress_tests": {"slippage": st["slippage"], "commission": st["commission"], "outliers": st["outliers"]},
        "prop_simulation": {"single_run": PR.simulate_single(b, rules),
                            "monte_carlo": rob["inputs"]["prop"], "survival_90d": rob["inputs"]["survival_90d"]},
        "risk_analysis": {"risk_of_ruin": ror, "losing_streaks": RK.losing_streak_report(b)},
        "score": rob["score"], "robustness": rob["robustness"], "overfitting": rob["overfitting"],
        "readiness": rob["readiness"],
        "warnings": rob["warnings"],
        "data_note": "Generated from deterministic synthetic data unless a real data feed was connected.",
        "net_pnl_check": float(pnl.sum()),
    }


def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return html.escape(str(v))


def _kv_table(d: dict, keys: list[str] | None = None) -> str:
    rows = "".join(f"<tr><th>{html.escape(k.replace('_', ' '))}</th><td>{_fmt(d[k])}</td></tr>"
                   for k in (keys or d) if k in d and not isinstance(d[k], (dict, list)))
    return f"<table>{rows}</table>"


def _table(rows: list[dict], cols: list[str]) -> str:
    head = "".join(f"<th>{html.escape(c.replace('_', ' '))}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{_fmt(r.get(c))}</td>" for c in cols) + "</tr>" for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def _spark(vals: list[float], w: int = 640, h: int = 120) -> str:
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pts = " ".join(f"{i / max(len(vals) - 1, 1) * w:.1f},{h - (v - lo) / span * h:.1f}" for i, v in enumerate(vals))
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}"><polyline fill="none" stroke="#2f81f7" stroke-width="1.5" points="{pts}"/></svg>'


def render_html(r: dict) -> str:
    s, p = r["summary"], r["performance"]
    sec = []
    sec.append(f"<h1>{html.escape(s['name'])} <small>{s['id']}</small></h1>"
               f"<p>{s['symbol']} - {s['strategy']} - {s['start_date']} to {s['end_date']} - commit {s['git_commit']}</p>")
    rd = r["readiness"]
    sec.append(f"<h2>Deployment readiness: {html.escape(rd['verdict'].replace('_', ' '))}</h2><p>{html.escape(rd['headline'])}</p>"
               + _table([{"check": c["label"], "status": c["status"].upper(), "detail": c["detail"]} for c in rd["checks"]],
                        ["check", "status", "detail"]))
    sec.append(f"<h2>Strategy score: {r['score']['score']:.0f}/100 (grade {r['score']['grade']})</h2>"
               + _table([{"category": k, "score": v, "weight": r['score']['weights'][k]}
                         for k, v in r["score"]["components"].items()], ["category", "score", "weight"]))
    sec.append("<h2>Performance</h2>" + _kv_table(p))
    sec.append("<h2>Equity</h2>" + _spark(r["equity"]["net_equity"]))
    sec.append("<h2>Top drawdowns</h2>" + _table(r["drawdowns"]["periods"][:10],
               ["start", "bottom", "recovery", "depth", "depth_pct", "duration_days"]))
    sec.append("<h2>Time analysis</h2>" + _table(r["time_analysis"]["time_of_day"],
               ["label", "trades", "net_pnl", "win_rate", "profit_factor", "expectancy"]))
    sec.append("<h2>MFE / MAE</h2>" + _kv_table(r["mfe_mae"]))
    sec.append("<h2>Monte Carlo</h2>" + _kv_table(r["monte_carlo"]))
    sec.append("<h2>Stress tests</h2><h3>Slippage</h3>" + _table(r["stress_tests"]["slippage"],
               ["ticks", "net_profit", "profit_factor", "sharpe"]) + "<h3>Commission</h3>"
               + _table(r["stress_tests"]["commission"], ["label", "net_profit", "profit_factor", "sharpe"]))
    sec.append("<h2>Overfitting risk: " + r["overfitting"]["level"] + "</h2>"
               + _table([{"factor": k, "risk": v} for k, v in r["overfitting"]["factors"].items()], ["factor", "risk"]))
    sec.append("<h2>Warnings</h2>" + ("<ul>" + "".join(
        f"<li><b>{html.escape(w['severity'].upper())}</b> {html.escape(w['title'])}: {html.escape(w['detail'])}</li>"
        for w in r["warnings"]) + "</ul>" if r["warnings"] else "<p>None.</p>"))
    sec.append(f"<p class='note'>{html.escape(r['data_note'])} Generated {r['generated_at']}.</p>")
    css = ("body{font:14px system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#111}"
           "table{border-collapse:collapse;margin:.5rem 0}td,th{border:1px solid #ccc;padding:3px 8px;text-align:right}"
           "th{background:#f3f4f6;text-align:left}h1 small{color:#666;font-weight:400}.note{color:#666}")
    return f"<!doctype html><meta charset=utf-8><title>{html.escape(s['name'])} report</title><style>{css}</style>" + "".join(sec)
