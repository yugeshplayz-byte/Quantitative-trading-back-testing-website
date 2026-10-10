"""Runtime settings, read from environment variables (and an optional backend/.env file)."""
from __future__ import annotations

import subprocess
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./quant.db"
    allowed_origins: str = "http://localhost:3000"
    allowed_origin_regex: str = ""
    git_commit: str = ""
    environment: str = "development"
    seed_demo_data: bool = True
    # Optional password for the WHOLE site (HTTP Basic auth). Strongly recommended for any public link.
    app_password: str = ""
    app_username: str = "admin"
    # Folder holding the exported website (frontend/out). When it exists, FastAPI serves the site itself,
    # so one URL serves both the UI and the API.
    frontend_dir: str = ""
    # Real market data: drop CSV files named like MNQ.csv / MNQ_1m.csv into this folder (see docs/REAL_DATA.md).
    real_data_dir: str = "./data/real"
    real_data_tz: str = "America/New_York"  # timezone of timestamps in the CSVs that carry no UTC offset
    real_data_bar_label: str = "start"  # "start" or "end": whether a bar's timestamp is its open or its close time
    # Running pasted Python on the server is remote code execution. OFF unless you opt in.
    enable_custom_code: bool = False
    custom_code_token: str = ""  # if set, custom-code endpoints require header X-Admin-Token
    custom_code_timeout: int = 180  # seconds per sandbox run

    @property
    def origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        """Normalise provider URLs (Railway/Render/Heroku use postgres:// or postgresql://)."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def git_commit() -> str:
    """Commit hash recorded on experiments: env var first, then local git, else 'unknown'."""
    configured = get_settings().git_commit
    if configured:
        return configured
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=3
        )
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - git may simply not exist on the host
        return "unknown"
