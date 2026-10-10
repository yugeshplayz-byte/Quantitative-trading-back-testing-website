"""Serving the exported website from FastAPI, and the optional site-wide password."""
from __future__ import annotations

import base64
import secrets
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import get_settings

OPEN_PATHS = ("/api/health",)  # left open so hosting platforms can health-check without a password


class PasswordGate:
    """HTTP Basic auth for every request when APP_PASSWORD is set (read at request time).

    Browsers show their native login prompt once and then send the credentials with every request,
    including the app's own API calls. No password configured = no gate (local development).
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        s = get_settings()
        if (scope["type"] != "http" or not s.app_password or scope["path"] in OPEN_PATHS
                or scope["method"] == "OPTIONS"):  # CORS preflights carry no credentials and no data
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        auth = headers.get("authorization", "")
        ok = False
        if auth.lower().startswith("basic "):
            try:
                user, _, pw = base64.b64decode(auth[6:]).decode("utf-8").partition(":")
                ok = secrets.compare_digest(user, s.app_username) & secrets.compare_digest(pw, s.app_password)
            except Exception:  # noqa: BLE001 - malformed header just fails the check
                ok = False
        if ok:
            await self.app(scope, receive, send)
            return
        resp = PlainTextResponse("Authentication required", status_code=401,
                                 headers={"WWW-Authenticate": 'Basic realm="Quant Backtester", charset="UTF-8"'})
        await resp(scope, receive, send)


def frontend_path() -> Path | None:
    configured = get_settings().frontend_dir
    candidates = [Path(configured)] if configured else [Path(__file__).resolve().parents[2] / "frontend" / "out"]
    return next((p for p in candidates if (p / "index.html").exists()), None)


def attach_frontend(app: FastAPI, directory: Path) -> None:
    """Serve the exported site at / (registered LAST so /api/* routes win)."""
    app.mount("/", StaticFiles(directory=str(directory), html=True), name="web")
