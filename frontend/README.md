# Frontend

Next.js (App Router) + TypeScript + Tailwind CSS. See the [root README](../README.md) for the full setup, environment variables and deployment steps.

```powershell
npm install
Copy-Item .env.example .env.local     # set NEXT_PUBLIC_API_URL
npm run dev                            # http://localhost:3000
npm run lint ; npm run typecheck ; npm run build
```

* `app/` - one route per page (dashboard, backtest, analysis, robustness, risk, prop, research)
* `components/` - `ui/` primitives, `charts/`, `layout/`, `metrics/`, `tables/`, `forms/`, `prop/`, `backtest/`
* `lib/` - API client (`api.ts`), shared types (`types.ts`, `types-api.ts`), hooks, formatting

The backend URL comes only from `NEXT_PUBLIC_API_URL` (`lib/config.ts`). Public env vars are compiled into the build, so changing it on Vercel requires a redeploy.
