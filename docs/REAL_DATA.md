# Using your own market data

The synthetic markets exist so the platform works out of the box. **They cannot tell you whether a strategy will make money in real markets.** To judge a strategy you intend to trade, run it on real data.

## 1. Put CSV files in `backend/data/real/`

(The folder is git-ignored so your data is never committed. Change it with `REAL_DATA_DIR`.)

* One or more files per symbol; the file name must start with the symbol: `MNQ.csv`, `MNQ_1m.csv`, `MNQ_2023.csv`, `MES.csv` ... Multiple files for a symbol are concatenated and de-duplicated.
* Required columns (case-insensitive): a timestamp (`timestamp`, `datetime`, `date_time` or `time`; or separate `date` and `time` columns), `open`, `high`, `low`, `close`. Optional: `volume`.
* **Bars:** 1-minute or 5-minute source data for a 5m backtest; 1-, 5- or 15-minute for a 15m backtest. Finer data is resampled (open=first, high=max, low=min, close=last, volume=sum). A 15-minute source cannot serve a 5-minute backtest.

```csv
timestamp,open,high,low,close,volume
2024-03-18 09:30:00,18012.25,18018.00,18009.50,18015.75,1432
2024-03-18 09:31:00,18015.75,18016.50,18012.00,18013.25,987
```

## 2. Conventions (stated, never guessed)

| Topic | Rule |
|---|---|
| Timezone | Timestamps without an offset are read as `REAL_DATA_TZ` (default `America/New_York`) and converted to US/Eastern. Timestamps with an offset (`...Z`, `+00:00`) are converted to Eastern. |
| Bar label | A timestamp is the bar's **start** time. If your vendor stamps the bar **end**, set `REAL_DATA_BAR_LABEL=end`. Getting this wrong shifts every signal by one bar - check it. |
| Sessions | Only regular trading hours **09:30-16:00 ET, Mon-Fri** are used. Everything else is ignored (and counted in the report). |
| Early closes | Days with fewer bars are kept but flagged; the engine flattens at each day's last bar. |
| Contract rolls | Use **back-adjusted continuous contracts**. Un-adjusted rolls create fake overnight jumps (flagged above 4%) that distort ATR/VWAP warm-up. |

## 3. Data-quality report

Every dataset gets a report (Configuration → Data, and `GET /api/meta` → `real_data`). It lists files, bar size, bars/days, date range and any of: unsorted rows, duplicate timestamps, impossible OHLC values (dropped), zero-volume bars, days with missing bars, intraday gaps, suspected contract rolls, and datasets shorter than a year. **Nothing is repaired silently**; read the report before trusting results.

## 4. Run a backtest on it

Configuration → Data → *Market model* → **Real data (your CSV)**, set dates inside the dataset's range. Experiments record the data files used. Indicators warm up from the first bar in the file, so start the backtest at least a month after the data begins; ML strategies train only on bars before the start date, so leave plenty of history.

## 5. Macro events

The built-in event calendar is a **sample** and is never applied to real data. To enable event analysis, add `events.csv` with columns `date,event[,time]` (time = release time in ET, default 08:30) from an official calendar.

## 6. What honest real-data results still cannot tell you

Bar-level fills (no queue position or partial fills), future liquidity, regime change, and the selection bias from trying many variants. See the **Deployment readiness** checklist on the Overfitting page: it never says "go live", only whether a strategy has cleared the checks that make it worth **paper trading**.
