"""Transparent scoring: strategy score, robustness score, automated warnings, overfitting risk.

Every number is a documented, monotone mapping onto 0-100 (or 0-1 risk). The methodology lists
returned alongside the scores are what the UI shows under "Show methodology".
"""
from __future__ import annotations

import math

import numpy as np


def clip01(x: float | None) -> float:
    if x is None or not math.isfinite(x):
        return 0.0
    return float(min(max(x, 0.0), 1.0))


def _safe(x, default=0.0):
    return default if x is None or not math.isfinite(x) else float(x)


# ------------------------------------------------------------------ robustness
ROBUSTNESS_WEIGHTS = {
    "oos_performance": 0.20, "walk_forward": 0.15, "monte_carlo": 0.15, "parameter_stability": 0.15,
    "slippage_resilience": 0.10, "commission_resilience": 0.05, "outlier_dependence": 0.10, "trade_count": 0.10,
}


def robustness_score(inp: dict) -> dict:
    """inp keys: is_expectancy, oos_expectancy, wf_consistency, mc_prob_profit, mc_prob_ruin,
    stability_score, base_net, slip2_net, comm2_net, top10_share, net_after_top5pct, trades."""
    is_e, oos_e = _safe(inp.get("is_expectancy")), _safe(inp.get("oos_expectancy"))
    oos = 100 * clip01(oos_e / is_e) if is_e > 0 else 0.0
    wf = 100 * clip01(inp.get("wf_consistency"))
    mc = 100 * (0.6 * clip01(inp.get("mc_prob_profit")) + 0.4 * (1 - clip01(inp.get("mc_prob_ruin"))))
    ps = _safe(inp.get("stability_score"))
    base = _safe(inp.get("base_net"))
    slip = 100 * clip01(_safe(inp.get("slip2_net")) / base) if base > 0 else 0.0
    comm = 100 * clip01(_safe(inp.get("comm2_net")) / base) if base > 0 else 0.0
    out = 100 * clip01(1 - _safe(inp.get("top10_share")) / 0.6)
    if _safe(inp.get("net_after_top5pct")) <= 0:
        out = min(out, 15.0)
    tc = 100 * clip01(_safe(inp.get("trades")) / 400)
    parts = {"oos_performance": oos, "walk_forward": wf, "monte_carlo": mc, "parameter_stability": ps,
             "slippage_resilience": slip, "commission_resilience": comm, "outlier_dependence": out,
             "trade_count": tc}
    total = sum(parts[k] * w for k, w in ROBUSTNESS_WEIGHTS.items())
    return {"score": float(total), "components": parts, "weights": ROBUSTNESS_WEIGHTS,
            "methodology": [
                "OOS performance: OOS expectancy / in-sample expectancy (walk-forward), capped at 100%",
                "Walk-forward: share of out-of-sample windows that were profitable",
                "Monte Carlo: 60% probability of profit + 40% probability of avoiding ruin",
                "Parameter stability: stability score of the neighbourhood around the best parameters",
                "Slippage resilience: net profit retained with 2 ticks of slippage / base net profit",
                "Commission resilience: net profit retained with 2x commissions / base net profit",
                "Outlier dependence: 100 when the 10 best trades are <= 0% of gross profit, 0 at >= 60%; capped low if profit vanishes without the top 5%",
                "Trade count: 100 at >= 400 trades, linear below"]}


# ------------------------------------------------------------------ strategy score
STRATEGY_WEIGHTS = {"profitability": 0.20, "risk": 0.20, "robustness": 0.25, "consistency": 0.15,
                    "execution_resilience": 0.10, "prop_suitability": 0.10}


def strategy_score(metrics: dict, extra: dict, robustness: float) -> dict:
    pf = _safe(metrics.get("profit_factor"), 0.0)
    pf = min(pf, 5.0)
    profit = 100 * (0.5 * clip01((pf - 1) / 1.0) + 0.25 * clip01(_safe(metrics.get("cagr")) / 0.5)
                    + 0.25 * clip01(_safe(metrics.get("avg_r")) / 0.3))
    dd = _safe(metrics.get("max_drawdown_pct"))
    risk = 100 * (0.5 * clip01(1 - dd / 0.30) + 0.3 * clip01(_safe(metrics.get("sharpe")) / 2.5)
                  + 0.2 * clip01(_safe(metrics.get("calmar")) / 3.0))
    ls = _safe(metrics.get("max_consecutive_losses"))
    consistency = 100 * (0.4 * clip01((_safe(extra.get("profitable_months")) - 0.4) / 0.4)
                         + 0.2 * clip01(1 - (ls - 5) / 15) + 0.4 * clip01(_safe(extra.get("equity_r2"))))
    base = _safe(extra.get("base_net"))
    ex_parts = []
    for k in ("slip2_net", "comm2_net"):
        ex_parts.append(clip01(_safe(extra.get(k)) / base) if base > 0 else 0.0)
    execution = 100 * float(np.mean(ex_parts))
    prop = 100 * (0.7 * clip01(extra.get("prop_pass_probability")) + 0.3 * clip01(extra.get("prop_survival_90d")))
    parts = {"profitability": profit, "risk": risk, "robustness": robustness, "consistency": consistency,
             "execution_resilience": execution, "prop_suitability": prop}
    raw = sum(parts[k] * w for k, w in STRATEGY_WEIGHTS.items())
    # HONESTY GATE: a strategy that loses money, or whose profit is indistinguishable from luck,
    # cannot score well no matter how smooth its equity curve looks.
    exp, pval = metrics.get("expectancy"), metrics.get("expectancy_pvalue")
    if exp is None or exp <= 0:
        cap, verdict = 25.0, "No edge: the average trade loses money after costs"
    elif pval is None or pval > 0.05:
        cap, verdict = 45.0, (f"Unproven: profit is not statistically significant (p = {pval:.2f}) - "
                              "consistent with luck" if pval is not None else "Unproven: too few trades to test")
    else:
        cap, verdict = 100.0, ("Statistical evidence of a positive edge (p < 0.05) - still confirm out-of-sample "
                               "and beware multiple-testing if many variants were tried")
    total = min(raw, cap)
    grade = "A" if total >= 80 else "B" if total >= 65 else "C" if total >= 50 else "D" if total >= 35 else "F"
    return {"score": float(total), "uncapped_score": float(raw), "capped": raw > cap, "cap": cap,
            "verdict": verdict, "grade": grade, "components": parts, "weights": STRATEGY_WEIGHTS,
            "methodology": [
                "Honesty gate: score is capped at 25 if expectancy <= 0 after costs, and at 45 if the mean trade "
                "P&L is not statistically significant (t-test p > 0.05)",
                "Profitability (20%): 50% profit factor (1.0 -> 0, 2.0 -> 100), 25% CAGR (50% -> 100), 25% average R (0.3 -> 100)",
                "Risk (20%): 50% max drawdown % (30% -> 0), 30% Sharpe (2.5 -> 100), 20% Calmar (3 -> 100)",
                "Robustness (25%): the robustness score (OOS, walk-forward, Monte Carlo, parameters, costs, outliers, trade count)",
                "Consistency (15%): 40% profitable months (40% -> 0, 80% -> 100), 20% longest losing streak (<=5 -> 100, >=20 -> 0), 40% equity-curve R-squared",
                "Execution resilience (10%): average share of net profit kept at +2 ticks slippage and 2x commissions",
                "Prop suitability (10%): 70% evaluation pass probability + 30% funded 90-day survival (default rules)"]}


# ------------------------------------------------------------------ warnings
def build_warnings(ctx: dict) -> list[dict]:
    w: list[dict] = []

    def add(code, severity, title, detail):
        w.append({"code": code, "severity": severity, "title": title, "detail": detail})

    n = ctx.get("trades", 0)
    exp, pval = ctx.get("expectancy"), ctx.get("pvalue")
    if exp is not None and n >= 5:
        if exp <= 0:
            add("no_edge", "high", "No edge after costs",
                f"Average trade loses ${abs(exp):,.2f} after fees and slippage - this strategy does not make money here.")
        elif pval is not None and pval > 0.05:
            add("significance", "medium" if pval < 0.2 else "high", "Profit not statistically significant",
                f"Mean trade P&L is positive but p = {pval:.2f}: results this good are common from luck alone. "
                "Treat as unproven.")
    if n < 30:
        add("few_trades", "high", "Too few trades", f"Only {n} trades - statistics are not meaningful below ~100.")
    elif n < 100:
        add("few_trades", "medium", "Low trade count", f"{n} trades; aim for 200+ before trusting any metric.")
    if ctx.get("outlier_warning"):
        add("outliers", ctx.get("outlier_severity") or "high",
            "High outlier dependence" if ctx.get("outlier_severity") != "medium" else "Moderate outlier dependence",
            ctx["outlier_warning"])
    deg = ctx.get("oos_degradation")
    oos_net = ctx.get("oos_net_per_day")
    if oos_net is not None and oos_net <= 0:
        add("poor_oos", "high", "Poor out-of-sample performance", "Walk-forward OOS windows lost money on average.")
    elif deg is not None and deg < -0.5:
        add("poor_oos", "medium", "Weak out-of-sample performance",
            f"OOS profit per day is {abs(deg):.0%} below in-sample.")
    base, slip2 = ctx.get("base_net"), ctx.get("slip2_net")
    if base and base > 0 and slip2 is not None:
        kept = slip2 / base
        if kept < 0.5:
            add("slippage", "high", "High slippage sensitivity", f"Only {kept:.0%} of net profit survives +2 ticks of slippage.")
        elif kept < 0.75:
            add("slippage", "medium", "Moderate slippage sensitivity", f"{kept:.0%} of net profit survives +2 ticks of slippage.")
    if ctx.get("stability_class") == "sharp peak":
        add("unstable_params", "high", "Unstable parameters", "Best parameters sit on an isolated peak; neighbours perform much worse.")
    elif ctx.get("stability_class") == "moderate":
        add("unstable_params", "low", "Parameter sensitivity", "Performance changes noticeably across nearby parameter values.")
    if ctx.get("optimization_trials", 0) > 150:
        add("over_optimization", "medium", "Excessive optimisation",
            f"{ctx['optimization_trials']} parameter trials recorded - expect selection bias in the headline numbers.")
    dd = ctx.get("max_drawdown_pct", 0)
    if dd > 0.25:
        add("drawdown", "high", "High drawdown", f"Maximum drawdown is {dd:.0%} of peak equity.")
    elif dd > 0.15:
        add("drawdown", "medium", "Elevated drawdown", f"Maximum drawdown is {dd:.0%} of peak equity.")
    sh = ctx.get("sharpe", 0)
    if sh > 3:
        add("sharpe", "high", "Unrealistically high Sharpe", f"Sharpe {sh:.2f} - check for lookahead bias, costs and data quality.")
    elif sh > 2.5:
        add("sharpe", "medium", "Very high Sharpe", f"Sharpe {sh:.2f} is rarely sustained live; verify the backtest.")
    if ctx.get("regimes_covered", 7) < 3:
        add("regimes", "high", "Insufficient regime coverage", f"Trades span only {ctx['regimes_covered']} of 7 market regimes.")
    elif ctx.get("regimes_covered", 7) < 5:
        add("regimes", "medium", "Limited regime coverage", f"Trades span {ctx['regimes_covered']} of 7 market regimes.")
    la = ctx.get("lookahead")
    if la and la.get("status") == "suspect":
        add("lookahead", "high", "Possible lookahead bias", la.get("message", ""))
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(w, key=lambda x: order[x["severity"]])


# ------------------------------------------------------------------ overfitting
OVERFIT_WEIGHTS = {"parameters": 0.10, "optimization_trials": 0.15, "is_oos_degradation": 0.20,
                   "parameter_stability": 0.15, "trade_count": 0.10, "complexity": 0.05,
                   "monte_carlo_degradation": 0.10, "walk_forward_consistency": 0.15}


def overfitting_risk(ctx: dict) -> dict:
    n_par = ctx.get("n_parameters", 0)
    deg = ctx.get("is_oos_degradation")  # share of the in-sample metric lost out of sample (0..1+)
    risks = {
        "parameters": clip01((n_par - 2) / 8),
        "optimization_trials": clip01(math.log10(ctx.get("optimization_trials", 0) + 1) / 3),
        "is_oos_degradation": clip01((deg if deg is not None else 0.5) / 0.6),
        "parameter_stability": 1 - clip01(_safe(ctx.get("stability_score")) / 100),
        "trade_count": clip01(1 - _safe(ctx.get("trades")) / 500),
        "complexity": clip01(ctx.get("complexity_features", 0) / 6),
        "monte_carlo_degradation": 1 - clip01(ctx.get("mc_prob_profit")),
        "walk_forward_consistency": 1 - clip01(ctx.get("wf_consistency")),
    }
    total = 100 * sum(risks[k] * w for k, w in OVERFIT_WEIGHTS.items())
    level = "LOW" if total < 33 else "MEDIUM" if total < 60 else "HIGH"
    return {"level": level, "score": float(total), "factors": risks, "weights": OVERFIT_WEIGHTS,
            "methodology": [
                "Parameters: risk rises from 0 at 2 tunable parameters to 1 at 10",
                "Optimisation trials: log10(trials + 1) / 3 (1,000 trials = full risk)",
                "IS/OOS degradation: share of in-sample performance lost out of sample, 60% loss = full risk",
                "Parameter stability: 1 - stability score / 100",
                "Trade count: 1 - trades / 500",
                "Complexity: number of enabled management features (breakeven, trailing, partial, scaling, structure stop) / 6",
                "Monte Carlo degradation: 1 - probability of profit in resampled paths",
                "Walk-forward consistency: 1 - share of profitable OOS windows",
                "Score < 33 = LOW, < 60 = MEDIUM, otherwise HIGH"]}
