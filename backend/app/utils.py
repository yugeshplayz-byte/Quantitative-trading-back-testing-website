"""Small shared helpers."""
from __future__ import annotations

import datetime as dt
import math
from typing import Any

import numpy as np
import pandas as pd


def clean(obj: Any) -> Any:
    """Recursively convert numpy/pandas/date values to JSON-safe python (NaN/inf -> None)."""
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, (dt.datetime, pd.Timestamp)):
        return obj.isoformat()
    if isinstance(obj, dt.date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [clean(v) for v in obj.tolist()]
    if isinstance(obj, pd.Series):
        return [clean(v) for v in obj.tolist()]
    if hasattr(obj, "model_dump"):
        return clean(obj.model_dump())
    return str(obj)
