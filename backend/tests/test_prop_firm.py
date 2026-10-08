"""Prop-firm rule engine: hand-built day sequences with known outcomes."""
import numpy as np

from app.models.prop import PropFirmRules
from app.prop_firm import montecarlo as pm
from app.prop_firm.days import DayPool
from app.prop_firm.rules import evaluate_challenge


def pool(pnl, low=None, high=None, contracts=2):
    pnl = np.array(pnl, dtype=float)
    low = np.minimum(pnl, 0) if low is None else np.array(low, dtype=float)
    high = np.maximum(pnl, 0) if high is None else np.array(high, dtype=float)
    n = len(pnl)
    return DayPool([f"D{i + 1}" for i in range(n)], pnl, low, high,
                   np.full(n, contracts), np.ones(n, bool), np.full(n, 360.0))


def rules(**kw):
    base = dict(starting_balance=50_000, profit_target=3_000, max_drawdown=2_500, daily_loss_limit=1_000,
                drawdown_type="static", min_trading_days=3, consistency_pct=None, max_contracts=10,
                max_evaluation_days=30)
    base.update(kw)
    return PropFirmRules(**base)


def test_pass_when_target_reached():
    res = evaluate_challenge(pool([500, 500, 500, 600, 1000]), rules())
    assert res.status == "PASS" and res.failure_type == "none"
    assert res.trading_days_elapsed == 5 and res.profit == 3100
    assert "Profit target" in res.reason


def test_min_trading_days_blocks_early_pass():
    res = evaluate_challenge(pool([3200, 100]), rules(min_trading_days=3))
    assert res.status == "ACTIVE"
    res2 = evaluate_challenge(pool([3200, 100, 100]), rules(min_trading_days=3))
    assert res2.status == "PASS" and res2.trading_days_elapsed == 3


def test_daily_loss_limit_fail_reason():
    res = evaluate_challenge(pool([400, -300, 200], low=[0, -1200, 0]), rules())
    assert res.status == "FAIL" and res.failure_type == "daily_loss"
    assert "Daily loss limit breached" in res.reason and "D2" in res.reason


def test_static_drawdown_fail():
    res = evaluate_challenge(pool([-800, -800, -800, -800]), rules(daily_loss_limit=1_000))
    assert res.status == "FAIL" and res.failure_type == "drawdown"
    # balance before day 4 is 47,600; the 4th day's low 46,800 is below the 47,500 floor
    assert res.trading_days_elapsed == 4 and "Maximum drawdown breached" in res.reason


def test_max_contracts_fail():
    res = evaluate_challenge(pool([100, 100], contracts=12), rules(max_contracts=10))
    assert res.status == "FAIL" and res.failure_type == "contracts"
    assert "Maximum contracts exceeded" in res.reason


def test_consistency_rule_blocks_pass():
    r = rules(consistency_pct=40, min_trading_days=1)
    res = evaluate_challenge(pool([2000, 500, 600]), r)
    assert res.status == "ACTIVE" and any("consistency" in c["detail"] for c in res.checks)
    ok = evaluate_challenge(pool([1000, 1000, 1100]), r)
    assert ok.status == "PASS"


def test_eod_trailing_floor_locks_at_start():
    r = rules(drawdown_type="eod_trailing", daily_loss_limit=None, profit_target=10_000)
    # peak 51,500 -> floor min(49,000, 50,000) = 49,000 ; second day stays above, third breaches
    res = evaluate_challenge(pool([1500, -1000, -600], low=[0, -1000, -1600]), r)
    assert res.status == "FAIL" and res.failure_type == "drawdown"
    assert res.trading_days_elapsed == 3
    # the same path survives a static-style floor of 47,500
    assert evaluate_challenge(pool([1500, -1000, -600], low=[0, -1000, -1600]),
                              rules(drawdown_type="static", daily_loss_limit=None,
                                    profit_target=10_000)).status == "ACTIVE"


def test_intraday_trailing_is_stricter_than_eod():
    p = pool([500, -900], low=[-100, -1100], high=[2000, 0])
    common = dict(daily_loss_limit=None, profit_target=20_000)
    assert evaluate_challenge(p, rules(drawdown_type="intraday_trailing", **common)).status == "FAIL"
    assert evaluate_challenge(p, rules(drawdown_type="eod_trailing", **common)).status == "ACTIVE"


def test_monte_carlo_reproducible_and_bounded():
    base = pool(list(np.random.default_rng(3).normal(40, 500, 120)))
    r = rules(drawdown_type="eod_trailing", max_evaluation_days=60)
    a = pm.evaluation_summary(pm.simulate(base, r, 500, seed=8), r)
    b = pm.evaluation_summary(pm.simulate(base, r, 500, seed=8), r)
    assert a["pass_probability"] == b["pass_probability"]
    total = a["pass_probability"] + a["fail_probability"] + a["active_probability"]
    assert abs(total - 1.0) < 1e-9
    fails = a["drawdown_failure_probability"] + a["daily_loss_failure_probability"] + a["other_failure_probability"]
    assert abs(fails - a["fail_probability"]) < 1e-9


def test_vectorised_matches_deterministic_for_single_path():
    """A pool with one repeated day makes every simulated path identical to the sequential evaluator."""
    p = pool([700])
    r = rules(min_trading_days=1, max_evaluation_days=10)
    seq = evaluate_challenge(DayPool(["d"] * 10, np.full(10, 700.0), np.zeros(10), np.full(10, 700.0),
                                     np.full(10, 2), np.ones(10, bool), np.full(10, 360.0)), r)
    sim = pm.simulate(p, r, 50, seed=1)
    assert seq.status == "PASS" and seq.trading_days_elapsed == 5
    assert (sim["status"] == pm.PASSED).all() and (sim["end_day"] == 5).all()


def test_payouts_and_survival_shapes():
    base = pool([300, 250, -100, 400, 150, -50, 500, 200, 100, 350])
    r = rules(drawdown_type="static", max_drawdown=5_000)
    res = pm.simulate(base, r, 300, horizon=120, mode="funded", payouts=True, seed=2)
    pay = pm.payout_summary(res, r)
    assert 0 <= pay["prob_third_payout"] <= pay["prob_second_payout"] <= pay["prob_first_payout"] <= 1
    surv = pm.survival_summary(res)
    s = [m["survival"] for m in surv["marks"]]
    assert all(a >= b - 1e-12 for a, b in zip(s, s[1:]))  # survival never increases with time
