"""Parent-side launcher for the sandbox worker (one subprocess per call)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

from ..config import get_settings
from .validate import check_code

WORKER = Path(__file__).with_name("worker.py")


class CustomCodeError(Exception):
    def __init__(self, message: str, traceback: str = "", problems: list[str] | None = None):
        super().__init__(message)
        self.message, self.traceback, self.problems = message, traceback, problems or []


def _scrubbed_env(workdir: str) -> dict:
    """Pass nothing but what Python needs: no DATABASE_URL, tokens or other secrets."""
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8", "OMP_NUM_THREADS": "2",
           "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "TEMP": workdir, "TMP": workdir, "TMPDIR": workdir}
    for k in ("SYSTEMROOT", "SYSTEMDRIVE", "LD_LIBRARY_PATH"):
        if k in os.environ:
            env[k] = os.environ[k]
    return env


def _limits():  # POSIX only: cap memory and CPU time of the child
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
    secs = get_settings().custom_code_timeout + 10
    resource.setrlimit(resource.RLIMIT_CPU, (secs, secs))


def run_worker(code: str, bars: pd.DataFrame, mode: str, test_lo: int, test_hi: int,
               param_sets: list[dict] | None = None, check_lookahead: bool = False) -> dict:
    problems = check_code(code)
    if problems:
        raise CustomCodeError("Code failed validation", problems=problems)
    timeout = get_settings().custom_code_timeout
    with tempfile.TemporaryDirectory(prefix="qbt_custom_") as tmp:
        jd = Path(tmp)
        (jd / "code.py").write_text(code, encoding="utf-8")
        bars.to_pickle(jd / "bars.pkl")
        (jd / "job.json").write_text(json.dumps({
            "mode": mode, "test_lo": test_lo, "test_hi": test_hi,
            "param_sets": param_sets or [{}], "check_lookahead": check_lookahead}))
        kwargs = {"preexec_fn": _limits} if os.name == "posix" else {}
        try:
            proc = subprocess.run([sys.executable, "-I", str(WORKER), str(jd)], cwd=tmp, env=_scrubbed_env(tmp),
                                  capture_output=True, text=True, timeout=timeout, **kwargs)
        except subprocess.TimeoutExpired as exc:
            raise CustomCodeError(f"Strategy exceeded the {timeout}s time limit") from exc
        result_file = jd / "result.json"
        if not result_file.exists():
            tail = (proc.stderr or proc.stdout or "")[-1500:]
            raise CustomCodeError("The strategy process crashed before returning a result", traceback=tail)
        result = json.loads(result_file.read_text(encoding="utf-8"))
    if not result.get("ok"):
        raise CustomCodeError(result.get("error", "Strategy failed"), traceback=result.get("traceback", ""))
    return result
