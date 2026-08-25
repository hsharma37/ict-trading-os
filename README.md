# ICT Trading OS

A private trading **decision operating system** for one trader: live market data,
ICT pattern detection, trading signals, quantitative analytics, a source-backed
knowledge base, and **real MetaTrader 5 execution + position management** — all in
one connected app.

- **Live app:** https://ict-trading-os-rho.vercel.app
- **Stack:** React + Vite + TypeScript (frontend) · FastAPI (backend) · PostgreSQL + pgvector (durable storage) · MetaTrader 5 bridge (execution) · deployed on Vercel

---

## Architecture

```
                         ┌───────────────────────────────────────────────┐
  Browser (React SPA) ──▶│  Vercel  ──  FastAPI (api/index.py → app/)     │
   marketApi / mt5Api    │   /api/*  →  routers → services                │
   useMt5 (React Query)  │             ├─ quote_service (single price src)│
                         │             │    └─ MT5 / OANDA / Yahoo        │
                         │             ├─ trade/analytics/quant/ict/kb …  │
                         │             └─ Postgres + pgvector (durable)   │
                         └───────────────────────┬───────────────────────┘
                                                 │ /api/mt5/* (X-Bridge-Key + retry)
                                                 ▼
                    ┌──────────────────────────────────────────────┐
                    │  MT5 Bridge (Windows) — mt5-bridge/           │
                    │  Flask + MetaTrader5 package + live terminal  │
                    │  exposed via a tunnel (ngrok / Cloudflare)    │
                    └──────────────────────────────────────────────┘
```

Three parts of the repo:

| Path | What |
|---|---|
| `app/` | **Active** FastAPI backend (deployed). Routers + services + Postgres. |
| `frontend/` | React SPA (Vite). Pages, the shared `useMt5` hook, `marketApi` client. |
| `mt5-bridge/` | Standalone Flask bridge (+ `watchdog.py` supervisor) that runs on Windows next to the MT5 terminal. |
| `ctrader-bridge/` | **Default bridge.** Same HTTP contract as `mt5-bridge/`, but runs anywhere (cTrader's Open API is server-side — no terminal, no Windows). See [`ctrader-bridge/README.md`](ctrader-bridge/README.md). Select via `BRIDGE_PROVIDER` env or Settings → bridge provider (`ctrader` default, `mt5` legacy). |

---

## Features

### 📈 Market data — one source, switchable provider
All prices flow through a **single resolver** (`app/services/quote_service.py`), so
every page shows the same value from the same source, with a short shared cache.

- Providers, selected by `MARKET_DATA_PROVIDER`: **`mt5`** (broker feed — matches
  your fills), **`oanda`** (v20 REST), **`yahoo`** (default), with graceful
  per-symbol fallback and a synthetic last resort.
- Every quote carries a **`source`** (mt5 / oanda / yahoo / scraped / synthetic /
  manual) and a **`stale`** flag; the UI shows a **Live · MT5** badge so demo/stale
  data is never presented as live.
- Endpoints: `GET /market/price/{symbol}`, `GET /market/prices`,
  `GET /market/history/{symbol}`, plus manual-price override.

### 🟢 MetaTrader 5 — real execution, management & data
The `mt5-bridge/` service wraps the official `MetaTrader5` Python package (Windows
only, next to a logged-in terminal). The app proxies to it over a tunnel with a
shared-secret (`X-Bridge-Key`), retries, and audit logging.

- **Execution:** market orders (`POST /mt5/trade`), close, **partial close**,
  **modify SL/TP**, **pending limit/stop orders**, cancel pending.
- **Execution Console (Execute page)** places orders **directly on the MT5 account**
  when the terminal is connected — market or pending (limit/stop), with the lot
  auto-sized from account balance + risk %, SL and TP1 attached. It shows a
  **Live MT5** badge with the account balance, and the live positions right below
  the form with full **close / partial-close / modify-SL-TP** controls. When the
  bridge is offline it falls back to planning in the internal ledger.
- **Safety guardrails** on every order: symbol allowlist, lot caps (`MT5_MAX_LOT`),
  min-lot, side-aware SL/TP validation, optional required SL, per-intent audit log.
- **Market data from the broker:** live tick, historical candles (M1–W1), contract
  specs, full tradable-symbol list.
- **Account & positions:** balance/equity/margin, open positions, paired trade
  history. The bridge self-heals from IPC drops and fails honestly (503) rather
  than faking data.

### 🔗 Live positions everywhere (connected UI)
A shared `useMt5` React Query hook is the single source of MT5 state for the whole
app, so **Dashboard**, **What's Up** and **MT5 Terminal** show identical positions
and P&L, and **close / modify SL-TP / partial-close work from any of them**
(mutations invalidate the one shared cache).

- **MT5 Terminal:** account cards, positions table + management, trade history, quick-trade panel.
- **Dashboard:** live MT5 open positions and P&L in the KPIs + positions card.
- **What's Up:** per-position SL→entry→TP progress-bar visualization + management.

### 🧭 MT5 terminal as the trades base
When the bridge is reachable and the terminal is connected, **MT5 is the single
source of truth for all trade data** — Dashboard KPIs, Analytics, and the chatbot
read the broker's real open positions, closed-deal history, and account instead of
the internal ledger (which remains the automatic fallback when the bridge is down).
- One service (`app/services/mt5_trades_service.py`) reshapes broker data into the
  same stats schema the ledger produced, so `/trades/stats/*` and `/analytics/*`
  switch over with no schema churn. Dashboard/Analytics show a **"Live · MT5"** badge.
- **Chatbot is account-aware:** ask "how are my positions doing?" / "what's my P&L?"
  and the KB assistant answers from the live terminal (with any relevant KB notes
  as educational context) instead of refusing. Reporting only — never trade advice.
- **Signals & research** are annotated with your live exposure (a signal flags
  `held` when you already have a position in that symbol; research summary lists
  your open positions).
- Broker closed deals carry no SL, so **R-multiple metrics read 0** under MT5 (not
  fabricated); P&L is the broker's own realized/float figure, matching the terminal.

### 🧠 Knowledge base (ICT sources)
- Add sources by **YouTube URL** (auto-transcribe) or **pasted transcript**;
  chunked, embedded, and searchable via **pgvector** semantic search
  (deterministic fallback when the extension isn't available).
- Auto-extracts ICT **concepts** (FVG, OB, MSS, liquidity, killzones, …) and a
  reusable **playbook** (setup / trigger / invalidation / management) per source.
- **Auto-transcribe works via the MT5 bridge:** YouTube blocks caption/title
  requests from cloud/serverless IPs, so the app fetches transcripts and titles
  through the bridge (`/transcript`, `/video-meta`) on the user's residential
  IP. Requires the bridge running; paste-transcript is always available too.

### 🎯 ICT analysis, signals & quant
- **ICT engine:** MSS/BOS, FVG, order blocks, liquidity — single & multi-timeframe.
- **Signals:** per-symbol signal generation, active-signal tracking, scanning.
- **Quant:** Sharpe/Sortino, Kelly sizing, Monte-Carlo, trend/volatility/levels,
  decision helper, bot coaching.
- **Analytics & journal:** expectancy, win rate, R-multiples, drawdown, streaks,
  session/symbol breakdowns — computed from the **MT5 terminal** when connected
  (see "MT5 terminal as the trades base"), else the internal ledger.

### 💬 Telegram
- Signal feed + notifications from the app (`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHANNEL_ID`).
- The MT5 bridge can also send trade execution/close notifications directly.
- **Public-channel polling:** reads a public ICT channel's posts via its web
  preview (`t.me/s/<channel>`) — **no bot membership or credentials needed** —
  parses each message into a structured signal (symbol/side/entry/SL/TP/strategy),
  dedupes by channel+message id, and stores it in the signal feed. Set the channel
  with `TELEGRAM_SOURCE_CHANNEL` (default `xxictxx`). The Telegram page shows the
  active source channel; the **Manual Poll** button runs it on demand.
  - **Hourly** polling is driven by the always-on **MT5 bridge** (set `APP_BASE_URL`
    in the bridge's `.env` — see [`mt5-bridge/README.md`](mt5-bridge/README.md)),
    which works on any hosting plan. A Vercel cron (`GET /api/telegram/poll-source`,
    `0 0 * * *`) also runs it **daily** as a fallback (Vercel Hobby caps crons at
    once/day; Pro can go hourly — bump the schedule to `0 * * * *`).

### 🔐 Security
- Production protects private/mutating routes behind an **`X-Api-Key`** gate
  (fails closed at startup if `API_KEY`/`JWT_SECRET` are unset/default).
- The frontend supplies the key at runtime (browser `localStorage`, never baked
  into the bundle); a global banner prompts for it on the first 401.
- Public routes: `GET /`, `/health`, `/docs`, `/openapi.json`, `/redoc`, plus
  read-only market/analytics/signals/quant/news/research.

---

## Pages

`Dashboard` · `MT5 Terminal` · `Execute` · `Analytics` · `Research` · `Signals` ·
`Telegram` · `Knowledge` · `Library` · `What's Up?` · `Settings`

---

## API surface (grouped)

| Group | Examples |
|---|---|
| **Market** | `GET /market/price/{sym}`, `/market/prices`, `/market/history/{sym}`, `POST/DELETE /market/manual-price/{sym}` |
| **MT5** | `GET /mt5/status·account·positions·history·tick/{s}·candles/{s}·symbol/{s}·symbols·orders`; `POST /mt5/trade·close·partial-close·modify·pending·pending/cancel` |
| **Trades** | `POST /trades`, `GET /trades`, `POST /trades/{id}/close·partial·move-sl-be`, stats, `DELETE /trades` (reset ledger) |
| **ICT** | `GET /ict/analyze/{sym}`, `/ict/analyze/multi/{sym}` |
| **Signals** | `GET /signals/analyze/{sym}`, `/signals/active`, `POST /signals/scan` |
| **Quant** | `GET /quant/metrics·kelly·coach·trend/{s}·volatility/{s}`, `POST /quant/monte-carlo` |
| **Analytics** | `GET /analytics/summary·expectancy·heatmap·drawdown·kelly·symbols` |
| **Knowledge** | `GET/POST /kb/sources`, `/kb/search·search-embeddings`, `POST /kb/auto-transcribe·chat` |
| **Telegram** | `GET /telegram/status·signals·stats`, `POST /telegram/poll·configure·auto-trade/{id}` |
| **Other** | `alerts`, `bot`, `orders`, `plans`, `research`, `news`, `settings` |

Interactive docs at `/docs` (Swagger) on any running instance.

---

## Local setup

```bash
uv venv --python 3.12 .venv
uv pip install -r requirements.txt pytest
npm --prefix frontend ci

export DATABASE_URL=postgresql://localhost:5432/ictos_dev
psql "$DATABASE_URL" -f migrations/001_postgres_pgvector_foundation.sql

# Backend
PRICE_CACHE_DIR=/tmp/tradingos \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend
VITE_API_URL=http://127.0.0.1:8000 npm --prefix frontend run dev -- --host 127.0.0.1 --port 3000
```

For throwaway local tests only, leave `DATABASE_URL` empty and set
`ALLOW_SQLITE_RUNTIME=true DATABASE_PATH=ictos.db`.

### MT5 bridge (Windows)

Real execution/data requires the bridge running on **Windows**, next to a
logged-in MT5 terminal (the `MetaTrader5` package is Windows-only). See
[`mt5-bridge/README.md`](mt5-bridge/README.md). Summary:

```powershell
cd mt5-bridge
pip install -r requirements.txt        # installs MetaTrader5 on Windows
copy .env.example .env                  # fill MT5_LOGIN/PASSWORD/SERVER + MT5_BRIDGE_API_KEY
python mt5_bridge.py
cloudflared tunnel --url http://localhost:5000   # or ngrok; paste the URL in Settings
```

> **To place orders, enable Algo Trading in the MT5 terminal** (Ctrl+E → button
> green). It's a MetaQuotes safety switch no API can toggle; while off, every
> order is rejected (the app shows a clear message). Order execution auto-selects
> a broker-supported filling mode, and `POST /api/mt5/order-check` validates an
> order without placing it (for safe diagnosis).

Then set `MT5_BRIDGE_URL` (the tunnel URL) and `MT5_BRIDGE_API_KEY` (matching the
bridge) on the app, and `MARKET_DATA_PROVIDER=mt5` to price from the broker feed.

**Tunnel URL changed? No redeploy needed.** A free Cloudflare *quick* tunnel URL
changes on every bridge restart. Instead of editing `MT5_BRIDGE_URL` on Vercel
and redeploying, open **Settings → MT5 Bridge Connection** in the app, paste the
new `https://…trycloudflare.com` URL, and hit **Save & Test** — it's stored in
the database, takes effect immediately, and is probed on save so you get instant
`reachable` / `MT5 connected` feedback. This DB override wins over the env var;
the env var stays the fallback default. (`MT5_BRIDGE_API_KEY` remains env-only —
it's a secret and isn't editable from the UI.)

---

## Configuration (env)

| Var | Purpose |
|---|---|
| `DATABASE_URL` | Postgres (+pgvector) connection — durable KB/trade state |
| `API_KEY`, `JWT_SECRET` | Production auth secrets (required, no defaults) |
| `MARKET_DATA_PROVIDER` | `auto` (default) / `mt5` / `oanda` / `yahoo` |
| `MT5_BRIDGE_URL`, `MT5_BRIDGE_API_KEY` | Reach + authenticate the MT5 bridge |
| `MT5_ALLOWED_SYMBOLS`, `MT5_MAX_LOT`, `MT5_REQUIRE_SL` | Execution guardrails |
| `OANDA_API_TOKEN`, `OANDA_ACCOUNT_ID`, `OANDA_ENV` | OANDA price provider |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` | Telegram notifications |
| `TELEGRAM_SOURCE_CHANNEL` | Public channel to poll hourly via web preview (default `xxictxx`) |
| `CRON_SECRET` | Optional; when set, the cron poll endpoint requires Vercel's `Authorization: Bearer` |
| `CORS_ORIGINS`, `LOG_LEVEL`, `APP_ENV` | Runtime config |

See `.env.example`, `.env.production.example`, `.env.preview.example`.

---

## Deployment

Deployed on Vercel: the React build is served statically and FastAPI runs as the
Python serverless function under `/api/*`. `main` is production. Details (branch
model, env separation, durable Postgres checklist) in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

```bash
npm --prefix frontend run build   # produces frontend/dist (copied to public/ on deploy)
vercel --prod
curl -s https://<your-app>.vercel.app/api/health
```

---

## Testing

```bash
.venv/bin/python -m pytest -q                 # backend suite
.venv/bin/python -m pytest mt5-bridge/test_bridge.py -q   # bridge (runs w/o MetaTrader5)
npm --prefix frontend run lint && npm --prefix frontend run build
```

The MT5 bridge tests inject a fake `MetaTrader5` module so they run on any OS.

---

## Progress

| Area | Status |
|---|---|
| Deployment & CI/CD | ✅ Live prod + API; SPA/API routing solved; no-store/asset-404 fixes |
| Durable storage | ✅ Postgres + pgvector in production |
| Market data | ✅ Single resolver, switchable providers, source/staleness transparency |
| MT5 execution | ✅ Real orders, close, partial, modify SL/TP, pending; validation + audit |
| MT5 data | ✅ Live ticks, candles, specs, symbols via the bridge |
| Connected UI | ✅ Live positions + management (incl. rich per-position viz) on Dashboard, What's Up, Terminal |
| MT5 as trades base | ✅ Dashboard KPIs, Analytics, chatbot, signals/research all read the live terminal (broker P&L/history/account) when connected; ledger fallback |
| Auth/security | ✅ X-Api-Key gate + runtime key entry; fail-closed secrets |
| Telegram | ✅ App feed + bridge notifications; **hourly public-channel polling** (web preview, no bot needed) |
| Execution Console | ✅ Places real MT5 market/pending orders + live position management from the Execute page |
| Knowledge base | ✅ Ingest/search/pgvector; YouTube auto-transcribe + titles via the bridge (residential IP) |
| Journal/planner | 🟡 Ledger + analytics exist; deeper plan↔trade↔journal linking pending |
| Reliability | 🟡 Bridge on a free **quick** tunnel — URL changes on restart, but re-pointing is a paste in **Settings → MT5 Bridge Connection** (no redeploy); a Cloudflare *named* tunnel or VPS gives a permanent URL |

See [PROGRESS.md](PROGRESS.md) for the detailed improvement plan.

---

## Notes & caveats

- The whole MT5 experience depends on the **Windows bridge + tunnel** staying up.
  A free quick-tunnel URL changes on restart — re-point it in **Settings → MT5
  Bridge Connection** (no redeploy). A **Cloudflare named tunnel** (free,
  permanent URL) or a small VPS is the durable setup.
- The app is a **decision/tracking cockpit** — AI is advisory only and never fires
  trades; deterministic guardrails enforce execution safety.
