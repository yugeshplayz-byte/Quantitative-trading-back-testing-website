import pytest

from app.quant.readiness import readiness

GOOD = dict(data_model="real", trades=450, expectancy=18.0, pvalue=0.004, ci_low=6.0, base_net=8000, slip2_net=5200,
            comm15_net=7000, wf_windows=8, wf_consistency=0.75, wf_oos_net=3100, outlier_top1_net=5500,
            outlier_top5_net=2100, top10_share=0.22, stability_class="broad plateau", custom=False, lookahead=None,
            max_dd_pct=0.11, months=24, regimes_covered=7, trials=3)


def status(r, cid):
    return next(c["status"] for c in r["checks"] if c["id"] == cid)


def test_all_good_is_only_ever_a_paper_trade_candidate():
    r = readiness(GOOD)
    assert r["verdict"] == "PAPER_TRADE_CANDIDATE" and r["blocking_failures"] == 0
    assert "PAPER TRADING" in r["headline"] and "not proof" in r["headline"]
    assert "READY" not in r["verdict"].replace("NOT_READY", "")  # there is no "ready to deploy" verdict at all
    assert len(r["next_steps"]) >= 3


def test_synthetic_data_can_never_pass():
    r = readiness({**GOOD, "data_model": "random_walk"})
    assert r["verdict"] == "NOT_READY" and status(r, "real_data") == "fail"
    assert readiness({**GOOD, "data_model": "structured"})["verdict"] == "NOT_READY"


@pytest.mark.parametrize("patch,check", [
    ({"trades": 60}, "trades"),
    ({"expectancy": -1.0}, "expectancy"),
    ({"pvalue": 0.3, "ci_low": -4.0}, "significance"),
    ({"pvalue": 0.01, "ci_low": -0.5}, "significance"),  # small p but interval still includes zero
    ({"slip2_net": -200}, "costs"),
    ({"comm15_net": -50}, "costs"),
    ({"wf_consistency": 0.4}, "walk_forward"),
    ({"wf_oos_net": -100}, "walk_forward"),
    ({"outlier_top1_net": -10}, "outliers"),
    ({"top10_share": 0.6}, "outliers"),
    ({"stability_class": "sharp peak"}, "stability"),
    ({"max_dd_pct": 0.5}, "drawdown"),
    ({"months": 3}, "history"),
    ({"custom": True, "lookahead": {"status": "suspect", "message": "leak"}}, "lookahead"),
])
def test_each_blocking_check_can_fail_the_verdict(patch, check):
    r = readiness({**GOOD, **patch})
    assert status(r, check) == "fail" and r["verdict"] == "NOT_READY" and r["blocking_failures"] >= 1


@pytest.mark.parametrize("patch,check", [
    ({"trades": 150}, "trades"), ({"max_dd_pct": 0.25}, "drawdown"), ({"outlier_top5_net": -5}, "outliers"),
    ({"stability_class": "moderate"}, "stability"), ({"months": 9}, "history"), ({"trials": 60}, "multiple_testing"),
    ({"wf_windows": 2}, "walk_forward"), ({"custom": True, "lookahead": None}, "lookahead"),
])
def test_soft_issues_warn_but_do_not_block(patch, check):
    r = readiness({**GOOD, **patch})
    assert status(r, check) == "warn" and r["verdict"] == "PAPER_TRADE_CANDIDATE" and r["warnings"] >= 1


def test_multiple_testing_adjusted_pvalue():
    r = readiness({**GOOD, "pvalue": 0.01, "trials": 30})
    assert r["adjusted_pvalue"] == pytest.approx(0.3)


def test_seeded_demo_backtests_are_not_ready_and_say_why(client):
    r = client.get("/api/backtests/BT-000001/robustness").json()["readiness"]
    assert r["verdict"] == "NOT_READY"
    reasons = {c["id"] for c in r["checks"] if c["status"] == "fail"}
    assert "real_data" in reasons and "expectancy" in reasons  # synthetic AND losing: both reported
    assert client.get("/api/backtests/BT-000001/dashboard").json()["cached_score"]["readiness"] == "NOT_READY"
    assert "Deployment readiness" in client.get("/api/backtests/BT-000001/report.html").text
