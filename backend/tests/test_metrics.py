"""Deterministic checks of the core statistics (expected values worked out by hand)."""
import math

import numpy as np

from app.quant import metrics as M


PNL = np.array([100.0, -50.0, 200.0, -100.0, 50.0])


def test_profit_factor():
    # gross profit 350, gross loss 150
    assert math.isclose(M.profit_factor(PNL), 350 / 150)


def test_profit_factor_edge_cases():
    assert M.profit_factor(np.array([10.0, 20.0])) == math.inf
    assert M.profit_factor(np.array([])) == 0.0
    assert M.profit_factor(np.array([-5.0, -5.0])) == 0.0


def test_expectancy_and_averages():
    assert math.isclose(M.expectancy(PNL), 40.0)
    assert math.isclose(M.average_winner(PNL), 350 / 3)
    assert math.isclose(M.average_loser(PNL), -75.0)
    assert math.isclose(M.win_rate(PNL), 0.6)
    assert M.gross_profit(PNL) == 350 and M.gross_loss(PNL) == -150


def test_sharpe_ratio():
    r = np.array([0.01, -0.01, 0.02, 0.0])
    # mean 0.005, sample variance 5e-4/3
    expected = 0.005 / math.sqrt(5e-4 / 3) * math.sqrt(252)
    assert math.isclose(M.sharpe_ratio(r), expected, rel_tol=1e-9)


def test_sharpe_zero_variance():
    assert M.sharpe_ratio(np.array([0.01, 0.01, 0.01])) == 0.0


def test_sortino_ratio():
    r = np.array([0.01, -0.01, 0.02, 0.0])
    # downside deviation = sqrt(mean([0, 1e-4, 0, 0])) = 0.005 ; mean excess = 0.005
    assert math.isclose(M.sortino_ratio(r), math.sqrt(252), rel_tol=1e-9)


def test_max_drawdown():
    eq = np.array([100, 120, 90, 110, 80, 130], dtype=float)
    dd, pct = M.max_drawdown(eq)
    assert dd == 40.0
    assert math.isclose(pct, 40 / 120)


def test_drawdown_periods():
    from datetime import date, timedelta
    d0 = date(2024, 1, 1)
    dates = [d0 + timedelta(days=i) for i in range(6)]
    eq = np.array([105, 110, 100, 95, 112, 112], dtype=float)
    periods = M.drawdown_periods(dates, eq, 100.0)
    assert len(periods) == 1
    p = periods[0]
    assert p["depth"] == 15.0 and p["start"] == dates[1] and p["bottom"] == dates[3]
    assert p["recovery"] == dates[4] and p["recovery_days"] == 1 and p["duration_days"] == 3


def test_losing_and_winning_streaks():
    pnl = [1, -1, -1, -1, 2, -1, -1]
    assert M.max_consecutive(pnl, winners=False) == 3
    assert M.streak_lengths(pnl, winners=False) == [3, 2]
    assert M.max_consecutive([1, 1, -1, 1, 1, 1], winners=True) == 3
    assert M.max_consecutive([], winners=False) == 0
