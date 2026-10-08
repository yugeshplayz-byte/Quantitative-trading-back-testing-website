"""Orchestration layer: turns a stored backtest into dashboard / analysis / robustness payloads."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..backtesting.instruments import get_instrument
from ..backtesting.strategies import get_strategy
from ..db import AnalysisCache, utcnow
from ..models.prop import PropFirmRules
from ..models.simulation import MonteCarloConfig
from ..optimization import grid as G
from ..optimization.walkforward import walk_forward as run_wf
from ..prop_firm import montecarlo as pm
from ..quant import analysis as A
from ..quant import metrics as M
from ..quant import scores as S
from ..quant import stress as ST
from ..quant.monte_carlo import run_monte_carlo
from .store import Bundle, cache_peek, cached, count_optimization_trials, req_hash


# ------------------------------------------------------------------ dashboard
def monthly_performance(b: Bundle) -> list[dict]:
    return A.calendar_analytics(b.df, b.days, b.cfg.starting_balance)["monthly"]


def health_summary(b: Bundle, outlier: dict | None = None) -> list[dict]:
    m = b.metrics
    out = outlier or ST.outlier_test(b.df, b.days, b.cfg.starting_balance)
    items = [
        ("Profitability", (m["profit_factor"] or 0) >= 1.3, (m["profit_factor"] or 0) >= 1.1,
         f"Profit factor {m['profit_factor'] or 0:.2f}"),
        ("Risk-adjusted return", (m["sharpe"] or 0) >= 1.0, (m["sharpe"] or 0) >= 0.5, f"Sharpe {m['sharpe'] or 0:.2f}"),
        ("Drawdown", m["max_drawdown_pct"] <= 0.15, m["max_drawdown_pct"] <= 0.25,
         f"Max drawdown {m['max_drawdown_pct']:.1%}"),
        ("Sample size", m["total_trades"] >= 200, m["total_trades"] >= 100, f"{m['total_trades']} trades"),
        ("Outlier dependence", not out["dependent"], out["top10_share_of_gross_profit"] < 0.6,
         f"Top 10 trades = {out['top10_share_of_gross_profit']:.0%} of gross profit"),
    ]
    return [{"name": n, "status": "good" if good else "warn" if warn else "bad", "detail": d}
            for n, good, warn, d in items]


def light_warnings(b: Bundle) -> list[dict]:
    m = b.metrics
    out = ST.outlier_test(b.df, b.days, b.cfg.starting_balance)
    tick_value = get_instrument(b.cfg.symbol).tick_value
    slip = ST.slippage_test(b.df, b.days, b.cfg.starting_balance, tick_value, b.cfg.execution.slippage_ticks)
    two = next(r for r in slip if r["ticks"] == 2)
    ctx = {
        "trades": m["total_trades"], "outlier_warning": out["warning"], "outlier_severity": out["severity"],
        "base_net": m["net_profit"], "expectancy": m["expectancy"], "pvalue": m.get("expectancy_pvalue"),
        "slip2_net": two["net_profit"], "max_drawdown_pct": m["max_drawdown_pct"], "sharpe": m["sharpe"] or 0,
        "regimes_covered": int((b.df["regime"].value_counts() >= 20).sum()) if len(b.df) else 0,
        "lookahead": b.meta.get("lookahead"),
    }
    return S.build_warnings(ctx)


def dashboard(session: Session, b: Bundle) -> dict:
    daily = b.daily()
    eq = daily[["date", "equity", "drawdown", "drawdown_pct"]].copy()
    recent = b.df.sort_values("exit_dt", ascending=False).head(12)
    cols = ["id", "date", "entry_time", "direction", "quantity", "net_pnl", "r_multiple", "setup", "exit_reason"]
    return {
        "backtest": b.summary(),
        "metrics": b.metrics,
        "equity": [{"date": str(r.date), "equity": round(r.equity, 2), "drawdown": round(r.drawdown, 2),
                    "drawdown_pct": round(r.drawdown_pct * 100, 3)} for r in eq.itertuples()],
        "monthly": monthly_performance(b),
        "recent_trades": recent[cols].astype({"date": str}).to_dict("records"),
        "warnings": light_warnings(b),
        "health": health_summary(b),
        "cached_score": cache_peek(session, f"{b.id}:score"),
    }


# ------------------------------------------------------------------ descriptive analytics
def analytics(b: Bundle, kind: str) -> dict:
    df, days, bal = b.df, b.days, b.cfg.starting_balance
    if kind == "equity":
        return A.equity_curves(df, days, bal)
    if kind == "drawdowns":
        return A.drawdown_series(df, days, bal)
    if kind == "calendar":
        return A.calendar_analytics(df, days, bal)
    if kind == "time":
        return {**A.time_analytics(df, days, bal), "long_short": A.long_short(df, days, bal)}
    if kind == "long-short":
        return A.long_short(df, days, bal)
    if kind == "mfe-mae":
        return A.mfe_mae(df)
    if kind == "distributions":
        return A.distributions(df, days, bal)
    if kind == "streaks":
        return A.streaks(df)
    if kind == "regimes":
        return {**A.regimes(df, days, bal), "volatility": A.volatility(df, days, bal)["rows"],
                "events": A.events(df, days, bal)}
    if kind == "volatility":
        return A.volatility(df, days, bal)
    if kind == "events":
        return A.events(df, days, bal)
    if kind == "performance":
        return {"metrics": b.metrics, "long_short": A.long_short(df, days, bal),
                "calendar": A.calendar_analytics(df, days, bal),
                "by_setup": A._group(df, df["setup"], sorted(df["setup"].unique().tolist()), days, bal),
                "by_exit": A._group(df, df["exit_reason"], sorted(df["exit_reason"].unique().tolist()), days, bal)}
    raise KeyError(kind)


# ------------------------------------------------------------------ simulations
def monte_carlo(session: Session, b: Bundle, cfg: MonteCarloConfig) -> dict:
    key = f"{b.id}:mc:{req_hash(cfg.model_dump())}"
    def go():
        pnl = b.df["net_pnl"].to_numpy(dtype=float)
        res = run_monte_carlo(pnl, b.avg_risk, cfg)
        cr = b.contract_risk
        res["summary"]["contract_risk"] = cr
        res["summary"]["risk_achievable"] = float(cfg.risk_per_trade is None or cr is None
                                                  or cfg.risk_per_trade >= cr / 2)
        res["summary"]["expectancy_ci95_low"] = b.metrics.get("expectancy_ci95_low")
        res["summary"]["expectancy_ci95_high"] = b.metrics.get("expectancy_ci95_high")
        return {"config": cfg.model_dump(), **res,
                "caveat": ("Monte Carlo resamples the trades this backtest ALREADY produced. It shows how path luck "
                           "changes drawdowns and ending balances, but it cannot tell you whether the underlying edge "
                           "is real - see the expectancy confidence interval and significance test for that.")}
    return cached(session, key, go)


def stress(session: Session, b: Bundle, runs: int = 300) -> dict:
    def go():
        tv = get_instrument(b.cfg.symbol).tick_value
        bal = b.cfg.starting_balance
        return {
            "baseline": ST.baseline(b.df, b.days, bal),
            "slippage": ST.slippage_test(b.df, b.days, bal, tv, b.cfg.execution.slippage_ticks),
            "commission": ST.commission_test(b.df, b.days, bal),
            "missed": ST.missed_trades_test(b.df, b.days, bal, runs),
            "outliers": ST.outlier_test(b.df, b.days, bal),
            "base_slippage_ticks": b.cfg.execution.slippage_ticks,
        }
    return cached(session, f"{b.id}:stress:{runs}", go)


def optimization(session: Session, b: Bundle, param_x: str, param_y: str, metric: str,
                 xs: list[float] | None, ys: list[float] | None, prop: PropFirmRules | None,
                 internal: bool = False) -> dict:
    # Only USER-initiated searches count as optimisation trials (selection bias); the platform's own
    # robustness probes are stored under a different key prefix and are not counted.
    tag = "optint" if internal else "opt"
    key = f"{b.id}:{tag}:{req_hash([param_x, param_y, metric, xs, ys, prop.model_dump() if prop else None])}"
    def go():
        res = G.optimise(b.cfg, param_x, param_y, metric, xs, ys, prop)
        res["strategy"] = b.cfg.strategy
        return res
    return cached(session, key, go)


def walk_forward(session: Session, b: Bundle, train: int, test: int, step: int, metric: str,
                 px: str | None, py: str | None, xs, ys, internal: bool = False) -> dict:
    tag = "optint" if internal else "opt"
    key = f"{b.id}:{tag}:wf:{req_hash([train, test, step, metric, px, py, xs, ys])}"
    def go():
        res = run_wf(b.cfg, train, test, step, metric, px, py, xs, ys)
        res["strategy"] = b.cfg.strategy
        res["runs"] = len(res["windows"]) * 10
        return res
    return cached(session, key, go)


def default_wf_months(b: Bundle) -> tuple[int, int, int]:
    total = (b.cfg.end_date.year - b.cfg.start_date.year) * 12 + b.cfg.end_date.month - b.cfg.start_date.month + 1
    if total >= 20:
        return 6, 2, 2
    train = max(2, int(total * 0.5))
    test = max(1, int(total * 0.2))
    return train, test, test


# ------------------------------------------------------------------ robustness orchestration
def _equity_r2(daily: pd.DataFrame) -> float:
    y = daily["equity"].to_numpy(dtype=float)
    if len(y) < 3 or np.allclose(y, y[0]):
        return 0.0
    x = np.arange(len(y))
    r = np.corrcoef(x, y)[0, 1]
    return float(r * r) if math.isfinite(r) and r > 0 else 0.0


def robustness(session: Session, b: Bundle) -> dict:
    """Score card combining stress tests, Monte Carlo, parameter grid, walk-forward and prop odds."""
    def go():
        bal = b.cfg.starting_balance
        strat = get_strategy(b.cfg.strategy)
        strat_params = [p.key for p in strat.parameters]
        px, py = (strat_params + ["stop.value", "target.value"])[:2]
        st = stress(session, b)
        mc = monte_carlo(session, b, MonteCarloConfig(backtest_id=b.id, simulations=1000,
                                                      trades=int(min(250, max(len(b.df), 20))),
                                                      starting_balance=bal, seed=7))
        grid = optimization(session, b, px, py, "sharpe", None, None, None, internal=True)
        tr, te, sp = default_wf_months(b)
        wf = walk_forward(session, b, tr, te, sp, "sharpe", None, None, None, None, internal=True)
        rules = PropFirmRules(starting_balance=bal)
        ev = pm.evaluation_summary(pm.simulate(b.pool, rules, 1500, rules.max_evaluation_days,
                                               1.0, 5, "evaluation"), rules)
        fund = pm.survival_summary(pm.simulate(b.pool, rules, 1000, 261, 1.0, 6, "funded"))
        surv90 = next(m["survival"] for m in fund["marks"] if m["calendar_days"] == 90)

        agg = wf.get("aggregate") or {}
        is_e = (agg.get("is") or {}).get("expectancy")
        oos_e = (agg.get("oos") or {}).get("expectancy")
        two = next(r for r in st["slippage"] if r["ticks"] == 2)
        comm2 = next(r for r in st["commission"] if r["multiplier"] == 2.0)
        rob_in = {
            "is_expectancy": is_e, "oos_expectancy": oos_e, "wf_consistency": wf.get("consistency", 0.0),
            "mc_prob_profit": mc["summary"]["prob_profit"], "mc_prob_ruin": mc["summary"]["prob_ruin"],
            "stability_score": grid["stability"]["score"], "base_net": st["baseline"]["net_profit"],
            "slip2_net": two["net_profit"], "comm2_net": comm2["net_profit"],
            "top10_share": st["outliers"]["top10_share_of_gross_profit"],
            "net_after_top5pct": st["outliers"]["net_profit_after_top5pct"], "trades": len(b.df)}
        rob = S.robustness_score(rob_in)
        daily = b.daily()
        months = A.calendar_analytics(b.df, b.days, bal)["monthly"]
        extra = {
            "profitable_months": float(np.mean([m["net_pnl"] > 0 for m in months])) if months else 0.0,
            "equity_r2": _equity_r2(daily), "base_net": st["baseline"]["net_profit"],
            "slip2_net": two["net_profit"], "comm2_net": comm2["net_profit"],
            "prop_pass_probability": ev["pass_probability"], "prop_survival_90d": surv90}
        score = S.strategy_score(b.metrics, extra, rob["score"])

        trials = count_optimization_trials(session, b.cfg.strategy)
        deg_ps = (agg.get("degradation") or {}).get("net_profit_per_day")
        is_oos_deg = None if deg_ps is None else max(0.0, -deg_ps)
        mg = b.cfg.management
        complexity = sum([mg.breakeven, mg.trailing_stop, mg.partial_profit, mg.scale_in, mg.scale_out,
                          b.cfg.stop.type == "structure"])
        n_params = len(strat_params) + (3 if mg.breakeven or mg.trailing_stop else 2)
        over = S.overfitting_risk({
            "n_parameters": n_params, "optimization_trials": trials, "is_oos_degradation": is_oos_deg,
            "stability_score": grid["stability"]["score"], "trades": len(b.df), "complexity_features": complexity,
            "mc_prob_profit": mc["summary"]["prob_profit"], "wf_consistency": wf.get("consistency", 0.0)})
        outliers = st["outliers"]
        warn = S.build_warnings({
            "trades": len(b.df), "outlier_warning": outliers["warning"], "outlier_severity": outliers["severity"],
            "oos_degradation": deg_ps,
            "oos_net_per_day": (agg.get("oos") or {}).get("net_profit_per_day"),
            "base_net": st["baseline"]["net_profit"], "slip2_net": two["net_profit"],
            "expectancy": b.metrics["expectancy"], "pvalue": b.metrics.get("expectancy_pvalue"),
            "stability_class": grid["stability"]["classification"], "optimization_trials": trials,
            "max_drawdown_pct": b.metrics["max_drawdown_pct"], "sharpe": b.metrics["sharpe"] or 0,
            "regimes_covered": int((b.df["regime"].value_counts() >= 20).sum()) if len(b.df) else 0,
            "lookahead": b.meta.get("lookahead")})
        return {"robustness": rob, "score": score, "overfitting": over, "warnings": warn,
                "inputs": {"walk_forward": {"windows": len(wf["windows"]), "consistency": wf.get("consistency"),
                                            "aggregate": wf.get("aggregate")},
                           "grid": {"param_x": px, "param_y": py, "stability": grid["stability"]},
                           "monte_carlo": mc["summary"], "prop": ev, "survival_90d": surv90,
                           "optimization_trials": trials}}
    out = cached(session, f"{b.id}:robustness", go)
    session.merge(AnalysisCache(
        key=f"{b.id}:score", created_at=utcnow(),
        payload={"score": out["score"]["score"], "grade": out["score"]["grade"],
                 "robustness": out["robustness"]["score"], "overfitting": out["overfitting"]["level"]}))
    session.commit()
    return out
