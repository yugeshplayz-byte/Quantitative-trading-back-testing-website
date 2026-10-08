"""Smoke + contract tests for every API group, run against the seeded demo database."""
import pytest

BT = "BT-000001"


def test_health_and_meta(client):
    assert client.get("/api/health").json()["status"] == "ok"
    meta = client.get("/api/meta").json()
    assert {i["symbol"] for i in meta["instruments"]} == {"MNQ", "NQ", "MES", "ES"}
    assert any(s["key"] == "mnq_trend" for s in meta["strategies"])
    assert meta["custom_code"]["enabled"] is False
    assert meta["data_source"]["kind"] == "synthetic"


def test_seeded_backtests_are_deterministic(client):
    rows = client.get("/api/backtests").json()
    assert [r["id"] for r in rows] == [f"BT-00000{i}" for i in range(1, 6)]
    first = client.get(f"/api/backtests/{BT}").json()
    again = client.get(f"/api/backtests/{BT}").json()
    assert first["metrics"] == again["metrics"]
    assert first["metrics"]["total_trades"] > 200


def test_dashboard_has_all_kpis(client):
    d = client.get(f"/api/backtests/{BT}/dashboard").json()
    for key in ["net_profit", "gross_profit", "gross_loss", "total_trades", "winning_trades", "losing_trades",
                "win_rate", "profit_factor", "expectancy", "average_winner", "average_loser", "win_loss_ratio",
                "sharpe", "sortino", "calmar", "recovery_factor", "max_drawdown", "max_drawdown_pct",
                "average_drawdown", "longest_drawdown_days", "max_consecutive_wins", "max_consecutive_losses",
                "largest_winner", "largest_loser", "average_holding_minutes", "total_fees", "slippage_cost"]:
        assert key in d["metrics"], key
    m = d["metrics"]
    assert m["net_profit"] == pytest.approx(m["gross_profit"] + m["gross_loss"])
    assert m["winning_trades"] + m["losing_trades"] <= m["total_trades"]
    assert len(d["equity"]) > 100 and d["recent_trades"] and d["health"]


def test_trades_filter_sort_page_csv(client):
    r = client.get(f"/api/backtests/{BT}/trades", params={"page_size": 10, "sort_by": "net_pnl", "sort_dir": "desc"}).json()
    assert len(r["rows"]) == 10 and r["rows"][0]["net_pnl"] >= r["rows"][1]["net_pnl"]
    win = client.get(f"/api/backtests/{BT}/trades", params={"result": "winner", "page_size": 5}).json()
    assert all(t["net_pnl"] > 0 for t in win["rows"])
    long = client.get(f"/api/backtests/{BT}/trades", params={"direction": "Long", "page_size": 5}).json()
    assert all(t["direction"] == "Long" for t in long["rows"]) and long["total"] < r["total"]
    tod = client.get(f"/api/backtests/{BT}/trades", params={"time_of_day": "10:00-11:00", "page_size": 5}).json()
    assert tod["total"] > 0
    csv = client.get(f"/api/backtests/{BT}/trades", params={"format": "csv"})
    assert csv.headers["content-type"].startswith("text/csv") and csv.text.splitlines()[0].startswith("id,symbol")
    assert len(csv.text.splitlines()) == r["total"] + 1


def test_trade_chart(client):
    t = client.get(f"/api/backtests/{BT}/trades", params={"page_size": 1}).json()["rows"][0]["id"]
    ch = client.get(f"/api/backtests/{BT}/trades/{t}/chart").json()
    assert len(ch["bars"]) > 10 and ch["levels"]["entry"] and ch["stop_path"]
    assert {"vwap", "ema9", "ema21"} <= set(ch["bars"][0])
    assert client.get(f"/api/backtests/{BT}/trades/T-999999/chart").status_code == 404


@pytest.mark.parametrize("kind", ["equity", "drawdowns", "calendar", "time", "long-short", "mfe-mae",
                                  "distributions", "streaks", "regimes", "volatility", "events", "performance"])
def test_analytics_sections(client, kind):
    r = client.get(f"/api/backtests/{BT}/analytics/{kind}")
    assert r.status_code == 200, r.text
    assert r.json()


def test_analytics_content(client):
    dd = client.get(f"/api/backtests/{BT}/analytics/drawdowns").json()
    assert 0 < len(dd["periods"]) <= 10 and dd["periods"][0]["depth"] >= dd["periods"][-1]["depth"]
    time = client.get(f"/api/backtests/{BT}/analytics/time").json()
    assert [r["label"] for r in time["time_of_day"]][0] == "9:30-10:00" and len(time["day_of_week"]) == 5
    mm = client.get(f"/api/backtests/{BT}/analytics/mfe-mae").json()
    assert mm["stats"]["avg_mfe"] is not None and mm["points"]
    dist = client.get(f"/api/backtests/{BT}/analytics/distributions").json()
    assert {"mean", "median", "std", "skew", "kurtosis", "p5", "p95"} <= set(dist["trade_pnl"]["stats"])
    reg = client.get(f"/api/backtests/{BT}/analytics/regimes").json()
    assert len(reg["rows"]) == 7 and len(reg["volatility"]) == 5
    assert {e["event"] for e in reg["events"]["rows"]} >= {"FOMC", "CPI", "NFP"}


def test_monte_carlo_endpoint_and_reproducibility(client):
    body = {"backtest_id": BT, "simulations": 500, "trades": 100, "seed": 3, "method": "block_bootstrap"}
    a, b = client.post("/api/monte-carlo", json=body).json(), client.post("/api/monte-carlo", json=body).json()
    assert a["summary"] == b["summary"]
    s = a["summary"]
    assert s["p5_ending_balance"] <= s["median_ending_balance"] <= s["p95_ending_balance"]
    assert 0 <= s["prob_ruin"] <= 1 and a["fan"]["p50"] and a["ending_hist"]["counts"]


def test_risk_of_ruin_endpoint(client):
    r = client.post("/api/risk-of-ruin", json={"win_rate": 0.45, "avg_win": 250, "avg_loss": 100}).json()
    assert 0 <= r["result"]["risk_of_ruin"] <= 1 and len(r["sensitivity"]) == 8


def test_stress_tests(client):
    s = client.post("/api/stress-test", json={"backtest_id": BT, "runs": 40}).json()
    assert [r["ticks"] for r in s["slippage"]] == [0, 1, 2, 3, 4, 5, 8]
    nets = [r["net_profit"] for r in s["slippage"]]
    assert nets == sorted(nets, reverse=True)  # more slippage never helps
    assert [r["multiplier"] for r in s["commission"]] == [1.0, 1.25, 1.5, 1.75, 2.0]
    assert [r["removed_pct"] for r in s["missed"]] == [1, 5, 10, 20]
    assert [r["label"] for r in s["outliers"]["rows"]][:2] == ["None", "Best trade"]
    # the "None" outlier row equals the baseline
    assert s["outliers"]["rows"][0]["net_profit"] == pytest.approx(s["baseline"]["net_profit"])


def test_prop_firm_endpoints(client):
    sim = client.post("/api/prop-firm/simulate", json={"backtest_id": BT}).json()
    assert sim["status"] in ("PASS", "FAIL", "ACTIVE") and sim["reason"] and sim["equity_path"]
    mc = client.post("/api/prop-firm/monte-carlo", json={"backtest_id": BT, "simulations": 400}).json()["summary"]
    assert mc["pass_probability"] + mc["fail_probability"] + mc["active_probability"] == pytest.approx(1.0)
    sv = client.post("/api/prop-firm/survival", json={"backtest_id": BT, "simulations": 300}).json()
    assert [m["calendar_days"] for m in sv["marks"]] == [30, 60, 90, 180, 365]
    po = client.post("/api/prop-firm/payouts", json={"backtest_id": BT, "simulations": 300, "horizon_days": 120}).json()
    assert po["prob_first_payout"] >= po["prob_second_payout"] >= po["prob_third_payout"]
    opt = client.post("/api/prop-firm/optimizer", json={"backtest_id": BT, "simulations": 300,
                                                          "risks": [75, 150, 300]}).json()
    assert len(opt["rows"]) == 3 and opt["best_risk"] in (75, 150, 300)
    assert len(client.get("/api/prop-firm/templates").json()) >= 3


def test_prop_rule_changes_outcome(client):
    loose = {"backtest_id": BT, "simulations": 300, "rules": {"max_drawdown": 10_000, "daily_loss_limit": None,
                                                              "consistency_pct": None}}
    tight = {"backtest_id": BT, "simulations": 300, "rules": {"max_drawdown": 500, "daily_loss_limit": 200}}
    a = client.post("/api/prop-firm/monte-carlo", json=loose).json()["summary"]
    b = client.post("/api/prop-firm/monte-carlo", json=tight).json()["summary"]
    assert b["fail_probability"] > a["fail_probability"]


def test_risk_endpoints(client):
    sz = client.post("/api/risk/position-size", json={"symbol": "MNQ", "risk_dollars": 200, "stop_points": 25}).json()
    assert sz["contracts"] == 4 and sz["risk_per_contract"] == 50  # 25 pts * $2
    cmp = client.post("/api/risk/sizing-comparison", json={"backtest_id": BT}).json()
    assert len(cmp["models"]) >= 3
    ls = client.get(f"/api/backtests/{BT}/losing-streaks").json()
    assert ls["longest"] >= 1 and ls["probabilities"]["rows"]


def test_optimization_and_walk_forward(client):
    opt = client.post("/api/optimization", json={"backtest_id": BT, "param_x": "fast", "param_y": "slow",
                                                  "x_values": [3, 5, 7], "y_values": [21, 26, 31],
                                                  "metric": "net_profit"}).json()
    assert len(opt["grid"]) == 3 and len(opt["grid"][0]) == 3 and opt["stability"]["classification"]
    wf = client.post("/api/walk-forward", json={"backtest_id": BT, "train_months": 6, "test_months": 3,
                                                 "step_months": 3, "x_values": [5, 9], "y_values": [21, 34]}).json()
    assert len(wf["windows"]) >= 3 and wf["aggregate"]["is"] and wf["aggregate"]["oos"]
    w = wf["windows"][0]
    assert w["train_end"] < w["test_start"]  # no overlap between train and test


def test_robustness_scores(client):
    r = client.get(f"/api/backtests/{BT}/robustness").json()
    assert 0 <= r["score"]["score"] <= 100 and r["overfitting"]["level"] in ("LOW", "MEDIUM", "HIGH")
    assert abs(sum(r["robustness"]["weights"].values()) - 1.0) < 1e-9
    assert r["warnings"] is not None and r["score"]["methodology"]
    d = client.get(f"/api/backtests/{BT}/dashboard").json()
    assert d["cached_score"]["grade"] == r["score"]["grade"]


def test_research_endpoints(client):
    cmp = client.post("/api/research/compare", json={"backtest_ids": ["BT-000001", "BT-000002"]}).json()
    assert len(cmp["rows"]) == 2 and cmp["rows"][0]["prop_pass_probability"] is not None
    comb = client.post("/api/research/combine", json={"weights": {"BT-000001": 60, "BT-000002": 40}}).json()
    assert comb["weights"]["BT-000001"] == pytest.approx(0.6) and comb["combined"]["max_drawdown"] >= 0
    for kind in ("returns", "daily_pnl", "drawdowns", "signals", "instruments"):
        c = client.post("/api/research/correlation", json={"backtest_ids": ["BT-000001", "BT-000003"], "kind": kind})
        assert c.status_code == 200, (kind, c.text)
        v = c.json()["values"]
        assert all(abs(v[i][i] - 1) < 1e-6 for i in range(len(v)))


def test_experiments_and_saved_strategies(client):
    up = client.patch(f"/api/experiments/{BT}", json={"name": "Renamed", "tags": ["x"], "favorite": True}).json()
    assert up["name"] == "Renamed" and up["favorite"] is True
    exps = client.get("/api/experiments").json()
    assert exps[0]["name"] == "Renamed" and exps[0]["git_commit"]
    strategies = client.get("/api/strategies").json()
    assert {s["name"] for s in strategies} >= {"MNQ Trend V1", "MES Mean Reversion", "Conservative Prop"}
    saved = client.post("/api/strategies", json={"name": "My preset", "config": strategies[0]["config"]}).json()
    assert client.delete(f"/api/strategies/{saved['id']}").json()["deleted"] == saved["id"]


def test_run_new_backtest_then_delete(client):
    cfg = {"strategy": "orb", "symbol": "MES", "start_date": "2023-01-02", "end_date": "2023-12-29"}
    r = client.post("/api/backtest/run", json={"config": cfg, "name": "Scratch ORB"})
    assert r.status_code == 200, r.text
    new_id = r.json()["id"]
    assert r.json()["metrics"]["total_trades"] > 0
    assert client.delete(f"/api/backtests/{new_id}").status_code == 200
    assert client.get(f"/api/backtests/{new_id}").status_code == 404


def test_report(client):
    rep = client.get(f"/api/backtests/{BT}/report").json()
    for key in ["summary", "performance", "monte_carlo", "walk_forward", "stress_tests", "score", "warnings"]:
        assert key in rep
    html = client.get(f"/api/backtests/{BT}/report.html")
    assert html.status_code == 200 and "<table" in html.text


def test_custom_code_disabled_by_default(client):
    assert client.post("/api/custom-strategies/validate", json={"name": "x", "code": "class Strategy: pass"}).status_code == 403
    assert client.get("/api/custom-strategies").status_code == 403
    cfg = {"strategy": "custom:1", "symbol": "MNQ"}
    assert client.post("/api/backtest/run", json={"config": cfg}).status_code == 403
    assert client.get("/api/custom-strategies/templates").status_code == 200  # templates are just text


def test_unknown_resources_404(client):
    assert client.get("/api/backtests/BT-009999").status_code == 404
    assert client.get(f"/api/backtests/{BT}/analytics/nope").status_code == 404
