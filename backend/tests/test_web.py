"""Single-URL hosting: optional site password and static website serving."""
import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.web import PasswordGate, attach_frontend


def basic(user, pw):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()}


@pytest.fixture()
def password(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "app_password", "s3cret-pass")
    monkeypatch.setattr(s, "app_username", "admin")


def test_no_password_configured_means_open(client):
    assert client.get("/api/backtests").status_code == 200


def test_password_protects_the_whole_api(client, password):
    assert client.get("/api/backtests").status_code == 401
    r = client.get("/api/backtests")
    assert r.headers["www-authenticate"].startswith("Basic")
    assert client.get("/api/backtests", headers=basic("admin", "wrong")).status_code == 401
    assert client.get("/api/backtests", headers=basic("someone", "s3cret-pass")).status_code == 401
    assert client.get("/api/backtests", headers={"Authorization": "Basic !!!notbase64"}).status_code == 401
    assert client.get("/api/backtests", headers=basic("admin", "s3cret-pass")).status_code == 200
    # the password also guards the custom-strategy and download endpoints
    assert client.get("/api/backtests/BT-000001/trades?format=csv").status_code == 401


def test_health_check_stays_open_for_hosting_platforms(client, password):
    assert client.get("/api/health").status_code == 200


def test_site_is_served_and_gated_from_one_origin(tmp_path, password):
    (tmp_path / "index.html").write_text("<title>site</title>")
    sub = tmp_path / "backtest" / "trades"
    sub.mkdir(parents=True)
    (sub / "index.html").write_text("<h1>trades</h1>")
    app = FastAPI()

    @app.get("/api/ping")
    def ping():
        return {"pong": True}

    attach_frontend(app, tmp_path)  # registered last, so /api still wins
    app.add_middleware(PasswordGate)
    c = TestClient(app)
    assert c.get("/").status_code == 401 and c.get("/api/ping").status_code == 401
    ok = basic("admin", "s3cret-pass")
    assert c.get("/", headers=ok).text == "<title>site</title>"
    assert c.get("/backtest/trades/", headers=ok).text == "<h1>trades</h1>"
    assert c.get("/api/ping", headers=ok).json() == {"pong": True}
