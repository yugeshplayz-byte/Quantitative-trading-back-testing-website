"""Deployment-readiness checklist.

This NEVER says a strategy is ready to trade live. The best possible verdict is
PAPER_TRADE_CANDIDATE: "this cleared the automated checks that make paper trading worth the time".
A single failed blocking check gives NOT_READY. Thresholds are deliberately conservative and are
listed in the returned methodology so you can judge them.
"""
from __future__ import annotations

import math

MIN_TRADES_FAIL, MIN_TRADES_WARN = 100, 200
MAX_P = 0.05
MIN_WF_WINDOWS, MIN_WF_CONSISTENCY = 3, 0.60
MIN_MONTHS_FAIL, MIN_MONTHS_WARN = 6, 12
DD_WARN, DD_FAIL = 0.20, 0.35
TRIALS_WARN = 20


def _num(x) -> float | None:
    return float(x) if isinstance(x, (int, float)) and math.isfinite(x) else None


def readiness(ctx: dict) -> dict:
    checks: list[dict] = []

    def add(cid: str, label: str, status: str, detail: str, blocking: bool = True):
        checks.append({"id": cid, "label": label, "status": status, "blocking": blocking, "detail": detail})

    # 1. Real data
    if ctx.get("data_model") == "real":
        add("real_data", "Tested on real market data", "pass", "Ran on your own CSV data.")
    else:
        add("real_data", "Tested on real market data", "fail",
            "This backtest used SYNTHETIC data, which cannot tell you anything about live results. "
            "Load real data (docs/REAL_DATA.md) and re-run.")

    # 2. Sample size
    n = int(ctx.get("trades", 0))
    if n < MIN_TRADES_FAIL:
        add("trades", f"At least {MIN_TRADES_WARN} trades", "fail", f"Only {n} trades: far too few to measure an edge.")
    elif n < MIN_TRADES_WARN:
        add("trades", f"At least {MIN_TRADES_WARN} trades", "warn", f"{n} trades is thin; aim for {MIN_TRADES_WARN}+.", blocking=False)
    else:
        add("trades", f"At least {MIN_TRADES_WARN} trades", "pass", f"{n} trades.")

    # 3-4. Positive expectancy and statistical significance
    exp, p, lo = _num(ctx.get("expectancy")), _num(ctx.get("pvalue")), _num(ctx.get("ci_low"))
    if exp is None or exp <= 0:
        add("expectancy", "Positive average trade after costs", "fail",
            f"Average trade is {'n/a' if exp is None else f'${exp:,.2f}'} after fees and slippage.")
    else:
        add("expectancy", "Positive average trade after costs", "pass", f"Average trade +${exp:,.2f} after costs.")
    if p is None or lo is None:
        add("significance", "Profit is distinguishable from luck", "fail", "Not enough trades to test significance.")
    elif p <= MAX_P and lo > 0:
        add("significance", "Profit is distinguishable from luck", "pass",
            f"p = {p:.3f} and the 95% interval for the average trade (${lo:,.2f} and up) excludes zero.")
    else:
        add("significance", "Profit is distinguishable from luck", "fail",
            f"p = {p:.2f}; the 95% interval for the average trade starts at ${lo:,.2f}. Results this good are common from luck alone.")

    # 5. Cost resilience
    base, s2, c15 = _num(ctx.get("base_net")), _num(ctx.get("slip2_net")), _num(ctx.get("comm15_net"))
    if base is None or s2 is None or c15 is None:
        add("costs", "Survives worse costs", "na", "Stress tests unavailable.", blocking=False)
    elif s2 > 0 and c15 > 0:
        add("costs", "Survives worse costs", "pass",
            f"Still profitable at +2 ticks slippage (${s2:,.0f}) and 1.5x commissions (${c15:,.0f}).")
    else:
        add("costs", "Survives worse costs", "fail",
            f"Net at +2 ticks slippage: ${s2:,.0f}; at 1.5x commissions: ${c15:,.0f}. Real fills are usually worse than a backtest.")

    # 6. Walk-forward
    w, cons, oos = int(ctx.get("wf_windows", 0)), _num(ctx.get("wf_consistency")), _num(ctx.get("wf_oos_net"))
    if w < MIN_WF_WINDOWS or cons is None or oos is None:
        add("walk_forward", "Out-of-sample (walk-forward) holds up", "warn",
            f"Only {w} walk-forward windows: not enough to judge. Use a longer history.", blocking=False)
    elif cons >= MIN_WF_CONSISTENCY and oos > 0:
        add("walk_forward", "Out-of-sample (walk-forward) holds up", "pass",
            f"{cons:.0%} of {w} OOS windows profitable; stitched OOS net ${oos:,.0f}.")
    else:
        add("walk_forward", "Out-of-sample (walk-forward) holds up", "fail",
            f"{cons:.0%} of {w} OOS windows profitable; stitched OOS net ${oos:,.0f} "
            f"(need at least {MIN_WF_CONSISTENCY:.0%} and positive).")

    # 7. Outlier dependence
    t1, t5, share = _num(ctx.get("outlier_top1_net")), _num(ctx.get("outlier_top5_net")), _num(ctx.get("top10_share"))
    if t1 is None:
        add("outliers", "Not carried by a few lucky trades", "na", "Unavailable.", blocking=False)
    elif t1 <= 0 or (share or 0) > 0.5:
        add("outliers", "Not carried by a few lucky trades", "fail",
            f"Net after removing the best 1% of trades: ${t1:,.0f}; the 10 best trades supply {(share or 0):.0%} of gross profit.")
    elif t5 is not None and t5 <= 0:
        add("outliers", "Not carried by a few lucky trades", "warn",
            "Profit disappears if the best 5% of trades are removed (common for trend systems, but fragile).", blocking=False)
    else:
        add("outliers", "Not carried by a few lucky trades", "pass", "Still profitable without its best trades.")

    # 8. Parameter stability
    cls = ctx.get("stability_class")
    if cls == "sharp peak":
        add("stability", "Parameters sit on a plateau, not a peak", "fail",
            "The best parameters are an isolated peak: classic curve-fitting.")
    elif cls == "moderate":
        add("stability", "Parameters sit on a plateau, not a peak", "warn", "Moderate sensitivity to parameters.", blocking=False)
    elif cls == "broad plateau":
        add("stability", "Parameters sit on a plateau, not a peak", "pass", "Performance holds across neighbouring parameter values.")
    else:
        add("stability", "Parameters sit on a plateau, not a peak", "na", "Not assessed.", blocking=False)

    # 9. Lookahead (custom strategies only)
    if ctx.get("custom"):
        la = ctx.get("lookahead") or {}
        status = la.get("status")
        if status == "suspect":
            add("lookahead", "No lookahead bias detected", "fail", la.get("message", "Signals changed when the future was removed."))
        elif status == "ok":
            add("lookahead", "No lookahead bias detected", "pass",
                "Signals were unchanged when future bars were removed (a strong hint, not proof).")
        else:
            add("lookahead", "No lookahead bias detected", "warn",
                la.get("message", "The lookahead check did not run - review your code manually."), blocking=False)

    # 10. Drawdown
    dd = _num(ctx.get("max_dd_pct"))
    if dd is None:
        add("drawdown", "Drawdown within tolerance", "na", "Unavailable.", blocking=False)
    elif dd > DD_FAIL:
        add("drawdown", "Drawdown within tolerance", "fail", f"Max drawdown {dd:.0%} of peak equity is very large.")
    elif dd > DD_WARN:
        add("drawdown", "Drawdown within tolerance", "warn", f"Max drawdown {dd:.0%}: be sure you could actually sit through it.", blocking=False)
    else:
        add("drawdown", "Drawdown within tolerance", "pass", f"Max drawdown {dd:.0%}.")

    # 11. History length / regimes
    months, regimes = float(ctx.get("months", 0)), int(ctx.get("regimes_covered", 0))
    if months < MIN_MONTHS_FAIL:
        add("history", "Enough history across regimes", "fail", f"Only {months:.0f} months tested.")
    elif months < MIN_MONTHS_WARN or regimes < 5:
        add("history", "Enough history across regimes", "warn",
            f"{months:.0f} months and {regimes} of 7 regimes covered; prefer 12+ months spanning varied conditions.", blocking=False)
    else:
        add("history", "Enough history across regimes", "pass", f"{months:.0f} months, {regimes} regimes covered.")

    # 12. Multiple testing (informational: shows the cost of trying many variants)
    trials = int(ctx.get("trials", 0))
    adj = min(1.0, (p if p is not None else 1.0) * max(trials, 1))
    if trials >= TRIALS_WARN:
        add("multiple_testing", "Selection bias from many variants is small", "warn",
            f"{trials} variants/trials logged for this strategy. Bonferroni-adjusted p = {adj:.2f}. Discount the headline numbers.", blocking=False)
    else:
        add("multiple_testing", "Selection bias from many variants is small", "pass" if trials else "na",
            f"{trials} variants logged (Bonferroni-adjusted p = {adj:.2f}).", blocking=False)

    blockers = [c for c in checks if c["blocking"] and c["status"] == "fail"]
    warns = [c for c in checks if c["status"] == "warn"]
    if blockers:
        verdict = "NOT_READY"
        headline = f"NOT READY: {len(blockers)} blocking check{'s' if len(blockers) != 1 else ''} failed."
    else:
        verdict = "PAPER_TRADE_CANDIDATE"
        headline = ("Cleared the automated checks - a candidate for PAPER TRADING, not proof of a live edge."
                    + (f" {len(warns)} warning{'s' if len(warns) != 1 else ''} to review." if warns else ""))
    return {
        "verdict": verdict, "headline": headline, "checks": checks, "blocking_failures": len(blockers),
        "warnings": len(warns), "adjusted_pvalue": adj,
        "next_steps": [
            "Paper trade (or trade the smallest possible size) for at least 4-8 weeks and compare fills, slippage and results with this backtest.",
            "Pre-commit stop conditions: the drawdown or losing streak at which you will stop, decided before you start.",
            "Do not re-tune parameters after seeing live results without re-testing on fresh data.",
            "Backtests assume fills, costs and data you must verify; live trading adds latency, outages and emotion.",
        ],
        "methodology": [
            f"Blocking: real data; at least {MIN_TRADES_FAIL} trades; positive expectancy after costs; p <= {MAX_P} AND the 95% interval above zero; "
            f"profitable at +2 ticks slippage and 1.5x commissions; at least {MIN_WF_CONSISTENCY:.0%} profitable walk-forward windows with positive stitched OOS "
            f"(when there are at least {MIN_WF_WINDOWS} windows); positive after removing the best 1% of trades and top-10 share <= 50%; no isolated parameter peak; "
            "no lookahead (custom strategies); max drawdown <= 35%; at least 6 months of data.",
            f"Warnings only: fewer than {MIN_TRADES_WARN} trades; moderate parameter sensitivity; fragile without the best 5%; drawdown above {DD_WARN:.0%}; "
            f"under {MIN_MONTHS_WARN} months or under 5 regimes; {TRIALS_WARN}+ trials logged.",
            "The best verdict is PAPER_TRADE_CANDIDATE. No check can establish that a strategy is safe to run with real money.",
        ],
    }
