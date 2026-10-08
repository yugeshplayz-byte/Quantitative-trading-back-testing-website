"""Standalone sandbox worker: executes ONE user strategy in an isolated subprocess.

Run as:  python -I worker.py <job_dir>
It deliberately imports nothing from the `app` package (no DB, no settings, no secrets) and
talks to the parent only through files in <job_dir>:
    in : job.json, code.py, bars.pkl        out: result.json

Python cannot be truly sandboxed in-process. The restrictions below (import allow-list, no open/
eval/exec, no dunder escapes) stop accidents and casual misuse; real isolation comes from the
parent (separate process, scrubbed environment, timeout) and from NOT enabling custom code on a
shared public host.
"""
from __future__ import annotations

import builtins
import json
import sys
import time
import traceback
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ALLOWED_IMPORTS = {
    "numpy", "pandas", "scipy", "sklearn", "statsmodels", "xgboost", "lightgbm", "torch", "joblib",
    "math", "statistics", "itertools", "functools", "collections", "typing", "dataclasses", "datetime",
    "warnings", "random", "numbers", "enum", "abc", "heapq", "bisect", "operator", "copy", "decimal",
    "fractions", "time", "__future__", "ta", "talib",
}
BLOCKED_BUILTINS = {"open", "eval", "exec", "compile", "input", "breakpoint", "exit", "quit", "help",
                    "memoryview", "__loader__", "__spec__"}
_real_import = builtins.__import__


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if globals is not None and globals.get("__name__") == "user_strategy":
        root = name.split(".")[0]
        if root not in ALLOWED_IMPORTS:
            raise ImportError(f"import of '{root}' is not allowed in custom strategies "
                              f"(allowed: {', '.join(sorted(ALLOWED_IMPORTS))})")
    return _real_import(name, globals, locals, fromlist, level)


def _namespace() -> dict:
    safe = {k: v for k, v in vars(builtins).items() if k not in BLOCKED_BUILTINS}
    safe["__import__"] = _guarded_import
    return {"__name__": "user_strategy", "__builtins__": safe}


def _spec_from_attr(params) -> list[dict]:
    specs = []
    for key, v in (params or {}).items():
        if isinstance(v, dict):
            d = float(v.get("default", 0.0))
            lo = float(v.get("min", d * 0.5 if d else -1.0))
            hi = float(v.get("max", d * 1.5 if d else 1.0))
            step = float(v.get("step", (hi - lo) / 10 or 1.0))
            label = str(v.get("label", key))
        else:
            d = float(v)
            lo, hi = (d * 0.5, d * 1.5) if d else (-1.0, 1.0)
            if lo > hi:
                lo, hi = hi, lo
            step, label = (hi - lo) / 10 or 1.0, key
        specs.append({"key": str(key), "label": label, "default": d, "min": lo, "max": hi,
                      "step": round(step, 6)})
    return specs


def _defaults(cls, overrides: dict) -> dict:
    out = {s["key"]: s["default"] for s in _spec_from_attr(getattr(cls, "params", {}))}
    for k, v in (overrides or {}).items():
        if k in out:
            out[k] = float(v)
    return out


def _make(cls, params: dict):
    inst = cls()
    inst.params = params
    return inst


def _normalize(res, n: int, mode: str) -> dict:
    if isinstance(res, (pd.Series, np.ndarray, list)):
        df = pd.DataFrame({"side": np.asarray(res)})
    elif isinstance(res, pd.DataFrame):
        df = res.reset_index(drop=True)
    else:
        raise TypeError("signals() must return a pandas DataFrame/Series or numpy array of per-bar signals")
    if len(df) != n:
        raise ValueError(f"signals() returned {len(df)} rows but {n} bars were supplied - return one row per bar")
    if "side" not in df.columns:
        raise ValueError("signals() DataFrame needs a 'side' column (+1 long, -1 short, 0 flat)")
    side = np.sign(np.nan_to_num(df["side"].to_numpy(dtype=float))).astype(int)
    if "confidence" in df.columns:
        conf = np.nan_to_num(df["confidence"].to_numpy(dtype=float), nan=50.0)
        if np.nanmax(np.abs(conf)) <= 1.0:
            conf = conf * 100.0
        conf = np.clip(conf, 0, 100)
    else:
        conf = np.full(n, 50.0)
    setup = (df["setup"].fillna("Custom").astype(str).to_numpy() if "setup" in df.columns
             else np.full(n, "Custom", dtype=object))
    if mode == "position":
        exit_long, exit_short = side != 1, side != -1
    else:
        exit_long = df["exit_long"].fillna(False).to_numpy(dtype=bool) if "exit_long" in df.columns else np.zeros(n, bool)
        exit_short = df["exit_short"].fillna(False).to_numpy(dtype=bool) if "exit_short" in df.columns else np.zeros(n, bool)
    setup = np.where(side != 0, setup, "")
    return {"side": side, "confidence": np.round(conf, 1), "setup": setup,
            "exit_long": exit_long, "exit_short": exit_short}


def _run_one(cls, bars: pd.DataFrame, train: pd.DataFrame, params: dict, mode: str) -> dict:
    inst = _make(cls, params)
    if hasattr(inst, "fit"):
        inst.fit(train.copy())
    return _normalize(inst.signals(bars.copy()), len(bars), mode)


def _lookahead_check(cls, bars, train, params, mode, first, lo, hi) -> dict:
    """Re-run on truncated histories; a causal strategy reproduces its earlier signals exactly."""
    again = _run_one(cls, bars, train, params, mode)
    if not np.array_equal(again["side"], first["side"]):
        return {"status": "skipped", "message": "Signals differ between two identical runs - set random seeds "
                "(e.g. random_state=0) so lookahead detection can run."}
    span = hi - lo
    if span < 400:
        return {"status": "skipped", "message": "Test window too short for lookahead detection."}
    cuts = [lo + span // 4, lo + span // 2, lo + 3 * span // 4]
    bad = 0
    for c in cuts:
        part = _run_one(cls, bars.iloc[: c + 1].reset_index(drop=True), train, params, mode)
        w0 = max(0, c - 300)
        bad += int((part["side"][w0 : c + 1] != first["side"][w0 : c + 1]).sum())
    if bad:
        return {"status": "suspect", "mismatches": bad,
                "message": f"{bad} signals changed when future bars were removed - your strategy likely "
                           "uses future information (lookahead bias). Check shift(), rolling windows and "
                           "any scaling/normalisation computed over the full series."}
    return {"status": "ok", "message": "No lookahead detected at 3 truncation points."}


def main(job_dir: str) -> None:
    jd = Path(job_dir)
    out: dict = {"ok": False}
    t0 = time.time()
    try:
        warnings.filterwarnings("ignore")
        job = json.loads((jd / "job.json").read_text())
        bars = pd.read_pickle(jd / "bars.pkl").reset_index(drop=True)
        code = (jd / "code.py").read_text(encoding="utf-8")
        ns = _namespace()
        exec(compile(code, "strategy.py", "exec"), ns)  # noqa: S102 - the whole point of this worker
        cls = ns.get("Strategy")
        if not isinstance(cls, type):
            raise NameError("Your code must define a class named `Strategy` with a `signals(self, bars)` method.")
        if not hasattr(cls, "signals"):
            raise AttributeError("`Strategy` needs a `signals(self, bars)` method.")
        mode = getattr(cls, "signal_mode", "events")
        if mode not in ("events", "position"):
            raise ValueError("signal_mode must be 'events' or 'position'")
        lo, hi = int(job["test_lo"]), int(job["test_hi"])
        train = bars.iloc[:lo]

        if job["mode"] == "describe":
            specs = _spec_from_attr(getattr(cls, "params", {}))
            params = _defaults(cls, {})
            smoke_n = min(len(bars), lo + 1500)
            smoke = _run_one(cls, bars.iloc[:smoke_n].reset_index(drop=True), train, params, mode)
            out.update(ok=True, parameters=specs, signal_mode=mode, has_fit=hasattr(cls, "fit"),
                       smoke_signals=int((smoke["side"] != 0).sum()), doc=(cls.__doc__ or "").strip(),
                       seconds=round(time.time() - t0, 2))
        else:
            results, lookahead = [], None
            for i, overrides in enumerate(job["param_sets"]):
                params = _defaults(cls, overrides)
                res = _run_one(cls, bars, train, params, mode)
                if i == 0 and job.get("check_lookahead"):
                    lookahead = _lookahead_check(cls, bars, train, params, mode, res, lo, hi)
                results.append({k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in res.items()}
                               | {"params": params})
            out.update(ok=True, results=results, lookahead=lookahead, signal_mode=mode,
                       seconds=round(time.time() - t0, 2))
    except BaseException as exc:  # noqa: BLE001 - report everything to the parent
        tb = traceback.format_exc().splitlines()
        # keep only frames from the user's file plus the final message
        keep = [ln for ln in tb if "strategy.py" in ln or not ln.startswith("  File")]
        out.update(ok=False, error=f"{type(exc).__name__}: {exc}", traceback="\n".join(keep[-14:]))
    (jd / "result.json").write_text(json.dumps(out), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
