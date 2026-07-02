# Deployment Runbook

TradingOS should use a protected production branch and a separate integration branch.

```text
feature/* -> dev -> main
              |      |
              |      production Vercel URL
              dev/staging Vercel URL
```

## Branches

- `main`: production only. Deploys to the production Vercel URL.
- `dev`: integration/staging. Deploys to Vercel preview/dev URLs.
- `feature/*`: short-lived branches opened into `dev`.

Before merging `dev` into `main`, run:

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
.venv/bin/python -m pytest -q
```

## Recommended Vercel Setup

Use one Vercel project for the app while the product is still stabilizing. The root project builds the React frontend and exposes FastAPI under `/api/*`.

| Surface | Branch | URL shape |
| --- | --- | --- |
| Production app | `main` | `https://ict-trading-os.vercel.app` or custom domain |
| Preview/dev app | `dev` | Vercel branch preview URL |
| API | same deployment | `/api/*` rewrites to FastAPI |

Vercel production deployments should track `main`. Preview/dev deployments should track `dev` or feature branches. Pushing to either branch triggers CI/CD through the GitHub integration.

## Environment Separation

Configure environment variables in Vercel instead of committing them in `vercel.json`.

- Production: use `.env.production.example` as the checklist.
- Dev/preview: use `.env.preview.example` as the checklist.
- Frontend production: set `VITE_API_URL=/api`, or omit it because the frontend defaults to `/api` in production.
- Frontend dev/preview: set `VITE_API_URL=/api`, or omit it for the same-domain preview API.

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

After logging in with `npx vercel login`, link this checkout to the app project:

```bash
# Production deploy from main
npx vercel link --project ict-trading-os
npx vercel --prod

# Preview deploy from dev/current branch
npx vercel
```

Add domains from the Vercel dashboard or CLI once authenticated:

```bash
npx vercel domains add app.yourdomain.com
npx vercel domains add dev.yourdomain.com
```
