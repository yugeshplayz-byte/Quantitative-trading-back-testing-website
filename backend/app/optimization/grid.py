"""Parameter grid search and parameter-stability analysis.

Every grid cell is a full backtest of the chosen date range (indicators/signals are cached per
parameter set, so cells that differ only in stop/target/risk reuse the same signals).
"""
from __future__ import annotations

import math

import numpy as np

from ..backtesting.runner import RunOutput, run_config, trades_frame
from ..backtesting.strategies import get_strategy
from ..models.config import BacktestConfig, ParameterSpec
from ..models.prop import PropFirmRules
from ..prop_firm import montecarlo as pm
from ..prop_firm.days import build_day_pool
from ..quant.fast import day_index, fast_metrics

HIGHER_IS_BETTER = {"net_profit": True, "profit_factor": True, "sharpe": True, "sortino": True, "calmar": True,
                    "max_drawdown": False, "expectancy": True, "prop_pass_probability": True}
MIN_TRADES = 30

# numeric knobs on the config itself (besides the strategy's own parameters)
CONFIG_PARAMS: list[ParameterSpec] = [
    ParameterSpec(key="stop.value", label="Stop value (ATR x / points / $)", default=1.0, min=0.5, max=3.0, step=0.25),
    ParameterSpec(key="target.value", label="Target value (R:R / points / ATR x)", default=3.0, min=1.0, max=5.0, step=0.5),
    ParameterSpec(key="risk.risk_dollars", label="Risk per trade ($)", default=150, min=50, max=400, step=50),
    ParameterSpec(key="trading.max_trades_per_day", label="Max trades per day", default=4, min=1, max=8, step=1),
    ParameterSpec(key="management.breakeven_trigger_r", label="Breakeven trigger (R)", default=1.0, min=0.5, max=2.0, step=0.25),
    ParameterSpec(key="management.trail_atr_mult", label="Trail distance (ATR x)", default=1.5, min=0.75, max=3.0, step=0.25),
    ParameterSpec(key="execution.slippage_ticks", label="Slippage (ticks)", default=1, min=0, max=4, step=1),
]


def parameter_catalog(cfg: BacktestConfig) -> list[dict]:
    strat = get_strategy(cfg.strategy)
    out = [{**p.model_dump(), "group": "strategy"} for p in strat.parameters]
    out += [{**p.model_dump(), "group": "config"} for p in CONFIG_PARAMS]
    return out


def apply_param(cfg: BacktestConfig, name: str, value: float) -> BacktestConfig:
    c = cfg.model_copy(deep=True)
    if "." in name:
        group, key = name.split(".", 1)
        obj = getattr(c, group)
        cur = getattr(obj, key)
        setattr(obj, key, int(round(value)) if isinstance(cur, int) and not isinstance(cur, bool) else float(value))
    else:
        c.params = {**c.params, name: float(value)}
    return c


def current_value(cfg: BacktestConfig, name: str) -> float:
    if "." in name:
        group, key = name.split(".", 1)
        return float(getattr(getattr(cfg, group), key))
    strat = get_strategy(cfg.strategy)
    return float(strat.resolve_params(cfg.params)[name])


def spec_for(cfg: BacktestConfig, name: str) -> ParameterSpec:
    for p in parameter_catalog(cfg):
        if p["key"] == name:
            return ParameterSpec(**{k: p[k] for k in ("key", "label", "default", "min", "max", "step")})
    raise ValueError(f"Unknown parameter {name!r}")


def default_axis(cfg: BacktestConfig, name: str, n: int = 5) -> list[float]:
    spec = spec_for(cfg, name)
    allv = np.arange(spec.min, spec.max + spec.step * 0.5, spec.step)
    cur = current_value(cfg, name)
    i = int(np.abs(allv - cur).argmin())
    n = min(n, len(allv))
    lo = min(max(i - n // 2, 0), len(allv) - n)
    vals = [round(float(v), 4) for v in allv[lo : lo + n]]
    if all(float(v).is_integer() for v in (spec.min, spec.max, spec.step)):
        vals = [int(v) for v in vals]
    return vals


def prefetch_custom(cfg: BacktestConfig, param_sets: list[dict]) -> None:
    """For pasted-code strategies: compute every needed parameter set in one sandbox process."""
    if not cfg.strategy.startswith("custom:"):
        return
    from ..backtesting.market import get_market_data

    strat = get_strategy(cfg.strategy)
    md = get_market_data(cfg.symbol, cfg.seed, cfg.timeframe)
    lo, _ = md.index_range(cfg.start_date, cfg.end_date)
    strat.prefetch(md, [strat.resolve_params({**cfg.params, **p}) for p in param_sets], lo)


def metrics_from_output(out: RunOutput, cfg: BacktestConfig, want_prop: PropFirmRules | None = None) -> dict:
    tdf = trades_frame(out.trades)
    if len(tdf):
        net = tdf["net_pnl"].to_numpy(dtype=float)
        idx = day_index(list(tdf["date"]), out.days)
    else:
        net, idx = np.array([]), np.array([], dtype=int)
    m = fast_metrics(net, idx, len(out.days), cfg.starting_balance)
    if want_prop is not None:
        if len(tdf) >= MIN_TRADES:
            pool = build_day_pool(tdf, out.days)
            res = pm.simulate(pool, want_prop, 400, want_prop.max_evaluation_days, 1.0, 3, "evaluation")
            m["prop_pass_probability"] = float((res["status"] == pm.PASSED).mean())
        else:
            m["prop_pass_probability"] = 0.0
    return m


def run_metrics(cfg: BacktestConfig, lo: int | None = None, hi: int | None = None,
                prop: PropFirmRules | None = None) -> dict:
    out = run_config(cfg, lo, hi)
    return metrics_from_output(out, cfg, prop)


def metric_value(m: dict, metric: str) -> float:
    if m["trades"] < MIN_TRADES:
        return math.nan
    v = m.get(metric, math.nan)
    return float(v) if v is not None and math.isfinite(v) else math.nan


def run_grid(cfg: BacktestConfig, param_x: str, param_y: str, xs: list[float], ys: list[float],
             metric: str, prop: PropFirmRules | None = None, lo: int | None = None, hi: int | None = None) -> dict:
    if metric not in HIGHER_IS_BETTER:
        raise ValueError(f"Unknown metric {metric!r}; choose from {sorted(HIGHER_IS_BETTER)}")
    if len(xs) * len(ys) > 100:
        raise ValueError("Grid too large (max 100 cells)")
    if prop is None and metric == "prop_pass_probability":
        prop = PropFirmRules()
    prefetch_custom(cfg, [{param_x: x, param_y: y} for x in xs for y in ys
                          if "." not in param_x and "." not in param_y]
                    or [{param_x: x} for x in xs if "." not in param_x])
    grid, counts = [], []
    for y in ys:
        row, crow = [], []
        for x in xs:
            c = apply_param(apply_param(cfg, param_x, x), param_y, y)
            m = run_metrics(c, lo, hi, prop if metric == "prop_pass_probability" else None)
            row.append(metric_value(m, metric))
            crow.append(m["trades"])
        grid.append(row)
        counts.append(crow)
    return {"grid": grid, "trades_grid": counts}


# ------------------------------------------------------------------ stability
def stability(grid: list[list[float]], higher_better: bool, xs: list[float], ys: list[float]) -> dict:
    Z = np.array(grid, dtype=float)
    valid = np.isfinite(Z)
    if valid.sum() < 4:
        return {"score": 0.0, "classification": "insufficient data", "plateau_fraction": 0.0,
                "best_neighbour_ratio": 0.0, "flags": [["n/a"] * Z.shape[1] for _ in range(Z.shape[0])],
                "message": "Too few valid cells to judge stability."}
    zmin, zmax = np.nanmin(Z), np.nanmax(Z)
    rng = zmax - zmin
    N = np.where(valid, (Z - zmin) / rng if rng > 0 else 1.0, np.nan)
    if not higher_better:
        N = 1.0 - N
    bi = np.unravel_index(np.nanargmax(N), N.shape)
    rows, cols = N.shape

    def window(i, j, r=1):
        return N[max(i - r, 0) : i + r + 1, max(j - r, 0) : j + r + 1]

    neigh_best = float(np.nanmean(window(*bi)))
    plateau_frac = float(np.nanmean(N >= 0.6))
    pos_frac = float(np.nanmean(Z[valid] > 0)) if (Z[valid] != 0).any() and higher_better else plateau_frac
    # largest jump between adjacent cells, relative to the whole range
    dx = np.abs(np.diff(N, axis=1)) if cols > 1 else np.zeros((rows, 1))
    dy = np.abs(np.diff(N, axis=0)) if rows > 1 else np.zeros((1, cols))
    cliff = float(max(np.nanmax(dx), np.nanmax(dy))) if dx.size and dy.size else 0.0
    score = 100 * (0.45 * neigh_best + 0.25 * min(plateau_frac / 0.4, 1.0) + 0.20 * pos_frac + 0.10 * (1 - min(cliff, 1.0)))
    flags = []
    for i in range(rows):
        frow = []
        for j in range(cols):
            if not np.isfinite(N[i, j]):
                frow.append("n/a")
                continue
            w = window(i, j)
            local_mean = float(np.nanmean(w))
            local_sd = float(np.nanstd(w))
            if N[i, j] >= 0.9 and local_mean < 0.65:
                frow.append("peak")
            elif local_sd > 0.30:
                frow.append("unstable")
            elif N[i, j] >= 0.6 and local_sd <= 0.2:
                frow.append("stable")
            else:
                frow.append("neutral")
        flags.append(frow)
    if score >= 70 and neigh_best >= 0.75:
        cls, msg = "broad plateau", "Performance holds across nearby parameter values - a robust region."
    elif neigh_best < 0.55 or score < 40:
        cls, msg = "sharp peak", "The best cell is isolated; neighbours perform much worse - likely overfit."
    else:
        cls, msg = "moderate", "Some sensitivity to parameters; prefer the stable cells over the single best."
    return {"score": float(score), "classification": cls, "plateau_fraction": plateau_frac,
            "best_neighbour_ratio": neigh_best, "positive_fraction": pos_frac, "max_adjacent_jump": cliff,
            "flags": flags, "message": msg,
            "best_cell": {"x": xs[bi[1]], "y": ys[bi[0]]}}


def optimise(cfg: BacktestConfig, param_x: str, param_y: str, metric: str,
             xs: list[float] | None = None, ys: list[float] | None = None,
             prop: PropFirmRules | None = None) -> dict:
    xs = xs or default_axis(cfg, param_x)
    ys = ys or default_axis(cfg, param_y)
    res = run_grid(cfg, param_x, param_y, xs, ys, metric, prop)
    hb = HIGHER_IS_BETTER[metric]
    Z = np.array(res["grid"], dtype=float)
    if np.isfinite(Z).any():
        flat = np.nanargmax(Z) if hb else np.nanargmin(Z)
        bi = np.unravel_index(flat, Z.shape)
        best = {"x": xs[bi[1]], "y": ys[bi[0]], "value": float(Z[bi]), "trades": res["trades_grid"][bi[0]][bi[1]]}
    else:
        best = {"x": None, "y": None, "value": None, "trades": 0}
    cur = {"x": current_value(cfg, param_x), "y": current_value(cfg, param_y)}
    ci = (int(np.abs(np.array(ys) - cur["y"]).argmin()), int(np.abs(np.array(xs) - cur["x"]).argmin()))
    cur["value"] = float(Z[ci]) if np.isfinite(Z[ci]) else None
    return {"param_x": param_x, "param_y": param_y, "x_values": xs, "y_values": ys, "metric": metric,
            "higher_is_better": hb, **res, "best": best, "current": cur,
            "stability": stability(res["grid"], hb, xs, ys), "runs": len(xs) * len(ys)}
