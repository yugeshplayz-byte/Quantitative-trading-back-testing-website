"""Scores, warnings and sizing must never flatter a strategy."""
import pytest

from app.quant import scores as S

GOOD_METRICS = {"profit_factor": 2.2, "cagr": 0.6, "avg_r": 0.4, "max_drawdown_pct": 0.05, "sharpe": 3.0,
                "calmar": 5.0, "max_consecutive_losses": 4}
GOOD_EXTRA = {"profitable_months": 0.9, "equity_r2": 0.98, "base_net": 10_000, "slip2_net": 9_000,
              "comm2_net": 9_500, "prop_pass_probability": 0.9, "prop_survival_90d": 0.95}


def test_losing_strategy_is_capped_even_if_everything_else_looks_great():
    m = {**GOOD_METRICS, "expectancy": -1.5, "expectancy_pvalue": 0.4}
    s = S.strategy_score(m, GOOD_EXTRA, robustness=95)
    assert s["score"] <= 25 and s["capped"] and "No edge" in s["verdict"]
    assert s["uncapped_score"] > 60  # the raw components alone would have looked impressive


def test_insignificant_profit_is_unproven():
    m = {**GOOD_METRICS, "expectancy": 12.0, "expectancy_pvalue": 0.38}
    s = S.strategy_score(m, GOOD_EXTRA, robustness=95)
    assert s["score"] <= 45 and "Unproven" in s["verdict"]


def test_significant_edge_is_not_capped_but_still_caveated():
    m = {**GOOD_METRICS, "expectancy": 12.0, "expectancy_pvalue": 0.001}
    s = S.strategy_score(m, GOOD_EXTRA, robustness=90)
    assert not s["capped"] and s["score"] > 70 and "out-of-sample" in s["verdict"]


def test_warnings_flag_no_edge_and_insignificance():
    w = S.build_warnings({"trades": 500, "expectancy": -3.0, "pvalue": 0.2})
    assert w[0]["code"] == "no_edge" and w[0]["severity"] == "high"
    w2 = S.build_warnings({"trades": 500, "expectancy": 4.0, "pvalue": 0.3})
    assert any(x["code"] == "significance" for x in w2)
    assert not any(x["code"] in ("no_edge", "significance")
                   for x in S.build_warnings({"trades": 500, "expectancy": 4.0, "pvalue": 0.01}))


def test_confidence_interval_brackets_zero_for_noise(client):
    for bid in ("BT-000001", "BT-000002", "BT-000004"):
        m = client.get(f"/api/backtests/{bid}").json()["metrics"]
        lo, hi = m["expectancy_ci95_low"], m["expectancy_ci95_high"]
        assert lo < m["expectancy"] < hi
        if m["expectancy_pvalue"] > 0.05:
            assert lo < 0 < hi  # an insignificant result must have an interval that includes zero


def test_dashboard_score_is_capped_for_random_walk_strategies(client):
    for bid in ("BT-000001", "BT-000002"):
        r = client.get(f"/api/backtests/{bid}/robustness").json()
        m = client.get(f"/api/backtests/{bid}").json()["metrics"]
        assert r["score"]["score"] <= 45, (bid, r["score"]["verdict"])
        assert m["expectancy_pvalue"] > 0.05 or r["score"]["verdict"]


def test_unachievable_risk_levels_are_flagged_and_excluded(client):
    opt = client.post("/api/prop-firm/optimizer", json={"backtest_id": "BT-000001", "simulations": 300,
                                                          "risks": [25, 50, 150, 300]}).json()
    by_risk = {r["risk_per_trade"]: r for r in opt["rows"]}
    cr = opt["contract_risk"]
    assert cr and cr > 0
    assert by_risk[25]["achievable"] is (25 >= cr / 2)
    assert by_risk[300]["achievable"] is True
    if opt["best_risk"] is not None:
        assert by_risk[opt["best_risk"]]["achievable"]


def test_caveats_are_published(client):
    meta = client.get("/api/meta").json()
    assert len(meta["caveats"]) >= 6 and any("synthetic" in c for c in meta["caveats"])


def test_monte_carlo_carries_the_caveat_and_expectancy_interval(client):
    mc = client.post("/api/monte-carlo", json={"backtest_id": "BT-000001", "simulations": 200, "trades": 50}).json()
    assert "cannot tell you whether the underlying edge" in mc["caveat"]
    assert mc["summary"]["expectancy_ci95_low"] < mc["summary"]["expectancy_ci95_high"]


@pytest.mark.parametrize("model", ["random_walk", "structured"])
def test_data_model_is_recorded_on_every_experiment(client, model):
    cfg = {"strategy": "mnq_trend", "symbol": "MNQ", "start_date": "2023-01-02", "end_date": "2023-04-28",
           "data_model": model}
    r = client.post("/api/backtest/run", json={"config": cfg}).json()
    assert model in client.get("/api/experiments").json()[-1]["dataset"]
    client.delete(f"/api/backtests/{r['id']}")
