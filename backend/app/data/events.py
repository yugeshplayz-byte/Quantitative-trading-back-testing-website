"""SAMPLE macro-event calendar (approximate dates, NOT an official schedule).

Rules of thumb are used to place each release so event analysis works out of the box:
CPI ~12th, PPI ~14th, retail sales ~15th, NFP first Friday, PCE last Friday, GDP late in
Jan/Apr/Jul/Oct, jobless claims every Thursday, FOMC on eight mid-month Wednesdays.
Replace `event_calendar()` with a real data feed (e.g. an economic-calendar API) later.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

import pandas as pd

EVENT_TYPES = ["FOMC", "CPI", "PPI", "NFP", "PCE", "GDP", "Retail Sales", "Jobless Claims"]
_RELEASE_TIME = {"FOMC": "14:00", "CPI": "08:30", "PPI": "08:30", "NFP": "08:30", "PCE": "08:30",
                 "GDP": "08:30", "Retail Sales": "08:30", "Jobless Claims": "08:30"}
_FOMC_MONTHS = (1, 3, 5, 6, 7, 9, 11, 12)


def _next_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7 + 7 * (n - 1))
    return d


def _last_weekday(year: int, month: int, weekday: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    d = nxt - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


@lru_cache(maxsize=1)
def event_calendar() -> pd.DataFrame:
    rows: list[tuple[date, str, str]] = []
    for year in range(2022, 2026):
        for month in range(1, 13):
            rows.append((_next_weekday(date(year, month, 12)), "CPI", _RELEASE_TIME["CPI"]))
            rows.append((_next_weekday(date(year, month, 14)), "PPI", _RELEASE_TIME["PPI"]))
            rows.append((_next_weekday(date(year, month, 15)), "Retail Sales", _RELEASE_TIME["Retail Sales"]))
            rows.append((_nth_weekday(year, month, 4, 1), "NFP", _RELEASE_TIME["NFP"]))
            rows.append((_last_weekday(year, month, 4), "PCE", _RELEASE_TIME["PCE"]))
            if month in (1, 4, 7, 10):
                rows.append((_last_weekday(year, month, 3), "GDP", _RELEASE_TIME["GDP"]))
            if month in _FOMC_MONTHS:
                rows.append((_nth_weekday(year, month, 2, 3), "FOMC", _RELEASE_TIME["FOMC"]))
        d = _nth_weekday(year, 1, 3, 1)
        while d.year == year:
            rows.append((d, "Jobless Claims", _RELEASE_TIME["Jobless Claims"]))
            d += timedelta(days=7)
    df = pd.DataFrame(rows, columns=["date", "event", "time"])
    return df.sort_values(["date", "event"]).reset_index(drop=True)
