# ICT Trading OS — Progress Tracker & Improvement Plan

> Generated 2026-07-14 from a full-repo scan + doc review + live deploy verification.
> Reconciles the planning docs (`MIGRATION_ROADMAP.md`, `docs/PRODUCT_DIRECTION_AND_BATCHES.md`,
> `CODE_REVIEW_BUG_REPORT.md`) against the **actual current code and the live Vercel deployment**.

> **Feature trust ratings:** see [`FEATURE_ASSESSMENT.md`](FEATURE_ASSESSMENT.md) for an honest,
> real-money-grade "how much can I trust this?" breakdown of every feature + a prioritized
> improvement roadmap.

## Shipped since (safety, trust & validation cycle — 2026-07-16)

- **Execution safety:** scale-out is opt-in (killed a double/triple-order bug), XAUUSD lot
  oversizing fixed, non-idempotent order retries removed (no double close/partial), bridge-health
  gating **blocks orders when the feed is offline/stale**, and every market order does an
  independent **read-back from MT5** ("Confirmed in MT5: ticket #…").
- **Trust integrity:** fabricated fallback candles are flagged; research/signals **refuse or clearly
  label** simulated data instead of showing invented levels; heuristics (news sentiment, signal
  confidence) are honestly labelled; Telegram **won't auto-trade a guessed stop-loss**.
- **Data bug:** Yahoo candle fetch used `period=` (ignored) → ~14 candles → HTF bias always NEUTRAL,
  SMAs null, 2R never viable. Fixed to `range=` → full history; bias/SMA/levels now real.
- **R & analytics:** editable per-instrument lot→$ risk calibration (Settings); money stats
  normalized per standard lot.
- **Research validation suite:** backtest (walk-forward, no look-ahead) + Monte Carlo (risk of ruin)
  + parameter sweep (with out-of-sample column) + honest walk-forward test + **live paper-forward
  test**. Verdict: the ICT signal has **no edge at 2R**, a **thin filter-dependent edge at ~3R**
  that held out-of-sample on GBPUSD/EURUSD — a candidate to forward-test, not a proven system.
- **Feed curation:** discard/keep for Telegram posts and trade plans; Signals page reorganised.

## Live status (verified 2026-07-15)

Production is **up and healthy** at **https://ict-trading-os-rho.vercel.app**.

| Check | Result |
|---|---|
| `GET /` (SPA) + `/assets/*.js` | `200` — bundle resolves (blank-screen class of bug fixed) |
| `GET /api/health` | `200` — `backend: postgres`, `durable: true`, `pgvector: true` |
| MT5 bridge | `reachable: true`, `mt5_connected: true` (Cloudflare quick tunnel) |
| Order readiness (`/api/mt5/order-check`) | EURUSD `ok: true` (would fill) — no trade placed |
| Price feed (`/api/market/prices`) | 6 symbols, **all `source: mt5`** |
| Trades base (`/api/trades/stats/summary`) | `source: mt5` — real broker P&L |
| Telegram poll (`/api/telegram/poll-source`) | `ok` — channel `xxictxx`, 17 msgs scanned |
| Knowledge chat | account-aware (`source: mt5_account`) |

## Shipped this cycle (MT5-first trading loop)

- **MT5 is the base for all trade data.** When the bridge is connected, Dashboard KPIs,
  Analytics, the chatbot, and signals/research read the **real broker account** (positions,
  closed history, balance) via `app/services/mt5_trades_service.py`, reshaped into the existing
  stats schema; the internal ledger is the automatic fallback. "Live · MT5" badges surface it.
- **Execution Console places real MT5 orders.** Market + pending (limit/stop) from the Execute
  page, lot auto-sized from balance × risk % (auto-resolved on send), SL/TP attached; live
  positions with **close / partial-close / modify-SL-TP** embedded below the form.
- **Order reliability fixes:** the bridge auto-selects a **supported filling mode** (FOK/IOC/
  RETURN) — the demo broker is FOK-only, which was silently rejecting IOC orders. Broker/bridge
  errors now propagate as real HTTP errors (no more false "order sent"), with plain-English help
  (e.g. AutoTrading-disabled → "press Ctrl+E"). New `POST /mt5/order-check` validates an order
  **without placing it** for safe diagnosis.
- **Editable bridge URL** (Settings → MT5 Bridge Connection): paste a new quick-tunnel URL,
  stored in the DB, effective immediately — no Vercel env change or redeploy.
- **Symbols limited to the 6 broker-tradeable instruments** (EURUSD, GBPUSD, USDJPY, AUDUSD,
  NZDUSD, XAUUSD) app-wide, from one `instrument_config` source; the price feed rejects anything
  off-list.
- **Telegram public-channel polling** of `@xxictxx` via `t.me/s/<channel>` (no bot/credentials):
  parses posts → signals, deduped, in the feed. Hourly via the always-on bridge (`APP_BASE_URL`)
  or a daily Vercel cron fallback (`/api/telegram/poll-source`).
- **KB auto-transcribe via the residential bridge** (`/transcript`, `/video-meta`) — YouTube
  blocks cloud IPs.
- **Deploy robustness:** `buildCommand` now cleans `public/` before copying `dist` (fixes the
  stale-asset blank screen). SPA-vs-API routing remains solved (static `public/` + FastAPI
  catch-all + `/api` prefix strip).

## Known manual step (not code)

Placing live orders requires **Algo Trading enabled in the MT5 desktop terminal** (Ctrl+E). This
is a MetaQuotes safety switch that no API can toggle; the app now reports it clearly when off.

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
| Deployment & CI/CD | 80% | **~95%** | Live prod; SPA/API routing solved; self-cleaning build fixes stale-asset blank screen |
| Durable storage | 70% | **~75%** | Prod on Postgres + pgvector, confirmed via `/api/health` |
| Production safety (Batch 1) | — | **done** | JWT/API_KEY fail-closed; auth middleware active; MT5 guardrails (allow-list, lot caps, side-aware SL/TP, audit) |
| Real execution (MT5) | — | **~90%** | Real orders/close/partial/modify/pending; filling-mode + error surfacing fixed; blocked only by terminal Algo-Trading toggle |
| Live market data | — | **done** | Single resolver; MT5 broker feed; 6-symbol allow-list; source/staleness transparency |
| Trades analytics base | 40% | **~85%** | Dashboard + Analytics read the live MT5 terminal (broker P&L/history), ledger fallback |
| Knowledge base | 55% | **~70%** | Ingest/search/pgvector; YouTube transcribe+titles via residential bridge; chat is account-aware |
| Telegram | — | **~80%** | App feed + bridge notifications + public-channel hourly polling (@xxictxx) |
| Trading planner | 45% | 45% | Plan APIs exist; UI not persisted |
| ML/agent pipeline | 25% | 25% | Heuristic analysis + retrieval; no eval/hallucination gate |
| Security/collab readiness | 35% | 35% | Env separation + API key; no real per-user auth |

## Improvement plan (prioritized)

### P0 — verify the remaining CRITICALs from the bug report are actually fixed
The bug report (`CODE_REVIEW_BUG_REPORT.md`) predates recent work. Confirmed **fixed**: #3 (Decimal),
#4 (SL side validation), #5 (JWT default), **#7 (MT5 proxy now enforces a symbol allow-list, lot
caps, side-aware SL/TP, and audit logging via `mt5_guard`)**. **Still verify / likely open:**
- #2 concurrent partial/full close has no locking → add row-level lock or optimistic concurrency.
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
- **Done:** `buildCommand` now `rm -rf public/assets public/index.html` before copying `dist`, so a
  deploy can't serve a stale index.html/asset pair (that was the blank-screen root cause). It still
  relies on a **committed `frontend/dist`** (no `npm build` on Vercel) — remember to `npm --prefix
  frontend run build` before committing UI changes. Building on Vercel is still the more robust
  long-term option.
- Frontend bundle is a single **~910 KB** chunk → code-split (route-level `lazy()`), which also
  removes the Vite dynamic/static import warning for `client.ts`.
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
#   API_KEY, JWT_SECRET, DATABASE_URL, APP_ENV, CORS_ORIGINS, LOG_LEVEL, ALLOW_SQLITE_RUNTIME,
#   MARKET_DATA_PROVIDER=mt5, MT5_BRIDGE_URL, MT5_BRIDGE_API_KEY, TELEGRAM_SOURCE_CHANNEL
npm --prefix frontend run build      # produces frontend/dist (committed, copied to public/ on Vercel)
vercel --prod --yes                  # deploy; aliases to ict-trading-os-rho.vercel.app
curl -s https://ict-trading-os-rho.vercel.app/api/health   # verify
```

**MT5 bridge tunnel changed?** No redeploy needed — paste the new quick-tunnel URL in
**Settings → MT5 Bridge Connection** (DB override, effective immediately). See
[`mt5-bridge/README.md`](mt5-bridge/README.md).
