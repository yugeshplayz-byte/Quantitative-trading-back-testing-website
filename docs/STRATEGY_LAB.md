# Strategy Lab: backtest your own Python / ML strategies

## Enable it (local use)

```powershell
# backend/.env
ENABLE_CUSTOM_CODE=true
```

Restart the backend. For scikit-learn models: `pip install -r backend/requirements-ml.txt`.

## The contract

```python
import numpy as np
import pandas as pd

class Strategy:
    params = {"lookback": 20}           # numbers you want to tune (or dicts with default/min/max/step)
    signal_mode = "events"              # or "position" (see below)

    def fit(self, train_bars):          # OPTIONAL - train a model here
        ...                             # receives ONLY bars before the backtest start date

    def signals(self, bars) -> pd.DataFrame:
        return pd.DataFrame({
            "side": ...,                # +1 long, -1 short, 0 nothing   (required)
            "confidence": ...,          # optional, 0-1 or 0-100
            "setup": "my label",        # optional, shown in the Trade Explorer
            "exit_long": ...,           # optional bool: close an open long at the next open
            "exit_short": ...,
        })
```

`bars` is a DataFrame with columns `ts, date, open, high, low, close, volume, tod, day_id, atr, vwap` (`tod` = minutes since 09:30). `self.params` holds the active parameter values.

* **Timing:** a signal on bar *i* is acted on at bar *i+1*'s open. Stops, targets, sizing, costs and trade management come from the Configuration, exactly as for built-in strategies.
* **`signal_mode = "events"`** (default): `side != 0` means "enter now"; exits come from stops/targets/`exit_*`/end of day.
* **`signal_mode = "position"`**: `side` is the *desired position every bar* (typical for classifiers). The engine enters when flat and exits when the desired position changes away.

## Allowed imports

`numpy, pandas, scipy, sklearn, statsmodels, xgboost, lightgbm, torch, joblib, math, statistics, itertools, functools, collections, typing, dataclasses, datetime, warnings, random, numbers, enum, abc, heapq, bisect, operator, copy, decimal, fractions, time, ta, talib` (only those you have installed will import). `open`, `eval`, `exec`, `compile`, `input`, `os`, `sys`, `subprocess`, `socket` and dunder-escape tricks are blocked.

## Keeping ML honest

1. **Never use future data.** `close.shift(-h)` labels are fine **only inside `fit()` on train bars**. In `signals()` use trailing information only.
2. **Fit scalers/encoders inside `fit()`**, not on the whole series.
3. **Set random seeds** (`random_state=0`, `torch.manual_seed`, ...) so runs repeat and the lookahead check can run.
4. **Expect failure on the random-walk market.** There is nothing to learn there. If your model is profitable on `random_walk`, you almost certainly have leakage or a bug.
5. One lucky backtest proves nothing: read the p-value and expectancy interval, run **walk-forward**, check **parameter sensitivity** and the **overfitting** page, and remember every variant you try raises the chance of fooling yourself.
6. Training history is limited to the synthetic epoch before your start date (from 2022-01-03). Short history means weak models - the page tells you how many training days you have.

## The lookahead check

After the first run the platform re-runs your `signals()` on the data truncated at five points inside the test window and compares the last 500 signals before each cut. A causal strategy reproduces them exactly; if any change, the run is marked **suspect** and a high-severity warning is attached. It also skips with an explanation if your strategy is non-deterministic. It is a strong hint, **not proof**: it cannot detect leaks that never affect bars near the cut points.

## How it runs (and why it is gated)

Each run spawns a separate Python process (`app/custom/worker.py`) with a scrubbed environment, an import allow-list, no file/eval builtins, and a timeout (`CUSTOM_CODE_TIMEOUT`, default 180s; memory/CPU limits on Linux). It communicates only through temp files. **This reduces accidents and casual misuse; it is not a security boundary.** Run it on your own machine. If you host it, put the backend on a private network, set `CUSTOM_CODE_TOKEN`, and never enable it on a public instance.

## Optimisation and walk-forward for custom strategies

Parameters you declare in `params` appear in Parameter Sensitivity and Walk-forward. All needed parameter sets are computed in **one** sandbox process (fast), but a model that retrains inside `fit()` retrains per parameter set, so keep grids small.
