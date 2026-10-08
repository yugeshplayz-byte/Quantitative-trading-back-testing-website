"""Bar-by-bar futures backtest engine.

Execution model (documented in docs/QUANT_ASSUMPTIONS.md):
* Signals are decided at a bar's close and filled at the NEXT bar's open (plus optional delay).
* One position at a time. Stops are resting orders; if a bar trades through both the stop and
  the target, the STOP is assumed to fill first (conservative).
* Gaps: if a bar opens beyond the stop, the fill is the open (not the stop price).
* Slippage + half the spread are charged on every market-type fill (entries, stops, signal and
  end-of-day exits). Limit fills (targets, partials) pay no slippage.
* Fees = (commission + exchange fee) per contract per side.
* Trade P&L: gross (price move x point value), minus fees, minus slippage = net.
* MAE/MFE are measured against the initial entry using bar highs/lows and expressed in $ for the
  initial quantity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..models.config import BacktestConfig
from .instruments import get_instrument
from .market import MarketData
from .strategies import get_strategy
from .strategies.base import Signals

MAX_EVENTS = 14


@dataclass
class _Pos:
    d: int  # +1 / -1
    entry_bar: int
    signal_bar: int
    entry: float  # initial entry price
    avg: float  # average entry price
    qty: int
    init_qty: int
    entered_qty: int
    stop: float
    stop_pts: float
    target: float | None
    atr: float
    setup: str
    conf: float
    atr_pct: float
    reason: str
    best: float  # most favourable price seen
    worst: float
    gross: float = 0.0
    fees: float = 0.0
    slip: float = 0.0
    exit_value: float = 0.0  # sum(exit_px * qty) for avg exit
    exited_qty: int = 0
    partial_done: bool = False
    scale_out_done: bool = False
    scale_in_done: bool = False
    be_done: bool = False
    trailed: bool = False
    risk_dollars: float = 0.0
    events: list = field(default_factory=list)


def _round_tick(x: float, tick: float, up: bool = False) -> float:
    n = x / tick
    return (math.ceil(n - 1e-9) if up else round(n)) * tick


def run_backtest(
    md: MarketData,
    cfg: BacktestConfig,
    lo: int | None = None,
    hi: int | None = None,
    start_equity: float | None = None,
) -> list[dict]:
    """Run one backtest and return trades (dicts compatible with `models.Trade`, without ids)."""
    strat = get_strategy(cfg.strategy)
    params = strat.resolve_params(cfg.params)
    cfg_lo, cfg_hi = md.index_range(cfg.start_date, cfg.end_date)
    sig: Signals = strat.signals(md, params, cfg_lo)  # models may train on bars before cfg_lo only
    if lo is None or hi is None:
        lo, hi = cfg_lo, cfg_hi
    inst = get_instrument(cfg.symbol)
    tick, tv, pv = inst.tick_size, inst.tick_value, inst.point_value
    ex, risk, trd = cfg.execution, cfg.risk, cfg.trading
    fee_side = ex.commission_per_side + ex.exchange_fee_per_side
    mkt_ticks = ex.slippage_ticks + ex.spread_ticks / 2.0
    latency_ticks = ex.latency_ms / 500.0
    bar_min = md.bar_minutes
    mg = cfg.management

    o, h, l, c = md.o, md.h, md.l, md.c
    day_id, is_last, atr_a = md.day_id, md.is_last, md.atr
    side_a, setup_a, conf_a = sig.side, sig.setup, sig.confidence
    exit_l, exit_s = sig.exit_long, sig.exit_short

    equity = start_equity if start_equity is not None else cfg.starting_balance
    peak = equity
    kill = False
    trades: list[dict] = []

    pos: _Pos | None = None
    pend: tuple | None = None  # (exec_bar, side, signal_bar, stop_pts, target_pts, atr)
    pend_exit_bar = -1
    cur_day = -1
    day_pnl, day_trades, consec_losses, day_halt = 0.0, 0, 0, False

    def stop_distance(i: int, d: int) -> float:
        a = atr_a[i]
        st = cfg.stop
        if st.type == "fixed_point":
            pts = st.value
        elif st.type == "fixed_dollar":
            pts = st.value / pv
        elif st.type == "atr":
            pts = st.value * a
        else:  # structure: beyond the recent swing, buffer in ticks
            ref = c[i]
            if d > 0:
                pts = ref - md.swing_low[i] + st.value * tick
            else:
                pts = md.swing_high[i] - ref + st.value * tick
            pts = min(max(pts, 0.5 * a), 4.0 * a)
        return max(_round_tick(pts, tick, up=True), 2 * tick)

    def target_distance(stop_pts: float, a: float) -> float | None:
        tg = cfg.target
        if tg.type == "fixed_point":
            pts = tg.value
        elif tg.type == "risk_reward":
            pts = tg.value * stop_pts
        else:
            pts = tg.value * a
        return max(_round_tick(pts, tick), tick)

    def position_size(stop_pts: float) -> int:
        per_contract = stop_pts * pv
        if risk.sizing_mode == "fixed_contracts":
            q = risk.contracts
        else:
            budget = risk.risk_dollars if risk.sizing_mode == "fixed_dollar" else equity * risk.risk_pct / 100.0
            if per_contract > 2.0 * budget:
                return 0  # one contract risks more than twice the budget: skip
            q = int(budget // per_contract)
        return max(0, min(max(q, 1), trd.max_contracts))

    def close_leg(p: _Pos, px: float, q: int, market: bool) -> None:
        p.gross += (px - p.avg) * p.d * q * pv
        p.fees += fee_side * q
        if market:
            p.slip += mkt_ticks * tv * q
        p.exit_value += px * q
        p.exited_qty += q
        p.qty -= q

    def finalize(p: _Pos, exit_bar: int, reason: str, offset_min: float) -> None:
        nonlocal equity, peak, day_pnl, day_trades, consec_losses, day_halt, kill, pos
        # entry-side fees for every contract ever entered
        p.fees += fee_side * p.entered_qty
        net = p.gross - p.fees - p.slip
        avg_exit = p.exit_value / max(p.exited_qty, 1)
        tstart = md.stamp(p.entry_bar)
        tend = md.stamp(exit_bar, offset_min)
        dur = (exit_bar - p.entry_bar) * bar_min + offset_min
        if p.d > 0:
            mae_pts = max(0.0, p.entry - p.worst)
            mfe_pts = max(0.0, p.best - p.entry)
        else:
            mae_pts = max(0.0, p.worst - p.entry)
            mfe_pts = max(0.0, p.entry - p.best)
        trades.append(
            {
                "symbol": cfg.symbol,
                "date": md.df["date"].iat[p.entry_bar],
                "entry_time": tstart,
                "exit_time": tend,
                "direction": "Long" if p.d > 0 else "Short",
                "entry_price": round(p.entry, 2),
                "exit_price": round(avg_exit, 2),
                "quantity": p.init_qty,
                "stop": round(p.entry - p.d * p.stop_pts, 2),
                "target": None if p.target is None else round(p.target, 2),
                "gross_pnl": round(p.gross, 2),
                "fees": round(p.fees, 2),
                "slippage": round(p.slip, 2),
                "net_pnl": round(net, 2),
                "r_multiple": round(net / p.risk_dollars, 3) if p.risk_dollars > 0 else 0.0,
                "risk_dollars": round(p.risk_dollars, 2),
                "mae": round(mae_pts * pv * p.init_qty, 2),
                "mfe": round(mfe_pts * pv * p.init_qty, 2),
                "mae_points": round(mae_pts, 2),
                "mfe_points": round(mfe_pts, 2),
                "duration_minutes": round(max(dur, 1.0), 1),
                "regime": md.regime[p.entry_bar],
                "setup": p.setup,
                "confidence": p.conf,
                "atr_percentile": round(p.atr_pct, 1),
                "entry_reason": p.reason,
                "exit_reason": reason,
                "entry_bar": p.entry_bar,
                "exit_bar": exit_bar,
                "events": p.events,
            }
        )
        equity += net
        peak = max(peak, equity)
        day_pnl += net
        day_trades += 1
        consec_losses = consec_losses + 1 if net < 0 else 0
        if risk.daily_loss_limit and day_pnl <= -risk.daily_loss_limit:
            day_halt = True
        if risk.consecutive_loss_limit and consec_losses >= risk.consecutive_loss_limit:
            day_halt = True
        if risk.max_drawdown and (peak - equity) >= risk.max_drawdown:
            kill = True
        pos = None

    def event(p: _Pos, i: int, kind: str, price: float, q: int = 0) -> None:
        if len(p.events) < MAX_EVENTS or kind != "trail":
            p.events.append({"time": md.stamp(i), "price": round(price, 2), "kind": kind, "quantity": q})

    for i in range(lo, hi):
        d_id = day_id[i]
        if d_id != cur_day:
            cur_day, day_pnl, day_trades, consec_losses, day_halt = d_id, 0.0, 0, 0, False
            pend, pend_exit_bar = None, -1

        # 1) signal-based exit at this open
        if pos is not None and pend_exit_bar == i:
            close_leg(pos, o[i], pos.qty, True)
            finalize(pos, i, sig.exit_reason, 0.0)
            pend_exit_bar = -1

        entered_now = False
        # 2) pending entry at this open
        if pos is None and pend is not None and pend[0] == i:
            _, d, sbar, stop_pts, tgt_pts, a = pend
            pend = None
            ok = (
                not kill
                and not day_halt
                and day_trades < trd.max_trades_per_day
                and ((d > 0 and trd.long_enabled) or (d < 0 and trd.short_enabled))
            )
            q = position_size(stop_pts) if ok else 0
            if q > 0:
                entry_px = o[i]
                st_px = entry_px - d * stop_pts
                tg_px = None if tgt_pts is None else entry_px + d * tgt_pts
                pos = _Pos(
                    d=d, entry_bar=i, signal_bar=sbar, entry=entry_px, avg=entry_px, qty=q, init_qty=q,
                    entered_qty=q, stop=st_px, stop_pts=stop_pts, target=tg_px, atr=a,
                    setup=setup_a[sbar], conf=conf_a[sbar], atr_pct=md.atr_pct[sbar],
                    reason=sig.entry_reason.get(f"{setup_a[sbar]}|{d}", setup_a[sbar]),
                    best=entry_px, worst=entry_px, risk_dollars=q * stop_pts * pv,
                )
                pos.slip += (mkt_ticks + latency_ticks) * tv * q
                entered_now = True

        # 3) manage the open position on this bar
        if pos is not None:
            p = pos
            d = p.d
            hi_i, lo_i, op_i = h[i], l[i], o[i]
            stop_hit = (lo_i <= p.stop) if d > 0 else (hi_i >= p.stop)
            if stop_hit:
                gapped = (not entered_now) and ((op_i <= p.stop) if d > 0 else (op_i >= p.stop))
                px = op_i if gapped else p.stop
                # worst excursion is capped at the fill price
                p.worst = min(p.worst, px) if d > 0 else max(p.worst, px)
                reason = "Trailing stop" if p.trailed else ("Breakeven stop" if p.be_done else "Stop loss")
                close_leg(p, px, p.qty, True)
                finalize(p, i, reason, bar_min / 2 if not gapped else 0.0)
            else:
                p.worst = min(p.worst, lo_i) if d > 0 else max(p.worst, hi_i)
                # scale-in (stop order beyond entry), then partials/target
                if mg.scale_in and not p.scale_in_done and p.qty > 0:
                    trig = p.entry + d * mg.scale_in_at_r * p.stop_pts
                    if (hi_i >= trig) if d > 0 else (lo_i <= trig):
                        add = min(max(1, p.init_qty // 2), max(trd.max_contracts - p.qty, 0))
                        if add > 0:
                            p.avg = (p.avg * p.qty + trig * add) / (p.qty + add)
                            p.qty += add
                            p.entered_qty += add
                            p.slip += mkt_ticks * tv * add
                            event(p, i, "scale_in", trig, add)
                        p.scale_in_done = True
                if mg.partial_profit and not p.partial_done and p.qty >= 2:
                    ppx = p.entry + d * mg.partial_at_r * p.stop_pts
                    if (hi_i >= ppx) if d > 0 else (lo_i <= ppx):
                        q = min(max(1, int(p.qty * mg.partial_pct)), p.qty - 1)
                        close_leg(p, ppx, q, False)
                        event(p, i, "scale_out", ppx, q)
                        p.partial_done = True
                if mg.scale_out and not p.scale_out_done and p.qty >= 2:
                    spx = p.entry + d * 2 * mg.partial_at_r * p.stop_pts
                    if (hi_i >= spx) if d > 0 else (lo_i <= spx):
                        q = min(max(1, int(p.qty * mg.partial_pct)), p.qty - 1)
                        close_leg(p, spx, q, False)
                        event(p, i, "scale_out", spx, q)
                        p.scale_out_done = True
                p.best = max(p.best, hi_i) if d > 0 else min(p.best, lo_i)
                tgt_hit = p.target is not None and ((hi_i >= p.target) if d > 0 else (lo_i <= p.target))
                if tgt_hit:
                    gapped = (op_i >= p.target) if d > 0 else (op_i <= p.target)
                    px = op_i if (gapped and not entered_now) else p.target
                    close_leg(p, px, p.qty, False)
                    finalize(p, i, "Target", bar_min / 2)
                elif is_last[i]:
                    close_leg(p, c[i], p.qty, True)
                    finalize(p, i, "End of day", float(bar_min))
                else:
                    # management updates take effect from the next bar
                    fav = (p.best - p.entry) * d
                    if mg.breakeven and not p.be_done and fav >= mg.breakeven_trigger_r * p.stop_pts:
                        new_stop = p.entry + d * tick
                        if (new_stop > p.stop) if d > 0 else (new_stop < p.stop):
                            p.stop = new_stop
                            event(p, i, "breakeven", new_stop)
                        p.be_done = True
                    if mg.trailing_stop:
                        cand = p.best - d * mg.trail_atr_mult * p.atr
                        cand = _round_tick(cand, tick)
                        if (cand > p.stop) if d > 0 else (cand < p.stop):
                            p.stop = cand
                            p.trailed = True
                            event(p, i, "trail", cand)

        # 4) decisions made at this bar's close
        if pos is not None:
            want_exit = exit_l[i] if pos.d > 0 else exit_s[i]
            if want_exit and pend_exit_bar < 0 and not is_last[i]:
                pend_exit_bar = i + 1 + trd.exit_delay_bars
                if pend_exit_bar > hi - 1 or day_id[min(pend_exit_bar, len(day_id) - 1)] != d_id:
                    pend_exit_bar = -1  # would cross the session end; end-of-day exit handles it
        elif pend is None and not kill and not day_halt and side_a[i] != 0 and not is_last[i]:
            d = side_a[i]
            exec_bar = i + 1 + trd.entry_delay_bars
            if exec_bar < hi and day_id[exec_bar] == d_id and day_trades < trd.max_trades_per_day:
                sp = stop_distance(i, d)
                pend = (exec_bar, d, i, sp, target_distance(sp, atr_a[i]), atr_a[i])

    # close anything still open at the very end of the window
    if pos is not None:
        last = hi - 1
        close_leg(pos, c[last], pos.qty, True)
        finalize(pos, last, "End of data", float(bar_min))
    return trades
