"""FastAPI application entry point.

Run locally:      uvicorn app.main:app --reload
Run in production: uvicorn app.main:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import backtests, custom, meta, prop, research, risk, simulations
from .config import get_settings
from .custom.runner import CustomCodeError
from .db import SessionLocal, init_db
from .services.seed import seed_if_empty
from .web import PasswordGate, attach_frontend, frontend_path

log = logging.getLogger("quant")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if get_settings().seed_demo_data:
        with SessionLocal() as s:
            if seed_if_empty(s):
                log.info("Seeded demo backtests and saved strategies")
    yield


settings = get_settings()
app = FastAPI(title="Quant Backtester API", version=meta.VERSION, lifespan=lifespan)

# CORS: only the origins listed in ALLOWED_ORIGINS (+ optional regex for Vercel previews).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_origin_regex=settings.allowed_origin_regex or None,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Optional site-wide password (APP_PASSWORD). Added last so it wraps everything, CORS included.
app.add_middleware(PasswordGate)

for module in (meta, backtests, simulations, prop, risk, research, custom):
    app.include_router(module.router, prefix="/api")


@app.exception_handler(KeyError)
async def key_error(_: Request, exc: KeyError):
    return JSONResponse({"detail": str(exc.args[0]) if exc.args else "Not found"}, status_code=404)


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(CustomCodeError)
async def code_error(_: Request, exc: CustomCodeError):
    return JSONResponse({"detail": {"message": exc.message, "traceback": exc.traceback,
                                    "problems": exc.problems}}, status_code=400)


_site = frontend_path()
if _site is not None:
    attach_frontend(app, _site)  # one URL serves the website AND /api (must be registered last)
else:

    @app.get("/")
    def root():
        return {"name": "Quant Backtester API", "docs": "/docs", "health": "/api/health"}
