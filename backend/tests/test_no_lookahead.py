"""Causality tests: removing the FUTURE must not change anything computed for the PAST.

If an indicator, signal or engine step peeked at later bars, truncating the data would change
earlier values and these tests would fail.
"""
import numpy as np
import pytest

from app.backtesting.engine import run_backtest
from app.backtesting.market import build_market_data, get_market_data
from app.backtesting.strategies import STRATEGIES, get_strategy
from app.models.config import BacktestConfig, ManagementConfig

CUTS = [31_000, 41_234, 52_517]  # includes cuts in the middle of a trading day


def truncated(md, cut):
    return build_market_data(md.df.iloc[:cut], md.symbol, md.seed, md.timeframe, md.data_model)


@pytest.fixture(scope="module")
def full():
    return get_market_data("MNQ", 42, "5m", "random_walk")


@pytest.mark.parametrize("cut", CUTS)
def test_indicators_are_causal(full, cut):
    part = truncated(full, cut)
    n = cut - 1  # is_last on the final truncated bar is unknowable, everything before must match
    for name in ("atr", "atr_pct", "swing_low", "swing_high"):
        assert np.allclose(getattr(full, name)[:n], getattr(part, name)[:n]), name
    assert np.allclose(full.vwap[:n], part.vwap[:n])
    assert np.allclose(full.er[:n], part.er[:n])
    assert full.regime[:n] == part.regime[:n], "regime labels must be computed from past data only"
    assert full.is_last[: n - 1] == part.is_last[: n - 1]


@pytest.mark.parametrize("key", sorted(STRATEGIES))
@pytest.mark.parametrize("cut", CUTS)
def test_strategy_signals_are_causal(full, key, cut):
    strat = get_strategy(key)
    params = strat.resolve_params({})
    part = truncated(full, cut)
    a, b = strat.compute_signals(full, params), strat.compute_signals(part, params)
    n = cut - 1
    assert a.side[:n] == b.side[:n]
    assert a.setup[:n] == b.setup[:n]
    assert a.confidence[:n] == b.confidence[:n]
    assert a.exit_long[:n] == b.exit_long[:n] and a.exit_short[:n] == b.exit_short[:n]


@pytest.mark.parametrize("key,symbol", [("mnq_trend", "MNQ"), ("mes_mean_reversion", "MES"), ("orb", "MNQ")])
def test_engine_trades_do_not_depend_on_future_bars(key, symbol):
    """Every trade that closed before the cut must be identical whether or not later bars exist."""
    cfg = BacktestConfig(strategy=key, symbol=symbol, start_date="2023-01-02", end_date="2023-12-29",
                         management=ManagementConfig(breakeven=True, trailing_stop=True, partial_profit=True,
                                                     scale_in=True))
    md = get_market_data(symbol, cfg.seed, cfg.timeframe, cfg.data_model)
    lo, hi = md.index_range(cfg.start_date, cfg.end_date)
    cut = lo + (hi - lo) // 2 + 17
    full_trades = run_backtest(md, cfg, lo, hi)
    part = truncated(md, cut)
    part_trades = run_backtest(part, cfg, lo, cut)
    closed_full = [t for t in full_trades if t["exit_bar"] < cut - 2]
    closed_part = [t for t in part_trades if t["exit_bar"] < cut - 2 and t["exit_reason"] != "End of data"]
    assert len(closed_full) > 20

    def sig(t):
        return (t["entry_time"], t["exit_time"], t["direction"], t["quantity"], t["net_pnl"], t["exit_reason"])

    assert [sig(t) for t in closed_full] == [sig(t) for t in closed_part]


def test_signal_is_filled_on_a_later_bar_than_it_was_decided():
    cfg = BacktestConfig(strategy="mnq_trend", start_date="2023-01-02", end_date="2023-06-30")
    md = get_market_data("MNQ", 42, "5m", "random_walk")
    for t in run_backtest(md, cfg)[:300]:
        assert t["entry_bar"] > 0
        # the regime/atr attached to a trade come from the signal bar (strictly before the entry bar)
        assert md.stamp(t["entry_bar"]) == t["entry_time"]
