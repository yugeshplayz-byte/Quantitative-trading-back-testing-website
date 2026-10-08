"""Experiment tracking model - every backtest run is an experiment (BT-000001 ...)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class Experiment(BaseModel):
    id: str
    name: str
    strategy: str
    version: str = "v1"
    dataset: str
    start_date: date
    end_date: date
    parameters: dict[str, float]
    risk_settings: dict
    metrics: dict[str, float | int | None]
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    favorite: bool = False
    created_at: datetime
    git_commit: str
    seed: int


class ExperimentUpdate(BaseModel):
    backtest_id: str | None = None
    name: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    favorite: bool | None = None
    version: str | None = None
