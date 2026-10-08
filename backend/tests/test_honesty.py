"""The platform must give honest answers: no edge in noise, edge detected where one is engineered,
costs always hurt, and conservative fill rules stay conservative."""
import numpy as np
import pandas as pd
import pytest

from app.backtesting.engine import run_backtest
from app.backtesting.market import get_market_data
from app.models.config import BacktestConfig, ExecutionConfig
from app.quant import metrics as M

STRATS = [("mnq_trend", "MNQ"), ("mes_mean_reversion", "MES"), ("orb", "MNQ")]


def run(strategy, symbol, seed=42, model="random_walk", **kw):
    cfg = BacktestConfig(strategy=strategy, symbol=symbol, seed=seed, data_model=model,
                         start_date="2023-01-02", end_date="2024-06-28", **kw)
    md = get_market_data(symbol, seed, cfg.timeframe, model)
    return cfg, run_backtest(md, cfg)


def test_random_walk_has_no_serial_correlation():
    md = get_market_data("MNQ", 42, "5m", "random_walk")
    c = md.df["close"]
    r = np.log(c).diff().dropna()
    r = r[md.df["tod"].iloc[1:] != 0]  # drop overnight gaps
    assert abs(r.autocorr(1)) < 0.03
    daily = np.log(c.groupby(md.df["day_id"]).last()).diff().dropna()
    assert abs(daily.mean() / daily.std() * np.sqrt(len(daily))) < 3.5  # no meaningful drift


def test_strategies_have_no_gross_edge_on_random_walk():
    pooled_gross, pooled_net, n_profitable, n_runs = [], [], 0, 0
    for seed in (1, 2, 3):
        for key, sym in STRATS:
            _, trades = run(key, sym, seed)
            df = pd.DataFrame(trades)
            pooled_gross += df["gross_pnl"].tolist()
            pooled_net += df["net_pnl"].tolist()
            n_profitable += int(df["net_pnl"].sum() > 0)
            n_runs += 1
    gross = np.array(pooled_gross)
    t_gross = gross.mean() / (gross.std(ddof=1) / np.sqrt(len(gross)))
    assert abs(t_gross) < 3.0, f"gross P&L looks non-random on a random walk (t={t_gross:.2f})"
    assert np.mean(pooled_net) < 0  # costs make a no-edge strategy lose on average
    assert n_profitable <= n_runs // 3


def test_engineered_market_is_detectable():
    """On the engineered-edge market the same untuned trend strategy has a clearly better gross result."""
    rw = pd.DataFrame(run("mnq_trend", "MNQ", 42, "random_walk")[1])
    st = pd.DataFrame(run("mnq_trend", "MNQ", 42, "structured")[1])
    assert st["gross_pnl"].sum() > rw["gross_pnl"].sum()
    assert st["gross_pnl"].sum() > 0


@pytest.mark.parametrize("key,sym", STRATS)
def test_more_costs_never_help(key, sym):
    base = pd.DataFrame(run(key, sym)[1])["net_pnl"].sum()
    harsh = pd.DataFrame(run(key, sym, execution=ExecutionConfig(slippage_ticks=3, commission_per_side=1.0))[1])["net_pnl"].sum()
    assert harsh < base


def test_limit_fills_require_trading_through_the_target():
    _, strict = run("mnq_trend", "MNQ", execution=ExecutionConfig(limit_through_ticks=1.0))
    _, touch = run("mnq_trend", "MNQ", execution=ExecutionConfig(limit_through_ticks=0.0))
    n_strict = sum(t["exit_reason"] == "Target" for t in strict)
    n_touch = sum(t["exit_reason"] == "Target" for t in touch)
    assert n_strict < n_touch  # touch-fills are optimistic: they hand out more winners


def test_gross_minus_costs_equals_net():
    _, trades = run("mnq_trend", "MNQ")
    for t in trades[:200]:
        assert t["net_pnl"] == pytest.approx(t["gross_pnl"] - t["fees"] - t["slippage"], abs=0.02)
        assert t["fees"] > 0 and t["slippage"] > 0


def test_headline_drawdown_is_at_least_the_daily_drawdown():
    from app.backtesting.runner import days_between, trades_frame

    cfg, trades = run("mnq_trend", "MNQ")
    md = get_market_data("MNQ", 42, "5m", "random_walk")
    lo, hi = md.index_range(cfg.start_date, cfg.end_date)
    tdf = trades_frame([{**t, "id": f"T-{i:06d}"} for i, t in enumerate(trades, 1)])
    m = M.compute_metrics(tdf, M.daily_frame(tdf, days_between(md, lo, hi), cfg.starting_balance), cfg.starting_balance)
    assert m["max_drawdown"] >= m["max_drawdown_daily"] - 1e-6
    assert m["expectancy_pvalue"] is not None and 0 <= m["expectancy_pvalue"] <= 1


def test_no_edge_warning_fires_for_losing_strategy(client):
    # BT-000001..4 run on the random walk: any with negative expectancy must be flagged as having no edge
    rows = client.get("/api/backtests").json()
    flagged = 0
    for r in rows:
        if "validation" in r["tags"]:
            continue
        dash = client.get(f"/api/backtests/{r['id']}/dashboard").json()
        losing = r["metrics"]["expectancy"] <= 0
        codes = {w["code"] for w in dash["warnings"]}
        assert ("no_edge" in codes) == losing or "significance" in codes
        flagged += losing
    assert flagged >= 1  # at least one random-walk demo strategy loses money, honestly reported
