import numpy as np
import pytest

from app.models.simulation import MonteCarloConfig
from app.quant.monte_carlo import longest_losing_streak, run_monte_carlo
from app.quant.ruin import risk_of_ruin

PNL = np.array([120.0, -60.0, 90.0, -60.0, 200.0, -80.0, 45.0, -60.0, 150.0, -70.0] * 5)


def cfg(**kw):
    base = dict(simulations=300, trades=60, seed=123, method="bootstrap")
    base.update(kw)
    return MonteCarloConfig(**base)


@pytest.mark.parametrize("method", ["shuffle", "bootstrap", "block_bootstrap"])
def test_reproducible_for_same_seed(method):
    a = run_monte_carlo(PNL, 60.0, cfg(method=method))
    b = run_monte_carlo(PNL, 60.0, cfg(method=method))
    assert a["summary"] == b["summary"]
    assert a["fan"]["p50"] == b["fan"]["p50"]


def test_different_seed_changes_result():
    a = run_monte_carlo(PNL, 60.0, cfg(seed=1))
    b = run_monte_carlo(PNL, 60.0, cfg(seed=2))
    assert a["summary"]["median_ending_balance"] != b["summary"]["median_ending_balance"]


def test_shuffle_preserves_total_pnl():
    # a full reshuffle of every historical trade always ends at the same balance
    res = run_monte_carlo(PNL, 60.0, cfg(method="shuffle", trades=len(PNL)))
    s = res["summary"]
    assert s["p5_ending_balance"] == pytest.approx(50_000 + PNL.sum())
    assert s["p95_ending_balance"] == pytest.approx(50_000 + PNL.sum())


def test_risk_scale_changes_dispersion():
    base = run_monte_carlo(PNL, 60.0, cfg())
    dbl = run_monte_carlo(PNL, 60.0, cfg(risk_per_trade=120.0))
    assert dbl["summary"]["risk_scale"] == 2.0
    assert dbl["summary"]["median_max_drawdown"] > base["summary"]["median_max_drawdown"]


def test_longest_losing_streak_vectorised():
    x = np.array([[1, -1, -1, -1, 2, -1], [-1, -1, 1, -1, -1, -1]], dtype=float)
    assert longest_losing_streak(x).tolist() == [3, 3]


def test_risk_of_ruin_monotonic_and_bounded():
    safe = risk_of_ruin(50_000, 2_500, None, 0.5, 200, 100, 200)
    risky = risk_of_ruin(50_000, 2_500, 400, 0.5, 200, 100, 200)
    for r in (safe, risky):
        assert 0 <= r["risk_of_ruin"] <= 1 and 0 <= r["drawdown_probability"] <= 1
        assert r["survival_probability"] == pytest.approx(1 - r["drawdown_probability"])
    assert risky["risk_of_ruin"] > safe["risk_of_ruin"]


def test_risk_of_ruin_negative_edge_is_certain():
    r = risk_of_ruin(50_000, 2_500, None, 0.3, 100, 100, 200)
    assert r["risk_of_ruin"] == 1.0
