from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_session
from ..services.store import Bundle, load_bundle

SessionDep = Depends(get_session)


def get_bundle(bid: str, session: Session = SessionDep) -> Bundle:
    return load_bundle(session, bid)  # KeyError -> 404 via the app-level handler


def require_custom_code(x_admin_token: str | None = Header(default=None)) -> None:
    check_custom_access(x_admin_token)


def check_custom_access(x_admin_token: str | None) -> None:
    """Pasted-code endpoints run arbitrary Python on the server: off by default, optional token."""
    s = get_settings()
    if not s.enable_custom_code:
        raise HTTPException(403, "Custom strategy code is disabled on this server. Set ENABLE_CUSTOM_CODE=true "
                                 "in backend/.env (local use) - see the README security section first.")
    if s.custom_code_token and not secrets.compare_digest(x_admin_token or "", s.custom_code_token):
        raise HTTPException(401, "Missing or invalid X-Admin-Token")
