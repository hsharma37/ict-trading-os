# Deployment Runbook

TradingOS should use a protected production branch and a separate integration branch.

```text
feature/* -> dev -> main
              |      |
              |      production Vercel URL
              dev/staging Vercel URL
```

## Branches

- `main`: production only. Deploys to production Vercel projects.
- `dev`: integration/staging. Deploys to dev Vercel projects.
- `feature/*`: short-lived branches opened into `dev`.

Before merging `dev` into `main`, run:

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
.venv/bin/python -m pytest -q
```

## Recommended Vercel Projects

Use two projects while the app is still stabilizing:

| Surface | Branch | Vercel project | Stable URL |
| --- | --- | --- | --- |
| Frontend production | `main` | `ict-trading-os-frontend-prod` | `https://app.yourdomain.com` |
| Frontend dev | `dev` | `ict-trading-os-frontend-dev` | `https://dev.yourdomain.com` |
| API production | `main` | `ict-trading-os-api-prod` | `https://api.yourdomain.com` |
| API dev | `dev` | `ict-trading-os-api-dev` | `https://api-dev.yourdomain.com` |

Vercel production deployments should track `main`. Preview/dev deployments should track `dev` or feature branches.

## Environment Separation

Configure environment variables in Vercel instead of committing them in `vercel.json`.

- Production API: use `.env.production.example` as the checklist.
- Dev/API preview: use `.env.preview.example` as the checklist.
- Frontend production: set `VITE_API_URL=https://api.yourdomain.com`.
- Frontend dev: set `VITE_API_URL=https://api-dev.yourdomain.com`.

Use different API keys, JWT secrets, databases, storage buckets, Telegram channels, and MT5 bridge settings for dev and production.

The current frontend does not implement a private session or backend-for-frontend auth proxy. If you set `AUTH_ENABLED=true` today, normal frontend API calls will be rejected unless the client is updated to authenticate safely. Do not put a raw production API key into public Vite client code.

## Durable Storage

The active Vercel backend must use Postgres for KB and trading state. Configure a separate `DATABASE_URL` for preview/staging and production, and apply:

```bash
psql "$DATABASE_URL" -f migrations/001_postgres_pgvector_foundation.sql
```

Use a provider that supports pgvector, such as Neon, Supabase, or a managed Postgres where `CREATE EXTENSION vector` is available. If pgvector is not enabled yet, the app can still store JSONB documents in Postgres, but semantic KB search falls back to the in-process scorer until the extension is available.

The Vercel entrypoint no longer defaults the database to `/tmp`. Production, preview, and Vercel runtimes refuse SQLite unless `ALLOW_SQLITE_RUNTIME=true` is explicitly set for a temporary smoke test. Never use that override for private KB, trade plans, journals, or execution state.

## CLI Setup

After logging in with `npx vercel login`, link each local checkout/project intentionally:

```bash
# API production project
npx vercel link --project ict-trading-os-api-prod
npx vercel --prod

# API dev project or dev checkout
npx vercel link --project ict-trading-os-api-dev
npx vercel

# Frontend production project
cd frontend
npx vercel link --project ict-trading-os-frontend-prod
npx vercel --prod

# Frontend dev project
npx vercel link --project ict-trading-os-frontend-dev
npx vercel
```

Add domains from the Vercel dashboard or CLI once authenticated:

```bash
npx vercel domains add app.yourdomain.com
npx vercel domains add dev.yourdomain.com
npx vercel domains add api.yourdomain.com
npx vercel domains add api-dev.yourdomain.com
```
