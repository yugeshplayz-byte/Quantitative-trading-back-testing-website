"""Real-data CSV loading: conventions, validation, and an exact round trip with the synthetic path."""
import numpy as np
import pandas as pd
import pytest

from app.backtesting.engine import run_backtest
from app.backtesting.market import get_market_data
from app.config import get_settings
from app.data.real import RealDataError, load_real_bars, quality_report
from app.data.synthetic import generate_5m_bars
from app.models.config import BacktestConfig


@pytest.fixture()
def real_dir(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "real_data_dir", str(tmp_path))
    monkeypatch.setattr(s, "real_data_tz", "America/New_York")
    monkeypatch.setattr(s, "real_data_bar_label", "start")
    return tmp_path


def export(df: pd.DataFrame, path, **kw):
    out = pd.DataFrame({"timestamp": df["ts"].dt.strftime("%Y-%m-%d %H:%M:%S"), "open": df["open"], "high": df["high"],
                        "low": df["low"], "close": df["close"], "volume": df["volume"]})
    out.to_csv(path, index=False, **kw)


@pytest.fixture(scope="module")
def synth():
    return generate_5m_bars("MNQ", 42, "random_walk")


def test_round_trip_matches_synthetic_exactly(real_dir, synth):
    export(synth, real_dir / "MNQ.csv")
    real = load_real_bars("MNQ", "5m")
    assert len(real) == len(synth)
    for col in ("open", "high", "low", "close", "volume", "tod"):
        assert np.allclose(real[col].to_numpy(), synth[col].to_numpy()), col
    assert (real["date"].to_numpy() == synth["date"].to_numpy()).all()
    assert (real["gen_regime"] == "real").all()


def test_backtest_on_real_path_equals_synthetic_path(real_dir, synth):
    """The same bars must give the same trades whichever way they arrive - no hidden synthetic-only behaviour."""
    export(synth, real_dir / "MNQ.csv")
    kw = dict(strategy="mnq_trend", symbol="MNQ", start_date="2023-01-02", end_date="2023-06-30")
    cfg_s, cfg_r = BacktestConfig(**kw), BacktestConfig(**kw, data_model="real")
    ts = run_backtest(get_market_data("MNQ", 42, "5m", "random_walk"), cfg_s)
    tr = run_backtest(get_market_data("MNQ", 42, "5m", "real"), cfg_r)
    assert len(ts) == len(tr) > 50
    assert [(t["entry_time"], t["net_pnl"], t["regime"]) for t in ts] == [(t["entry_time"], t["net_pnl"], t["regime"]) for t in tr]


def test_one_minute_bars_resample_to_the_same_five_minute_bars(real_dir, synth):
    sample = synth.iloc[78 * 10 : 78 * 13]  # three trading days
    rows = []
    for r in sample.itertuples():
        o, h, l, c, v = r.open, r.high, r.low, r.close, r.volume
        subs = [(o, h, o, o), (o, o, l, o), (o, o, o, o), (o, o, o, o), (o, max(o, c), min(o, c), c)]
        for k, (so, sh, sl, sc) in enumerate(subs):
            rows.append((r.ts + pd.Timedelta(minutes=k), so, sh, sl, sc, v // 5))
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"]).to_csv(real_dir / "MNQ_1m.csv", index=False)
    real = load_real_bars("MNQ", "5m")
    assert len(real) == len(sample)
    for col in ("open", "high", "low", "close"):
        assert np.allclose(real[col].to_numpy(), sample[col].to_numpy()), col
    assert quality_report("MNQ")["source_bar_minutes"] == 1


def test_utc_offsets_convert_to_eastern_across_dst(real_dir):
    # 09:30 ET is 13:30Z in summer (EDT) and 14:30Z in winter (EST)
    rows = []
    for day, hh in (("2023-07-10", 13), ("2023-12-11", 14)):
        for k in range(78):
            m = 30 + 5 * k
            rows.append((f"{day}T{hh + m // 60:02d}:{m % 60:02d}:00Z", 100, 101, 99, 100, 10))
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"]).to_csv(real_dir / "MNQ.csv", index=False)
    df = load_real_bars("MNQ", "5m")
    first = df.groupby("day_id").first()
    assert (first["tod"] == 0).all() and len(df) == 156
    assert any("UTC offset" in i["message"] for i in quality_report("MNQ")["issues"])


def test_bar_end_labels_are_shifted_back(real_dir, monkeypatch):
    monkeypatch.setattr(get_settings(), "real_data_bar_label", "end")
    rows = [(f"2023-03-01 {9 + (35 + 5 * k) // 60:02d}:{(35 + 5 * k) % 60:02d}:00", 100, 101, 99, 100, 10) for k in range(78)]
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"]).to_csv(real_dir / "MNQ.csv", index=False)
    df = load_real_bars("MNQ", "5m")
    assert df["tod"].iloc[0] == 0 and df["tod"].iloc[-1] == 385 and len(df) == 78


def test_outside_regular_hours_and_weekends_are_ignored_and_reported(real_dir):
    rows = [("2023-03-03 08:00:00", 1, 2, 1, 1, 1), ("2023-03-03 09:30:00", 1, 2, 1, 1, 1), ("2023-03-03 16:00:00", 1, 2, 1, 1, 1),
            ("2023-03-04 10:00:00", 1, 2, 1, 1, 1), ("2023-03-03 09:35:00", 1, 2, 1, 1, 1)]
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"]).to_csv(real_dir / "MNQ.csv", index=False)
    quality = quality_report("MNQ")
    assert not quality["ok"]  # a one-day dataset is flagged as an ERROR in the quality report
    assert any(i["severity"] == "error" and "Fewer than 30 trading days" in i["message"] for i in quality["issues"])
    df = load_real_bars("MNQ", "5m")
    assert len(df) == 2 and set(df["tod"]) == {0, 5}
    assert any("outside it" in i["message"] for i in quality_report("MNQ")["issues"])


def test_bad_data_is_reported_never_silently_fixed(real_dir, synth):
    d = synth.iloc[:78 * 40].copy()
    csv = pd.DataFrame({"timestamp": d["ts"].dt.strftime("%Y-%m-%d %H:%M:%S"), "open": d["open"], "high": d["high"],
                        "low": d["low"], "close": d["close"], "volume": d["volume"]})
    csv = pd.concat([csv, csv.iloc[[5, 6]]])  # duplicate rows
    csv.loc[csv.index[10], "high"] = csv.loc[csv.index[10], "low"] - 5  # impossible OHLC
    csv = csv.sample(frac=1, random_state=1)  # unsorted
    csv.to_csv(real_dir / "MNQ.csv", index=False)
    issues = " | ".join(i["message"] for i in quality_report("MNQ")["issues"])
    assert "not in ascending order" in issues and "duplicate timestamps" in issues and "impossible OHLC" in issues


@pytest.mark.parametrize("content,needle", [
    ("timestamp,open,high,low\n2023-01-02 09:30:00,1,2,1\n", "missing required column"),
    ("foo,open,high,low,close\n1,1,2,1,1\n", "No timestamp column"),
    ("timestamp,open,high,low,close\nnot-a-date,1,2,1,1\n", "parse timestamps"),
])
def test_unusable_files_raise_clear_errors(real_dir, content, needle):
    (real_dir / "MNQ.csv").write_text(content)
    rep = quality_report("MNQ")
    assert not rep["ok"] and needle in rep["issues"][0]["message"]
    with pytest.raises(RealDataError, match=needle):
        load_real_bars("MNQ", "5m")


def test_missing_symbol_and_coarse_source_errors(real_dir, synth):
    with pytest.raises(RealDataError, match="No real data found for MES"):
        load_real_bars("MES", "5m")
    d = synth.iloc[::3].copy()  # 15-minute spacing
    export(d, real_dir / "MNQ.csv")
    with pytest.raises(RealDataError, match="15-minute bars but a 5m backtest"):
        load_real_bars("MNQ", "5m")


def test_api_gives_helpful_errors_and_events_need_an_official_calendar(client, real_dir, synth):
    cfg = {"strategy": "mnq_trend", "symbol": "MNQ", "data_model": "real"}
    r = client.post("/api/backtest/run", json={"config": cfg})
    assert r.status_code == 422 and "No real data found" in r.json()["detail"]
    export(synth.iloc[78 * 250 : 78 * 560], real_dir / "MNQ.csv")  # roughly 2023-ish onward
    span = quality_report("MNQ")
    cfg_bad = {**cfg, "start_date": "2022-01-03", "end_date": "2022-02-01"}
    r2 = client.post("/api/backtest/run", json={"config": cfg_bad})
    assert r2.status_code == 422 and "dataset spans" in r2.json()["detail"]
    ok = {**cfg, "start_date": span["start"], "end_date": span["end"]}
    r3 = client.post("/api/backtest/run", json={"config": ok, "name": "real csv"})
    assert r3.status_code == 200, r3.text
    bid = r3.json()["id"]
    assert "REAL data" in client.get("/api/experiments").json()[-1]["dataset"]
    ev = client.get(f"/api/backtests/{bid}/analytics/events").json()
    assert ev["rows"] == [] and "events.csv" in ev["note"]  # the sample calendar is never used on real data
    pd.DataFrame({"date": ["2024-02-14", "2024-03-20"], "event": ["CPI", "FOMC"], "time": ["08:30", "14:00"]}).to_csv(real_dir / "events.csv", index=False)
    ev2 = client.get(f"/api/backtests/{bid}/analytics/events").json()
    assert "events.csv" in ev2["note"] and any(r["event"] == "CPI" for r in ev2["rows"])
    client.delete(f"/api/backtests/{bid}")
