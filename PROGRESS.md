# ICT Trading OS — Progress Tracker & Improvement Plan

> Generated 2026-07-14 from a full-repo scan + doc review + live deploy verification.
> Reconciles the planning docs (`MIGRATION_ROADMAP.md`, `docs/PRODUCT_DIRECTION_AND_BATCHES.md`,
> `CODE_REVIEW_BUG_REPORT.md`) against the **actual current code and the live Vercel deployment**.

## Live status (verified 2026-07-14)

Production is **up and healthy** at **https://ict-trading-os.vercel.app** (alias `ict-trading-os-rho.vercel.app`).

| Check | Result |
|---|---|
| `GET /api/health` | `200` — `backend: postgres`, `durable: true`, `pgvector: true` |
| `GET /` (SPA) | `200 text/html` |
| `GET /dashboard` (SPA deep link) | `200` → index.html (client routing works) |
| `GET /assets/*.js` (static) | `200 application/javascript` (correct MIME) |
| `GET /api/market/price/EURUSD` (live data) | `200` |
| Data in prod DB | 1 KB source, 58 chunks, 1 trade |

The SPA-vs-API routing problem (the subject of the last ~12 commits) is **resolved**: Vercel serves
static files from `public/`, falls back to the FastAPI catch-all for SPA routes, and `/api/*` reaches
the Python function which strips the `/api` prefix.

## Architecture reality: three stacked generations

| Gen | What | State |
|---|---|---|
| 0 | `ICT_Trading_OS_v7.html` + `server.js` (Node) + `lib/*.js` | **Legacy** — superseded, mostly dead |
| 1 | `app/` (FastAPI + SQLite/Postgres) + `frontend/` (React/Vite) via `api/index.py` | **DEPLOYED** — this is production |
| 2 | `backend/` (FastAPI + Postgres/pgvector + Redis + Celery + Alembic) via `docker-compose.yml` | **Dormant** — target rewrite, not deployed, no tests |

The frontend (`frontend/src/api/client.ts`) is wired to **Gen 1** (`app/`) bare-prefix routes, not
`backend/`'s `/api/v1/*` scheme.

## Reconciled progress vs. product tracker

Updates the table in `docs/PRODUCT_DIRECTION_AND_BATCHES.md` (was dated 2026-07-02):

| Area | Doc said | Verified now | Notes |
|---|---:|---|---|
| Deployment & CI/CD | 80% | **~90%** | Live prod + aliases; SPA/API routing solved; CI runs pytest + lint + typecheck + build |
| Durable storage | 70% | **~75%** | Prod on Postgres + pgvector, confirmed via `/api/health` |
| Production safety (Batch 1) | — | **~mostly done** | JWT/API_KEY fail-closed at startup; auth middleware active in prod |
| Trade ledger correctness (Batch 2) | 35% | **~partial-done** | `Decimal` money math + side-aware SL/TP validation landed; concurrency locking still to verify |
| Knowledge base | 55% | 55% | Ingestion/search/pgvector exist; async + citations pending |
| Trading planner | 45% | 45% | Plan APIs exist; UI not persisted (see below) |
| Journal & analytics | 40% | 40% | Analytics routes exist; Journal/Plan pages are pure UI |
| ML/agent pipeline | 25% | 25% | Heuristic analysis + retrieval; no eval/hallucination gate |
| Security/collab readiness | 35% | 35% | Env separation + API key; no real per-user auth |

## Improvement plan (prioritized)

### P0 — verify the remaining CRITICALs from the bug report are actually fixed
The bug report (`CODE_REVIEW_BUG_REPORT.md`) predates recent work. Confirmed **fixed**: #3 (Decimal),
#4 (SL side validation), #5 (JWT default). **Still verify / likely open:**
- #2 concurrent partial/full close has no locking → add row-level lock or optimistic concurrency.
- #7 MT5 proxy accepts arbitrary trade commands → add symbol whitelist, lot caps, approval token.
- #8 two different Kelly implementations (`trade_lifecycle_service` vs `quant_service`) → unify.
- #9 price timestamp format inconsistency (float vs ISO) → standardize to UTC ISO.

### P1 — structural: collapse the parallel backends
Carrying both `app/` (shipping) and `backend/` (dormant) doubles maintenance and confuses newcomers.
**Decide one:**
- (a) Delete/archive `backend/` until the migration is actually resourced, **or**
- (b) Commit to finishing the `backend/` migration and point the frontend at `/api/v1/*`.
Recommendation: (a) for now — keep the repo honest about what ships.

### P2 — dead code & repo hygiene
- `start_backend.py:6` hardcodes `os.chdir('/Users/hsharma5/Documents/Kimi/.../ict-trading-os')` — a
  path that doesn't exist in this checkout. Fix to a relative/`__file__`-based path or delete the script.
- `server.js` routes `/api/market/*` to `./api/market/*.js` handlers that were deleted — dead Gen-0 code.
- `lib/*.js` and `ICT_Trading_OS_v7.html` are superseded by `app/` — move to an `legacy/` folder or remove.

### P3 — build/deploy robustness
- `vercel.json` `buildCommand` only does `cp -r frontend/dist/* public/` — it **does not build** the
  frontend, relying on a committed `frontend/dist`. A stale commit ships stale UI. Prefer building on
  Vercel: `cd frontend && npm ci && npm run build && cp -r dist/* ../public/`.
- Frontend bundle is a single **875 KB** chunk → code-split (route-level `lazy()`), which also removes
  the Vite dynamic/static import warning for `client.ts`.
- `frontend/src/hooks/useMarketData.ts` (currently modified in the working tree) reads
  `(globalThis as any)?.import?.meta?.env` — that expression is always `undefined`, so `VITE_API_URL`
  is never honored (harmless in prod where `/api` is the default, but it's broken code). Use
  `import.meta.env.VITE_API_URL` like `client.ts` does.

### P4 — product integration gaps (from bug report, high user value)
- Journal page (`frontend/src/pages/Journal.tsx`) and Plan page (`Plan.tsx`) are **pure UI** — no
  persistence. Wire them to the plans/journal APIs.
- Analytics "auto-journal" button never saves (bug #39).
- Settings theme toggle is a no-op (bug #37) — no dark-mode class wiring.

### P5 — testing & CI depth
- `app/` has a real pytest suite; `backend/` has **zero** tests. If `backend/` stays, it needs coverage.
- Add a post-deploy smoke check (curl `/api/health` + one data route) to CI, per Batch 0.

## Deployment runbook (confirmed working)

```bash
# One-time: linked already (.vercel/project.json). Env vars set in Vercel Production:
#   API_KEY, JWT_SECRET, DATABASE_URL, APP_ENV, CORS_ORIGINS, LOG_LEVEL, ALLOW_SQLITE_RUNTIME
npm --prefix frontend run build      # produces frontend/dist (committed, copied to public/ on Vercel)
vercel --prod --yes                  # deploy; aliases to ict-trading-os.vercel.app
curl -s https://ict-trading-os.vercel.app/api/health   # verify
```
