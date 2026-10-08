"""Starter strategies shown in the Strategy Lab. Each must run as-is in the sandbox."""
from __future__ import annotations

TEMPLATES = [
    {
        "id": "rsi_reversion",
        "name": "Rule-based: RSI mean reversion",
        "description": "Plain pandas rules, no ML. Shows the 'events' signal mode with explicit exits.",
        "code": '''import numpy as np
import pandas as pd


class Strategy:
    """Buy oversold / sell overbought RSI, exit when RSI crosses back through 50."""

    # simple numbers, or dicts with default/min/max/step for optimiser ranges
    params = {
        "rsi_len": {"default": 14, "min": 5, "max": 30, "step": 5, "label": "RSI length"},
        "low": {"default": 25, "min": 10, "max": 35, "step": 5, "label": "Oversold level"},
    }

    def signals(self, bars):
        c = bars["close"]
        delta = c.diff()
        n = int(self.params["rsi_len"])
        up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
        dn = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
        rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
        low = self.params["low"]
        in_window = (bars["tod"] >= 30) & (bars["tod"] <= 330)  # skip first 30 / last 60 minutes
        side = np.where((rsi < low) & in_window, 1, np.where((rsi > 100 - low) & in_window, -1, 0))
        return pd.DataFrame({
            "side": side,                       # +1 long, -1 short, 0 nothing (entry events)
            "confidence": (50 - rsi).abs() * 2, # optional 0-100
            "setup": "RSI extreme",             # optional label shown in the trade explorer
            "exit_long": rsi > 50,              # optional: close an open long at the next open
            "exit_short": rsi < 50,
        })
''',
    },
    {
        "id": "ml_logistic",
        "name": "ML: logistic-regression direction model",
        "description": ("scikit-learn model trained ONLY on bars before the backtest start, then used for every "
                        "bar in the test window ('position' signal mode). Install scikit-learn first "
                        "(pip install -r requirements-ml.txt)."),
        "code": '''import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


class Strategy:
    """Predicts whether price will be higher `horizon` bars from now.

    fit() receives ONLY bars before the backtest start date (no leakage into the test period).
    signals() receives every bar; each row's features use past data only (pct_change, rolling).
    """

    signal_mode = "position"  # side is a desired position every bar; engine enters/exits as it changes

    params = {
        "horizon": {"default": 6, "min": 3, "max": 18, "step": 3, "label": "Prediction horizon (bars)"},
        "threshold": {"default": 0.54, "min": 0.50, "max": 0.62, "step": 0.02, "label": "Probability threshold"},
    }

    def _features(self, bars):
        c = bars["close"]
        f = pd.DataFrame(index=bars.index)
        for n in (1, 3, 6, 12, 24):
            f[f"ret_{n}"] = c.pct_change(n)
        f["vwap_dist"] = (c - bars["vwap"]) / bars["atr"]
        f["range_atr"] = (bars["high"] - bars["low"]) / bars["atr"]
        vol = bars["volume"]
        f["vol_z"] = (vol - vol.rolling(48).mean()) / vol.rolling(48).std()
        f["tod_sin"] = np.sin(2 * np.pi * bars["tod"] / 390)
        f["tod_cos"] = np.cos(2 * np.pi * bars["tod"] / 390)
        return f.replace([np.inf, -np.inf], np.nan)

    def fit(self, train_bars):
        h = int(self.params["horizon"])
        X = self._features(train_bars)
        future = train_bars["close"].shift(-h)
        y = (future > train_bars["close"]).astype(int)
        ok = X.notna().all(axis=1) & future.notna()  # last h rows have no label -> excluded
        self.model = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=500))
        self.model.fit(X[ok], y[ok])

    def signals(self, bars):
        X = self._features(bars)
        p = pd.Series(0.5, index=bars.index)
        ok = X.notna().all(axis=1)
        p[ok] = self.model.predict_proba(X[ok])[:, 1]
        thr = self.params["threshold"]
        side = np.where(p > thr, 1, np.where(p < 1 - thr, -1, 0))
        tradable = (bars["tod"] >= 15) & (bars["tod"] <= 360)
        return pd.DataFrame({
            "side": np.where(tradable, side, 0),
            "confidence": (p - 0.5).abs() * 200,
            "setup": "ML direction",
        })
''',
    },
    {
        "id": "skeleton",
        "name": "Blank skeleton",
        "description": "The minimal contract: a Strategy class with signals(self, bars).",
        "code": '''import numpy as np
import pandas as pd


class Strategy:
    """bars columns: ts, date, open, high, low, close, volume, tod (min since 09:30), day_id, atr, vwap."""

    params = {"lookback": 20}

    def fit(self, train_bars):
        # optional: train a model here. train_bars contains only data BEFORE the backtest start.
        pass

    def signals(self, bars):
        ma = bars["close"].rolling(int(self.params["lookback"])).mean()
        side = np.where(bars["close"] > ma, 1, np.where(bars["close"] < ma, -1, 0))
        return pd.DataFrame({"side": side})
''',
    },
]
