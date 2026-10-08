# Quant assumptions & honesty design

The platform's one rule: **its output must be honest**. Nothing is tuned to make strategies look good, and every place where a number could mislead is labelled. This document lists the assumptions behind each calculation and the safeguards that keep results truthful.

## 1. Data

* **Default market (`random_walk`)**: 5-minute RTH bars (09:30–16:00 ET). Returns are uncorrelated and fat-tailed (Student-t, 5 d.o.f.), with a U-shaped intraday volatility profile and volatility clustering. There is **no drift, momentum or mean-reversion**. A correct backtester should therefore find no edge here, and costs make strategies lose on average. A test enforces this (`tests/test_honesty.py`).
* **`structured` market**: engineered momentum on a minority of days, mean reversion on others. Used only to validate the platform; always labelled "ENGINEERED" in the UI.
* Deterministic: the same `(symbol, seed, model)` always yields the same bars. MNQ/NQ share one underlying, MES/ES another (~0.9 correlated).
* Regimes (Trending, Ranging, Bull, Bear, Neutral, High/Low Volatility) are derived **causally** from price (ATR percentile, efficiency ratio, trend vs a slow EMA), never from the generator's hidden labels, and a trade's regime is the one known at its signal bar.
* Real data: replace `load_bars()`; nothing else changes.

## 2. Execution model (`backtesting/engine.py`)

| Item | Assumption |
|---|---|
| Signals | Decided at a bar's close, filled at the **next bar's open** (+ optional delay). |
| Position | One at a time. |
| Stops | Resting orders. If a bar trades through both stop and target, **the stop fills first**. A gap beyond the stop fills at the open. |
| Targets / partials | Limit orders filled only if price trades **through** the level by `limit_through_ticks` (default 1 tick). A mere touch does not fill. |
| Slippage | `slippage_ticks + spread_ticks/2` charged on every market fill (entries, stops, signal exits, end-of-day exits), plus latency (1 tick per 500 ms, entries). |
| Fees | `(commission + exchange fee)` per contract per side, on every contract entered and exited. |
| P&L | `net = gross − fees − slippage`. |
| Sizing | Fixed contracts, fixed-dollar risk or % risk from the stop distance. If one contract risks more than 2× the budget the trade is **skipped**, not oversized. |
| MAE/MFE | Bar highs/lows vs the initial entry, in dollars for the initial quantity; a stopped trade's MAE is capped at its fill. |
| Breakeven / trailing | Updated after a bar's exit checks, effective from the **next** bar. |

## 3. Statistics (`quant/metrics.py`)

* Sharpe / Sortino use **daily** returns including no-trade days (zeros), annualised with √252, risk-free 0. Sortino downside deviation = √mean(min(r,0)²) over all days.
* Headline max drawdown uses equity after **every closed trade** (so it is never smaller than the end-of-day figure). Drawdown tables use daily closes. Neither includes open-trade excursions.
* Calmar = CAGR / max drawdown %.
* **Significance:** `expectancy_pvalue` is a two-sided t-test of mean trade P&L vs 0, and a 95% interval for the true average trade is reported. Trades are treated as independent (slightly flattering for clustered strategies). If the interval contains 0 the result is "unproven".

## 4. Monte Carlo (`quant/monte_carlo.py`)

Seeded NumPy resampling of the backtest's **net trade P&L**: reshuffle (without replacement, tiling if more trades than history), iid bootstrap, circular block bootstrap. Optional rescaling to another risk per trade (`pnl × risk/base_risk`), which is **hypothetical** when the risk is below one contract's cost (flagged). Monte Carlo shows path luck; it cannot prove an edge is real.

## 5. Risk of ruin (`quant/ruin.py`)

Brownian-motion approximation with drift μ and variance σ² of a two-point trade distribution: `P(ruin) = exp(−2μD/σ²)` (μ>0, else 1) and the exact first-passage formula for a finite number of trades, cross-checked by a seeded Bernoulli simulation. Real outcomes are fatter-tailed, so true risk is usually higher.

## 6. Prop-firm engine (`prop_firm/`)

Rules are fully configurable (no firm hard-coded). Day-level model: each day's intraday low/high = closed P&L extended by each trade's MAE/MFE.

* **Static**: floor = start − max drawdown. **EOD trailing**: floor follows the highest end-of-day balance; breaches are still tested intraday. **Intraday trailing**: floor follows the highest intraday equity; assumes the day's high prints **before** its low (worst case). Optional lock at the starting balance.
* PASS needs target reached **and** minimum trading days, minimum profitable days and the consistency rule. Breach checks win over PASS on the same day. Failure reasons are exact ("Daily loss limit breached on 2023-03-14: intraday low −1,240 vs limit −1,100").
* Monte Carlo resamples **days** (optionally blocks of days) and rescales P&L, lows/highs and contracts by the risk scale. Funded survival converts calendar days to trading days at 5/7. Payouts reduce the balance but not the drawdown floor (conservative).
* The risk optimiser's score is *expected payout per attempt* = P(pass) × E[trader payouts]. Risk levels below half a contract's cost are flagged unachievable and excluded from the best zone.

## 7. Optimisation, walk-forward, scores

* Grid results are **in-sample**. The page shows a selection-bias estimate: with N cells and T years, a zero-edge strategy's best Sharpe is typically ≈ √(2 ln N)/√T.
* Walk-forward: parameters chosen on each train window, evaluated on the following unseen window; OOS segments are stitched using only days not already covered.
* Stability score: neighbourhood of the best cell, plateau width, share of positive cells, largest adjacent jump.
* **Strategy score** (0–100) = weighted profitability, risk, robustness, consistency, execution resilience, prop suitability. **Honesty gate:** capped at 25 if expectancy ≤ 0 after costs, at 45 if profit is not statistically significant (p > 0.05). Full formulas are shown in the UI under "Show methodology".
* **Overfitting risk** (LOW/MEDIUM/HIGH) from parameter count, optimisation trials logged, IS→OOS degradation, parameter stability, trade count, complexity, Monte Carlo degradation and walk-forward consistency. The platform's own robustness probes are not counted as trials; your searches are.

## 8. Lookahead protection

* `tests/test_no_lookahead.py` truncates the data at several points (including mid-day) and requires that **every indicator, every built-in strategy's signals and every trade that had closed** are identical with the future removed.
* Custom strategies get the same check at run time (five truncation points; mismatches are flagged as "suspect"). It is a strong hint, not proof. Models are trained only on bars before the test start.

## 9. Known limitations

Bar-level fills; no queue position, partial fills or market impact; static slippage (use the stress tests); synthetic data; approximate event calendar; day-level prop evaluation; trade independence assumed in the t-test and ruin approximation.
