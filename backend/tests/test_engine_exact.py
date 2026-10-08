"""Hand-computed engine scenarios (MNQ: tick 0.25, $0.50/tick, $2/point).

Cost model used in every expectation:
  fees      = (0.35 commission + 0.37 exchange) = $0.72 per contract per side
  slippage  = (1 tick + 0.5 spread/2 ticks) = 1.25 ticks = $0.625 per contract on every MARKET fill
              (entries, stops, end-of-day / signal exits); limit fills (target, partials) pay none.
Expected values are written out from these rules, not read back from the engine.
"""
import numpy as np
import pandas as pd
import pytest

from app.backtesting.engine import run_backtest
from app.backtesting.market import build_market_data
from app.backtesting.strategies import STRATEGIES
from app.backtesting.strategies.base import BaseStrategy, Signals
from app.models.config import (BacktestConfig, ExecutionConfig, ManagementConfig, RiskConfig, StopConfig,
                               TargetConfig, TradingConfig)

PV, FEE, SLIP = 2.0, 0.72, 0.625


class Scripted(BaseStrategy):
    key, name, parameters = "test_script", "scripted", []

    def __init__(self, longs=(), shorts=(), exit_long=(), exit_short=()):
        self.longs, self.shorts, self.xl, self.xs = set(longs), set(shorts), set(exit_long), set(exit_short)

    def compute_signals(self, md, params):
        n = len(md.c)
        side = [1 if i in self.longs else -1 if i in self.shorts else 0 for i in range(n)]
        return Signals(side=side, setup=["T" if s else "" for s in side], confidence=[50.0] * n,
                       exit_long=[i in self.xl for i in range(n)], exit_short=[i in self.xs for i in range(n)],
                       entry_reason={"T|1": "scripted long", "T|-1": "scripted short"}, exit_reason="Scripted exit")


def md_from(days: list[list[tuple]]):
    frames = []
    for d, rows in enumerate(days):
        n = len(rows)
        ts = pd.Timestamp(f"2023-03-{1 + d:02d} 09:30") + pd.to_timedelta(np.arange(n) * 5, unit="m")
        frames.append(pd.DataFrame({"ts": ts, "date": ts.date, "open": [r[0] for r in rows], "high": [r[1] for r in rows],
                                    "low": [r[2] for r in rows], "close": [r[3] for r in rows], "volume": 1000,
                                    "gen_regime": "x", "tod": np.arange(n) * 5, "day_id": d}))
    return build_market_data(pd.concat(frames, ignore_index=True), "MNQ", 0, "5m", "random_walk")


def run(monkeypatch, days, longs=(), shorts=(), xl=(), xs=(), **cfg_kw):
    monkeypatch.setitem(STRATEGIES, "test_script", Scripted(longs, shorts, xl, xs))
    cfg = BacktestConfig(
        strategy="test_script", symbol="MNQ", start_date="2023-03-01", end_date="2023-03-31",
        stop=cfg_kw.pop("stop", StopConfig(type="fixed_point", value=10)),
        target=cfg_kw.pop("target", TargetConfig(type="fixed_point", value=20)),
        risk=cfg_kw.pop("risk", RiskConfig(sizing_mode="fixed_contracts", contracts=1, daily_loss_limit=None,
                                          consecutive_loss_limit=None)),
        trading=cfg_kw.pop("trading", TradingConfig(max_trades_per_day=5, max_contracts=20)),
        execution=cfg_kw.pop("execution", ExecutionConfig()), **cfg_kw)
    md = md_from(days)
    return run_backtest(md, cfg, 0, len(md.c))


def flat(p, n):
    return [(p, p, p, p)] * n


def approx(x):
    return pytest.approx(x, abs=0.011)


# bars 0,1 are warm-up/signal; entry fills at bar 2's open
HEAD = [(100, 101, 99, 100), (100, 101, 99, 100)]


def test_long_target_exact(monkeypatch):
    day = HEAD + [(100, 105, 98, 104), (104, 125, 104, 120)] + flat(120, 3)
    (t,) = run(monkeypatch, [day], longs=[1])
    assert (t["direction"], t["entry_price"], t["exit_price"], t["exit_reason"]) == ("Long", 100.0, 120.0, "Target")
    assert t["gross_pnl"] == approx(40.0)  # (120-100) * 1 * $2
    assert t["fees"] == approx(2 * FEE) and t["slippage"] == approx(SLIP)  # entry slips, limit target does not
    assert t["net_pnl"] == approx(40 - 2 * FEE - SLIP)
    assert t["risk_dollars"] == approx(10 * PV) and t["r_multiple"] == pytest.approx(t["net_pnl"] / 20, abs=0.01)
    assert t["mae_points"] == pytest.approx(2.0) and t["mfe_points"] == pytest.approx(25.0)


def test_stop_beats_target_when_both_trade_in_one_bar(monkeypatch):
    day = HEAD + [(100, 105, 98, 104), (104, 125, 89, 120)] + flat(120, 3)
    (t,) = run(monkeypatch, [day], longs=[1])
    assert (t["exit_price"], t["exit_reason"]) == (90.0, "Stop loss")
    assert t["gross_pnl"] == approx(-20.0)
    assert t["slippage"] == approx(2 * SLIP)  # market entry + market stop
    assert t["net_pnl"] == approx(-20 - 2 * FEE - 2 * SLIP)


def test_gap_through_stop_fills_at_the_open_not_the_stop(monkeypatch):
    day = HEAD + [(100, 102, 99, 101), (85, 86, 84, 85)] + flat(85, 3)
    (t,) = run(monkeypatch, [day], longs=[1])
    assert t["exit_price"] == 85.0 and t["gross_pnl"] == approx(-30.0)


def test_touching_the_target_does_not_fill_but_trading_through_does(monkeypatch):
    day = HEAD + [(100, 105, 98, 104), (104, 120.0, 103, 119)] + flat(119, 2)
    (strict,) = run(monkeypatch, [day], longs=[1])  # high == target exactly: not filled by default
    assert strict["exit_reason"] == "End of day" and strict["exit_price"] == 119.0
    (touch,) = run(monkeypatch, [day], longs=[1], execution=ExecutionConfig(limit_through_ticks=0.0))
    assert touch["exit_reason"] == "Target" and touch["exit_price"] == 120.0
    day2 = HEAD + [(100, 105, 98, 104), (104, 120.25, 103, 119)] + flat(119, 2)
    (through,) = run(monkeypatch, [day2], longs=[1])  # one tick through: fills
    assert through["exit_reason"] == "Target"


def test_short_target_exact(monkeypatch):
    day = HEAD + [(100, 102, 95, 96), (96, 97, 79.75, 80)] + flat(80, 3)
    (t,) = run(monkeypatch, [day], shorts=[1])
    assert (t["direction"], t["exit_price"], t["exit_reason"]) == ("Short", 80.0, "Target")
    assert t["gross_pnl"] == approx(40.0) and t["net_pnl"] == approx(40 - 2 * FEE - SLIP)
    assert t["stop"] == 110.0 and t["target"] == 80.0


def test_end_of_day_exit_at_last_close_with_market_slippage(monkeypatch):
    day = HEAD + [(100, 103, 99, 102)] + [(102, 104, 101, 103)] * 2  # never reaches stop or target
    (t,) = run(monkeypatch, [day], longs=[1])
    assert t["exit_reason"] == "End of day" and t["exit_price"] == 103.0
    assert t["gross_pnl"] == approx(6.0) and t["slippage"] == approx(2 * SLIP)


def test_no_entry_is_taken_on_the_last_bar_or_across_days(monkeypatch):
    day = HEAD + flat(100, 3)
    assert run(monkeypatch, [day], longs=[len(day) - 1]) == []  # signal on the final bar of the day is dropped
    two = [HEAD + flat(100, 2), HEAD + flat(100, 2)]
    assert run(monkeypatch, two, longs=[3]) == []  # last bar of day 1 (index 3) cannot enter on day 2


def test_breakeven_moves_stop_to_entry_plus_one_tick(monkeypatch):
    mgmt = ManagementConfig(breakeven=True, breakeven_trigger_r=1.0)
    day = HEAD + [(100, 111, 99.5, 110), (110, 110.5, 100.0, 101)] + flat(101, 3)
    (t,) = run(monkeypatch, [day], longs=[1], management=mgmt)
    assert t["exit_reason"] == "Breakeven stop" and t["exit_price"] == 100.25
    assert t["gross_pnl"] == approx(0.5) and any(e["kind"] == "breakeven" for e in t["events"])


def test_partial_profit_then_target(monkeypatch):
    mgmt = ManagementConfig(partial_profit=True, partial_pct=0.5, partial_at_r=1.0)
    risk = RiskConfig(sizing_mode="fixed_contracts", contracts=2, daily_loss_limit=None, consecutive_loss_limit=None)
    day = HEAD + [(100, 110.25, 99, 110), (110, 125, 109, 120)] + flat(120, 3)
    (t,) = run(monkeypatch, [day], longs=[1], management=mgmt, risk=risk)
    assert t["gross_pnl"] == approx(20 + 40)  # 1 lot out at 110, last lot at 120
    assert t["fees"] == approx(4 * FEE)  # 2 contracts in, 2 out
    assert t["slippage"] == approx(2 * SLIP)  # only the two market entries pay slippage
    assert t["net_pnl"] == approx(60 - 4 * FEE - 2 * SLIP) and t["quantity"] == 2
    assert any(e["kind"] == "scale_out" for e in t["events"])


def test_scale_in_updates_average_price_and_costs(monkeypatch):
    mgmt = ManagementConfig(scale_in=True, scale_in_at_r=0.5)
    risk = RiskConfig(sizing_mode="fixed_contracts", contracts=2, daily_loss_limit=None, consecutive_loss_limit=None)
    day = HEAD + [(100, 106, 99, 105), (105, 125, 104, 120)] + flat(120, 3)
    (t,) = run(monkeypatch, [day], longs=[1], management=mgmt, risk=risk)
    avg = (100 * 2 + 105) / 3
    assert t["gross_pnl"] == approx((120 - avg) * 3 * PV)
    assert t["fees"] == approx(6 * FEE)  # 3 contracts in, 3 out
    assert t["slippage"] == approx(3 * SLIP)  # two initial + one added at market


def test_fixed_dollar_sizing_and_oversize_skip(monkeypatch):
    risk = RiskConfig(sizing_mode="fixed_dollar", risk_dollars=150, daily_loss_limit=None, consecutive_loss_limit=None)
    day = HEAD + [(100, 105, 98, 104), (104, 125, 104, 120)] + flat(120, 3)
    (t,) = run(monkeypatch, [day], longs=[1], risk=risk)  # $20 risk / contract -> floor(150/20) = 7
    assert t["quantity"] == 7
    big = run(monkeypatch, [day], longs=[1], risk=risk, stop=StopConfig(type="fixed_point", value=200))
    assert big == []  # one contract risks $400 > 2 x $150: skipped, never oversized
    ok = run(monkeypatch, [day], longs=[1], risk=risk, stop=StopConfig(type="fixed_point", value=100))
    assert ok and ok[0]["quantity"] == 1  # $200 <= $300: one contract, flagged as oversized by the optimiser


def test_daily_loss_limit_and_max_trades_halt_the_day(monkeypatch):
    lose = [(100, 101, 80, 85)]  # stop (90) hit
    day = HEAD + [(100, 101, 80, 85)] + flat(100, 2) + [(100, 101, 99, 100), (100, 101, 80, 85)] + flat(100, 2)
    risk = RiskConfig(sizing_mode="fixed_contracts", contracts=1, daily_loss_limit=15.0, consecutive_loss_limit=None)
    trades = run(monkeypatch, [day], longs=[1, 5], risk=risk)
    assert len(trades) == 1  # first loss (~$22) breaches the $15 limit; the second signal is ignored
    capped = run(monkeypatch, [day], longs=[1, 5], trading=TradingConfig(max_trades_per_day=1, max_contracts=20))
    assert len(capped) == 1
    assert len(run(monkeypatch, [day], longs=[1, 5])) == 2 and lose


def test_direction_toggles_and_entry_delay(monkeypatch):
    day = HEAD + [(100, 105, 98, 104), (104, 125, 104, 120)] + flat(120, 3)
    assert run(monkeypatch, [day], longs=[1], trading=TradingConfig(long_enabled=False)) == []
    delayed = HEAD + [(100, 101, 99, 100), (103, 105, 98, 104), (104, 125, 104, 120)] + flat(120, 2)
    (t,) = run(monkeypatch, [delayed], longs=[1], trading=TradingConfig(entry_delay_bars=1, max_trades_per_day=5, max_contracts=20))
    assert t["entry_price"] == 103.0  # filled one bar later than signal+1, at THAT bar's open


def test_signal_exit_fills_at_next_open_with_slippage(monkeypatch):
    day = HEAD + [(100, 103, 99, 102), (102, 104, 101, 103), (107, 108, 106, 107)] + flat(107, 2)
    (t,) = run(monkeypatch, [day], longs=[1], xl=[3])  # exit signal at bar 3's close -> exit at bar 4's open (107)
    assert t["exit_reason"] == "Scripted exit" and t["exit_price"] == 107.0
    assert t["gross_pnl"] == approx(14.0) and t["slippage"] == approx(2 * SLIP)


def test_costs_scale_with_quantity_and_zero_cost_gives_gross(monkeypatch):
    risk = RiskConfig(sizing_mode="fixed_contracts", contracts=3, daily_loss_limit=None, consecutive_loss_limit=None)
    day = HEAD + [(100, 105, 98, 104), (104, 125, 104, 120)] + flat(120, 3)
    (t,) = run(monkeypatch, [day], longs=[1], risk=risk)
    assert t["fees"] == approx(6 * FEE) and t["slippage"] == approx(3 * SLIP)
    free = ExecutionConfig(commission_per_side=0, exchange_fee_per_side=0, slippage_ticks=0, spread_ticks=0)
    (z,) = run(monkeypatch, [day], longs=[1], risk=risk, execution=free)
    assert z["net_pnl"] == z["gross_pnl"] == approx(120.0) and z["fees"] == 0 and z["slippage"] == 0
