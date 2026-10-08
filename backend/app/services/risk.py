"""Risk tools: position sizing, losing-streak probabilities and sizing-model comparison."""
from __future__ import annotations

import math

import numpy as np

from ..backtesting.instruments import get_instrument
from ..quant import metrics as M
from .store import Bundle


def position_size(symbol: str, account_balance: float, risk_dollars: float | None, risk_pct: float | None,
                  stop_points: float, win_rate: float | None, avg_win_r: float | None, max_contracts: int = 100) -> dict:
    inst = get_instrument(symbol)
    budget = risk_dollars if risk_dollars else account_balance * (risk_pct or 0.5) / 100.0
    per_contract = stop_points * inst.point_value
    contracts = int(budget // per_contract) if per_contract > 0 else 0
    kelly = None
    if win_rate is not None and avg_win_r:
        kelly = win_rate - (1 - win_rate) / avg_win_r
    table = []
    for pts in sorted({max(1.0, stop_points * f) for f in (0.5, 0.75, 1.0, 1.5, 2.0, 3.0)}):
        pc = pts * inst.point_value
        q = int(budget // pc)
        table.append({"stop_points": round(pts, 2), "risk_per_contract": pc, "contracts": min(q, max_contracts),
                      "actual_risk": min(q, max_contracts) * pc})
    return {"symbol": symbol, "risk_budget": budget, "risk_per_contract": per_contract,
            "contracts": min(contracts, max_contracts), "actual_risk": min(contracts, max_contracts) * per_contract,
            "risk_pct_of_account": (min(contracts, max_contracts) * per_contract) / account_balance * 100,
            "kelly_fraction": kelly, "half_kelly_pct": (kelly / 2 * 100) if kelly and kelly > 0 else None,
            "point_value": inst.point_value, "tick_value": inst.tick_value, "table": table}


def sizing_comparison(b: Bundle, balance: float, fixed_risk: float, pct_risk: float, fixed_contracts: int) -> dict:
    """Re-size the historical trades under different models using each trade's R multiple."""
    df = b.df.sort_values("exit_dt")
    r = df["r_multiple"].to_numpy(dtype=float)
    pnl_per_contract = (df["net_pnl"] / df["quantity"]).to_numpy(dtype=float)
    wr = float((r > 0).mean()) if len(r) else 0.0
    avg_w = float(r[r > 0].mean()) if (r > 0).any() else 0.0
    avg_l = float(abs(r[r < 0].mean())) if (r < 0).any() else 1.0
    kelly = max(wr - (1 - wr) / (avg_w / avg_l), 0.0) if avg_w > 0 else 0.0
    models = {}

    def run(name: str, fn):
        eq, peak, mdd, cur = [balance], balance, 0.0, balance
        for i in range(len(r)):
            cur += fn(cur, i)
            eq.append(cur)
            peak = max(peak, cur)
            mdd = max(mdd, peak - cur)
            if cur <= 0:
                break
        step = max(1, len(eq) // 150)
        models[name] = {"final_balance": eq[-1], "return_pct": (eq[-1] / balance - 1) * 100, "max_drawdown": mdd,
                        "curve": [round(v, 2) for v in eq[::step]]}

    run(f"Fixed ${fixed_risk:g} risk", lambda cur, i: r[i] * fixed_risk)
    run(f"Fixed {pct_risk:g}% of equity", lambda cur, i: r[i] * cur * pct_risk / 100)
    run(f"Fixed {fixed_contracts} contracts", lambda cur, i: pnl_per_contract[i] * fixed_contracts)
    if kelly > 0:
        run(f"Half-Kelly ({kelly / 2:.1%})", lambda cur, i: r[i] * cur * kelly / 2)
    return {"models": models, "win_rate": wr, "avg_win_r": avg_w, "avg_loss_r": avg_l, "kelly_fraction": kelly,
            "trades": len(r)}


def streak_probabilities(loss_prob: float, ns=(50, 100, 250, 500), ks=range(3, 16)) -> dict:
    """P(at least one run of k consecutive losses within n trades) via a run-length Markov chain."""
    out = []
    for n in ns:
        row = {"trades": n, "probabilities": []}
        for k in ks:
            state = np.zeros(k)  # state[j] = P(current run = j, no run of k yet)
            state[0] = 1.0
            for _ in range(n):
                nxt = np.zeros(k)
                nxt[0] = state.sum() * (1 - loss_prob)
                nxt[1:] = state[:-1] * loss_prob
                state = nxt
            row["probabilities"].append({"k": k, "probability": float(1 - state.sum())})
        out.append(row)
    return {"loss_probability": loss_prob, "rows": out}


def losing_streak_report(b: Bundle) -> dict:
    pnl = b.df.sort_values("exit_dt")["net_pnl"].to_numpy(dtype=float)
    loss_prob = float((pnl < 0).mean()) if len(pnl) else 0.0
    runs = M.streak_lengths(pnl, False)
    # money lost in each historical losing streak
    sums, cur, run = [], 0.0, 0
    for x in pnl:
        if x < 0:
            cur += x
            run += 1
        else:
            if run:
                sums.append(cur)
            cur, run = 0.0, 0
    if run:
        sums.append(cur)
    worst = sorted(sums)[:5]
    return {"loss_probability": loss_prob, "longest": max(runs, default=0), "count": len(runs),
            "average": float(np.mean(runs)) if runs else 0.0, "worst_streak_losses": worst,
            "probabilities": streak_probabilities(loss_prob),
            "median_longest_streak_250": _median_longest(loss_prob, 250)}


def _median_longest(loss_prob: float, n: int) -> int:
    """Largest k such that a k-loss run appears in n trades at least half the time."""
    best = 0
    for k in range(1, 40):
        p = streak_probabilities(loss_prob, (n,), [k])["rows"][0]["probabilities"][0]["probability"]
        if p >= 0.5:
            best = k
        else:
            break
    return best
