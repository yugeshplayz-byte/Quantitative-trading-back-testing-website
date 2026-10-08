"""Walk-forward and grid search must not leak: selection uses TRAIN data only, OOS is unseen, results are reproducible."""
import math

import numpy as np
import pandas as pd
import pytest

from app.backtesting.market import get_market_data
from app.models.config import BacktestConfig
from app.optimization import grid as G
from app.optimization.walkforward import walk_forward

XS, YS = [5, 9], [21, 34]


def cfg(end="2024-12-31"):
    return BacktestConfig(strategy="mnq_trend", symbol="MNQ", start_date="2023-01-02", end_date=end)


@pytest.fixture(scope="module")
def wf():
    return walk_forward(cfg(), 6, 3, 3, "sharpe", "fast", "slow", XS, YS)


def test_windows_never_overlap_train_and_test(wf):
    assert len(wf["windows"]) >= 4
    for w in wf["windows"]:
        assert w["train_start"] < w["train_end"] < w["test_start"] < w["test_end"]
        assert (pd.Timestamp(w["test_start"]) - pd.Timestamp(w["train_end"])).days == 1  # test begins right after train


def test_selected_parameters_are_the_argmax_on_the_training_window_only(wf):
    c = cfg()
    md = get_market_data("MNQ", 42, "5m", "random_walk")
    for w in wf["windows"]:
        lo, hi = md.index_range(w["train_start"], w["train_end"])
        scores = {}
        for x in XS:
            for y in YS:
                m = G.run_metrics(G.apply_param(G.apply_param(c, "fast", x), "slow", y), lo, hi)
                v = G.metric_value(m, "sharpe")
                if math.isfinite(v):
                    scores[(x, y)] = v
        best = max(scores, key=scores.get)
        assert (w["params"]["fast"], w["params"]["slow"]) == best


def test_oos_metrics_equal_a_clean_rerun_of_the_chosen_parameters(wf):
    c = cfg()
    md = get_market_data("MNQ", 42, "5m", "random_walk")
    for w in wf["windows"][:3]:
        lo, hi = md.index_range(w["test_start"], w["test_end"])
        run = G.run_metrics(G.apply_param(G.apply_param(c, "fast", w["params"]["fast"]), "slow", w["params"]["slow"]), lo, hi)
        assert w["oos_metrics"]["net_profit"] == pytest.approx(run["net_profit"], abs=0.01)
        assert w["oos_metrics"]["trades"] == run["trades"]


def test_stitched_oos_curve_covers_only_test_periods_once(wf):
    dates = [pd.Timestamp(p["date"]).date() for p in wf["oos_curve"]]
    assert len(dates) == len(set(dates)) and dates == sorted(dates)
    first, last = pd.Timestamp(wf["windows"][0]["test_start"]).date(), pd.Timestamp(wf["windows"][-1]["test_end"]).date()
    assert min(dates) >= first and max(dates) <= last


def test_results_do_not_depend_on_data_after_the_window():
    """Re-running with an earlier overall end date must give identical results for windows that fit in both."""
    full = walk_forward(cfg("2024-12-31"), 6, 3, 3, "sharpe", "fast", "slow", XS, YS)
    short = walk_forward(cfg("2024-06-30"), 6, 3, 3, "sharpe", "fast", "slow", XS, YS)
    common = {(w["test_start"], w["test_end"]): w for w in short["windows"]}
    matched = 0
    for w in full["windows"]:
        s = common.get((w["test_start"], w["test_end"]))
        if s:
            matched += 1
            assert s["params"] == w["params"] and s["oos_metrics"] == w["oos_metrics"] and s["is_metrics"] == w["is_metrics"]
    assert matched >= 2


def test_grid_best_cell_is_the_true_extreme_and_flags_selection_bias():
    res = G.optimise(cfg("2023-12-31"), "fast", "slow", "net_profit", XS + [13], YS + [50])
    z = np.array(res["grid"], dtype=float)
    assert res["best"]["value"] == pytest.approx(np.nanmax(z))
    assert res["selection_bias"]["cells_tested"] == int(np.isfinite(z).sum())
    assert res["selection_bias"]["expected_best_sharpe_if_no_edge"] > 0 and "IN-SAMPLE" in res["selection_bias"]["note"]
    lowdd = G.optimise(cfg("2023-12-31"), "fast", "slow", "max_drawdown", XS, YS)
    zz = np.array(lowdd["grid"], dtype=float)
    assert lowdd["best"]["value"] == pytest.approx(np.nanmin(zz))  # drawdown: lower is better
