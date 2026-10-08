# Quant Backtester

A full-stack **futures strategy backtesting and robustness platform** (MNQ / NQ / MES / ES): Python backtest engine, Monte Carlo, walk-forward testing, parameter sensitivity, prop-firm challenge simulation, strategy comparison, and a **Strategy Lab** where you can paste your own Python (including machine-learning) strategies.

> **Honest by design.** This tool exists to tell you the truth about a strategy, not to flatter it. The default demo market is a pure **random walk with no edge**, so most strategies are *expected to lose* after costs. Costs are charged on every fill, results carry a significance test, optimisation is labelled in-sample, and scores are capped for strategies with no proven edge. See [docs/QUANT_ASSUMPTIONS.md](docs/QUANT_ASSUMPTIONS.md).

```
Browser ──► Next.js (Vercel) ──HTTP/JSON──► FastAPI (Railway / Render) ──► PostgreSQL
              frontend/                        backend/
```

## What it does

| Area | Pages |
|---|---|
| **Backtest** | Configuration (all strategy / risk / stop / target / management / execution settings, presets) · Trade Explorer (sort, filter, CSV, per-trade candlestick viewer) · Equity curve (net / gross / long / short / benchmark, version overlays) · Drawdowns |
| **Analysis** | Performance (27 KPIs, calendar heatmap, monthly matrix, long vs short) · Time analysis (time-of-day, weekday, heatmap) · MFE/MAE scatter · Regimes, volatility & macro events · Distributions & streaks |
| **Robustness** | Monte Carlo (reshuffle / bootstrap / block bootstrap) · Walk-forward with IS-vs-OOS · Parameter sensitivity & stability score · Stress tests (slippage, commissions, missed trades, outliers) · Strategy score, robustness score, overfitting detector, automated warnings |
| **Risk** | Position sizing · Risk of ruin · Losing streaks · Risk-per-trade optimiser |
| **Prop firms** | Fully configurable rule engine (static / EOD-trailing / intraday-trailing drawdown, daily loss, consistency, min days, payouts…) · Challenge simulator · Pass probability · Funded-account survival · Payout simulator · Risk optimiser |
| **Research** | Strategy comparison, weighted combinations, correlation matrices · **Strategy Lab (your Python / ML code)** · Experiment tracking (BT-000001…) · Saved strategies · Printable / downloadable reports |

## Tech stack

* **Frontend:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn-style Radix components, Recharts, TanStack Table & Query
* **Backend:** Python 3.12, FastAPI, Pydantic v2, pandas, NumPy, SciPy, SQLAlchemy 2
* **Database:** SQLite locally, PostgreSQL in production (`DATABASE_URL`)

## Repository layout

```
.
├── README.md  .env.example  .gitignore  render.yaml
├── docs/                      QUANT_ASSUMPTIONS.md · STRATEGY_LAB.md
├── .github/workflows/ci.yml   backend tests + frontend lint/typecheck/build
├── docker-compose.yml         optional: Postgres + backend + frontend in containers
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, CORS, startup seeding
│   │   ├── api/               routers: backtests, simulations, prop, risk, research, custom, meta
│   │   ├── backtesting/       engine, market data/indicators, strategies/ (plug-ins)
│   │   ├── quant/             metrics, drawdown, Monte Carlo, ruin, stress, scores, analysis
│   │   ├── optimization/      parameter grid + stability, walk-forward
│   │   ├── prop_firm/         rule evaluator, vectorised Monte Carlo, optimiser
│   │   ├── custom/            sandboxed user-code runner (Strategy Lab)
│   │   ├── data/              deterministic synthetic market data, sample event calendar
│   │   ├── models/            Pydantic models
│   │   └── services/          orchestration, persistence, seeding
│   ├── tests/                 pytest suite (metrics, MC, prop rules, API, lookahead, honesty, sandbox)
│   ├── requirements.txt  requirements-dev.txt  requirements-ml.txt
│   └── Procfile  railway.json  Dockerfile
└── frontend/
    ├── app/                   one route per page (29 routes)
    ├── components/            ui/ charts/ layout/ metrics/ tables/ forms/ prop/ backtest/
    ├── lib/                   api client, types, hooks, formatting
    └── vercel.json  package.json
```

## Quick start (local)

Prerequisites: **Python 3.12+**, **Node.js 20+**, **Git**.

### 1. Backend (terminal 1)

PowerShell (Windows):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item ..\.env.example .env       # then edit backend/.env (see Environment variables)
uvicorn app.main:app --reload
```

macOS / Linux:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload
```

The API is now at <http://localhost:8000> (interactive docs at `/docs`). On the **first start** it seeds five demo backtests (takes ~10–20 seconds, once).

> The entry point is `app.main:app` (module `app.main`, object `app`). Production command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

### 2. Frontend (terminal 2)

```powershell
cd frontend
npm install
Copy-Item ..\.env.example .env.local   # keep only the NEXT_PUBLIC_API_URL line
npm run dev
```

Open <http://localhost:3000>. 

### Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | frontend | Base URL of the backend, e.g. `http://localhost:8000` or `https://your-api.onrender.com` (no trailing slash). A localhost fallback exists **only in development**; a production build without it shows a configuration error. |
| `DATABASE_URL` | backend | `sqlite:///./quant.db` (default) or a PostgreSQL URL. `postgres://` and `postgresql://` are normalised automatically. |
| `ALLOWED_ORIGINS` | backend | Comma-separated browser origins allowed by CORS, e.g. `http://localhost:3000,https://your-app.vercel.app`. No wildcard is ever used. |
| `ALLOWED_ORIGIN_REGEX` | backend | Optional regex for Vercel preview URLs, e.g. `^https://your-app-.*\.vercel\.app$`. |
| `ENABLE_CUSTOM_CODE` | backend | `true` enables the Strategy Lab (runs pasted Python). **Off by default.** See Security. |
| `CUSTOM_CODE_TOKEN` | backend | If set, Strategy Lab endpoints require header `X-Admin-Token`. |
| `CUSTOM_CODE_TIMEOUT` | backend | Seconds allowed per sandbox run (default 180). |
| `SEED_DEMO_DATA` | backend | `false` to skip creating the demo backtests on an empty database. |
| `GIT_COMMIT` | backend | Recorded on each experiment; auto-detected from git if available. |

Never commit real values. `.env`, `.env.local` and `*.db` are git-ignored; `.env.example` documents everything.

## Running tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q
```

~110 tests cover: profit factor, expectancy, Sharpe, Sortino, drawdown, streaks (hand-computed expected values); Monte Carlo reproducibility; prop-firm pass/fail logic for each drawdown type; **no-lookahead tests** (truncating the future must not change any earlier indicator, signal or trade); **honesty tests** (no edge on a random walk, costs always hurt, scores capped); the API; and the sandbox.

Frontend checks:

```powershell
cd frontend
npm run lint ; npm run typecheck ; npm run build
```

## Strategy Lab: paste your own Python / ML strategies

1. Set `ENABLE_CUSTOM_CODE=true` in `backend/.env`, restart the backend. For ML install the extras: `pip install -r requirements-ml.txt`.
2. Open **Research → Strategy Lab**, start from a template, paste/edit your class, **Validate**, then **Save & run backtest**.
3. Your class defines `signals(self, bars)` (and optionally `fit(self, train_bars)` for models trained *only on data before the test window*). See [docs/STRATEGY_LAB.md](docs/STRATEGY_LAB.md).

Every custom run gets an automatic **lookahead check** (the data is truncated at five points; a causal strategy reproduces its earlier signals exactly).

### Security: read this before enabling custom code

Pasted code is **arbitrary code execution** on the backend host. It runs in a separate subprocess with a scrubbed environment (no `DATABASE_URL`/secrets), an import allow-list, no `open`/`eval`/`exec`, and a timeout, but **Python cannot be perfectly sandboxed**. Therefore: keep it off on public deployments; enable it on your own machine; if you host it, restrict network access and set `CUSTOM_CODE_TOKEN`; never expose it to people you do not trust.

## Using your own market data later

Data enters through one function, `load_bars()` in `backend/app/data/synthetic.py`, returning the columns in `BAR_COLUMNS` (timestamp, OHLCV, session minute, day id). Replace it with a loader for your MNQ/MES history and everything else (engine, analytics, robustness, prop simulation) keeps working. Regimes are always re-derived causally from price. Built-in strategies live in `backend/app/backtesting/strategies/`; add a class and register it in `__init__.py`.

## GitHub workflow

```powershell
git clone https://github.com/<you>/<repo>.git
cd <repo>
git checkout -b feat/my-change
# ...edit...
git add -A
git commit -m "feat: describe the change"
git push -u origin feat/my-change     # then open a Pull Request
```

CI (`.github/workflows/ci.yml`) runs backend tests and frontend lint / typecheck / build on every push and PR.

## Deployment

### 1. Database (PostgreSQL)

Add a hosted Postgres (Railway "PostgreSQL" plugin, Render Postgres, Neon, Supabase…). Copy its connection string into the backend's `DATABASE_URL`. Tables are created automatically on startup. **Without Postgres, SQLite lives on the host's ephemeral disk and demo data is re-seeded on every restart.**

### 2. Backend → Render (or Railway)

**Render** (blueprint): New → *Blueprint* → pick this repo; it reads `render.yaml` at the repo root (web service rooted at `backend/` + free Postgres). Or manually: New Web Service, **Root directory** `backend`, **Build** `pip install -r requirements.txt`, **Start** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set:

* `DATABASE_URL` (from the Postgres instance)
* `ALLOWED_ORIGINS=https://<your-vercel-domain>`

**Railway:** New Project → Deploy from GitHub, set **Root Directory** to `backend` (it uses `railway.json`/`Procfile`), add the PostgreSQL plugin, then set `DATABASE_URL=${{Postgres.DATABASE_URL}}` and `ALLOWED_ORIGINS`.

Check `https://<backend>/api/health` returns `{"status":"ok"}`.

### 3. Frontend → Vercel

1. Vercel → *Add New Project* → import the GitHub repo.
2. **Root Directory:** `frontend` (framework preset: Next.js is auto-detected).
3. **Environment variable:** `NEXT_PUBLIC_API_URL=https://<your-backend-url>` (no trailing slash).
4. Deploy. Then add the Vercel domain to the backend's `ALLOWED_ORIGINS` and redeploy the backend.

### Changing the backend URL later

Update `NEXT_PUBLIC_API_URL` in Vercel and **redeploy** (public env vars are baked in at build time). Update `ALLOWED_ORIGINS` on the backend if the frontend domain changed.

### CORS notes

CORS is restricted to the origins you list. For Vercel preview deployments use `ALLOWED_ORIGIN_REGEX`. Never use `*` in production.

### Docker (optional)

```bash
docker compose up --build        # Postgres + backend :8000 + frontend :3000
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Frontend says "Cannot reach the backend" | Is the backend running? Does `NEXT_PUBLIC_API_URL` match it? Is the frontend origin in `ALLOWED_ORIGINS`? (Browser console shows CORS errors.) |
| "Backend URL not configured" on Vercel | Set `NEXT_PUBLIC_API_URL` and redeploy. |
| `uvicorn: Error loading ASGI app` | Run from the `backend/` folder and use `app.main:app`. |
| First backend start is slow | It is seeding demo backtests (once). |
| Render/Railway lose data | Using SQLite on ephemeral disk - set `DATABASE_URL` to Postgres. |
| `ModuleNotFoundError: sklearn` in the Strategy Lab | `pip install -r requirements-ml.txt`. |
| Strategy Lab says it is disabled | Set `ENABLE_CUSTOM_CODE=true` (local use only) and restart. |
| PowerShell blocks `Activate.ps1` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. |
| Port already in use | `uvicorn app.main:app --port 8001` and update `NEXT_PUBLIC_API_URL`. |

## Limitations (please read)

* The demo data is **synthetic**. Nothing here is evidence of live profitability, and no tool can promise it.
* Fills are modelled at bar level (no order book, queue position or partial fills). Real execution is usually worse; use the stress tests.
* Monte Carlo and prop simulations resample the trades/days a backtest already produced - they quantify path luck, not whether the edge is real.
* Intraday prop-firm rules are evaluated from daily records extended by MAE/MFE; verify against your firm's exact rules.
* The sample event calendar is approximate, not an official schedule.
