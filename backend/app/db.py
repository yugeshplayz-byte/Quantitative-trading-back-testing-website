"""Database setup (SQLAlchemy 2.0). SQLite locally, PostgreSQL in production via DATABASE_URL."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class BacktestRow(Base):
    __tablename__ = "backtests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    strategy: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(40), default="v1")
    dataset: Mapped[str] = mapped_column(String(200), default="")
    config: Mapped[dict] = mapped_column(JSON)
    metrics: Mapped[dict] = mapped_column(JSON)
    trades: Mapped[list] = mapped_column(JSON)
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # e.g. lookahead check result, run seconds
    git_commit: Mapped[str] = mapped_column(String(64), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PresetRow(Base):
    __tablename__ = "strategy_presets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    config: Mapped[dict] = mapped_column(JSON)
    prop_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CustomStrategyRow(Base):
    __tablename__ = "custom_strategies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    code: Mapped[str] = mapped_column(Text)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AnalysisCache(Base):
    __tablename__ = "analysis_cache"
    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


_settings = get_settings()
_url = _settings.sqlalchemy_url
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}
engine = create_engine(_url, connect_args=_connect_args, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
