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
