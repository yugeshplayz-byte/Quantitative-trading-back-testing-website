"""Custom (pasted) strategy sandbox: validation, execution, lookahead detection, access control."""
import pytest

from app.config import get_settings
from app.custom.templates import TEMPLATES
from app.custom.validate import check_code

LEAKY = '''
import numpy as np
import pandas as pd

class Strategy:
    def signals(self, bars):
        fwd = bars["close"].shift(-3) - bars["close"]  # uses the FUTURE
        return pd.DataFrame({"side": np.sign(fwd).fillna(0)})
'''


@pytest.fixture()
def enabled(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "enable_custom_code", True)
    monkeypatch.setattr(s, "custom_code_token", "")
    return s


def test_static_checks_block_dangerous_code():
    assert any("os" in p for p in check_code("import os\nclass Strategy:\n  def signals(self,b): return b"))
    assert any("open" in p for p in check_code("class Strategy:\n  def signals(self,b): return open('f')"))
    assert any("__subclasses__" in p for p in check_code(
        "class Strategy:\n  def signals(self,b): return ().__class__.__subclasses__()"))
    assert check_code("class Foo: pass")  # no Strategy class
    assert not check_code(TEMPLATES[0]["code"])


def test_validate_template_reports_parameters(client, enabled):
    r = client.post("/api/custom-strategies/validate", json={"name": "t", "code": TEMPLATES[0]["code"]}).json()
    assert r["ok"] and {p["key"] for p in r["parameters"]} == {"rsi_len", "low"}


def test_validate_reports_runtime_errors_with_traceback(client, enabled):
    code = "class Strategy:\n    def signals(self, bars):\n        raise ValueError('boom')\n"
    r = client.post("/api/custom-strategies/validate", json={"name": "t", "code": code}).json()
    assert not r["ok"] and "boom" in " ".join(r["problems"]) and "strategy.py" in r["traceback"]


def test_blocked_import_rejected_at_runtime_too(client, enabled):
    r = client.post("/api/custom-strategies/validate",
                    json={"name": "t", "code": "import socket\nclass Strategy:\n  def signals(self,b): return b"}).json()
    assert not r["ok"]


def test_save_and_backtest_custom_strategy(client, enabled):
    saved = client.post("/api/custom-strategies", json={"name": "RSI test", "code": TEMPLATES[0]["code"]})
    assert saved.status_code == 200, saved.text
    key = saved.json()["key"]
    assert any(s["key"] == key for s in client.get("/api/meta").json()["strategies"])
    cfg = {"strategy": key, "symbol": "MNQ", "start_date": "2023-01-02", "end_date": "2023-12-29"}
    run = client.post("/api/backtest/run", json={"config": cfg, "name": "Custom RSI"})
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["metrics"]["total_trades"] > 20 and body["meta"]["lookahead"]["status"] == "ok"
    # optimiser works on custom strategies (signals for all grid cells computed in one sandbox call)
    opt = client.post("/api/optimization", json={"backtest_id": body["id"], "param_x": "rsi_len", "param_y": "low",
                                                  "x_values": [10, 14], "y_values": [20, 25], "metric": "net_profit"})
    assert opt.status_code == 200, opt.text
    client.delete(f"/api/backtests/{body['id']}")


def test_lookahead_bias_is_flagged(client, enabled):
    saved = client.post("/api/custom-strategies", json={"name": "Leaky", "code": LEAKY}).json()
    cfg = {"strategy": saved["key"], "symbol": "MNQ", "start_date": "2023-01-02", "end_date": "2023-12-29"}
    body = client.post("/api/backtest/run", json={"config": cfg}).json()
    assert body["meta"]["lookahead"]["status"] == "suspect"
    rob = client.get(f"/api/backtests/{body['id']}/dashboard").json()
    assert any(w["code"] == "lookahead" for w in rob["warnings"])
    client.delete(f"/api/backtests/{body['id']}")


def test_ml_template_runs_without_leakage(client, enabled):
    pytest.importorskip("sklearn")
    ml = next(t for t in TEMPLATES if t["id"] == "ml_logistic")
    saved = client.post("/api/custom-strategies", json={"name": "ML logistic", "code": ml["code"]}).json()
    cfg = {"strategy": saved["key"], "symbol": "MNQ", "start_date": "2023-06-01", "end_date": "2023-12-29"}
    body = client.post("/api/backtest/run", json={"config": cfg}).json()
    assert body["meta"]["lookahead"]["status"] == "ok" and body["metrics"]["total_trades"] > 50
    client.delete(f"/api/backtests/{body['id']}")


def test_token_required_when_configured(client, enabled, monkeypatch):
    monkeypatch.setattr(enabled, "custom_code_token", "s3cret")
    body = {"name": "t", "code": TEMPLATES[0]["code"]}
    assert client.post("/api/custom-strategies/validate", json=body).status_code == 401
    assert client.post("/api/custom-strategies/validate", json=body, headers={"X-Admin-Token": "nope"}).status_code == 401
    ok = client.post("/api/custom-strategies/validate", json=body, headers={"X-Admin-Token": "s3cret"})
    assert ok.status_code == 200 and ok.json()["ok"]


def test_sandbox_environment_has_no_secrets(client, enabled, monkeypatch):
    """The child process must not inherit DATABASE_URL or other secrets from the server."""
    monkeypatch.setenv("SECRET_CANARY", "top-secret")
    from app.custom.runner import _scrubbed_env

    env = _scrubbed_env("/tmp/x")
    assert "SECRET_CANARY" not in env and "DATABASE_URL" not in env
