# ICT Trading OS — Engineering Solution Document

> **Version:** 2.0 | **Date:** 2026-09-05 | **Status:** Living document
>
> Covers: design → high-level design → application architecture → dev phase →
> test phase → production. Supersedes scattered status notes; the canonical
> engineering reference alongside `ARCHITECTURE.md` (product/feature view).

---

## 1. Purpose & Scope

ICT Trading OS is a **personal trading command center** built around the ICT
(Inner Circle Trader) methodology. It answers four questions for its operator:

1. **What is the market doing?** — live broker prices, charts, ICT level detection
2. **What should I trade?** — signals, strategist (regime → strategy), forward tests
3. **Did it work?** — journal, analytics, forward-test tracking
4. **How do I get better?** — knowledge base (RAG over trading content), backtests

**Hard invariant (non-negotiable):** AI advises, humans execute. The only order
path is `signal (advisory) → suggestion (UI) → human approval → deterministic
Python → broker bridge`. No LLM output ever reaches an order endpoint directly.

---

## 2. Design (Product-Level)

### 2.1 Personas

| Persona | Need | Surface |
|---|---|---|
| Operator (owner) | One-screen market state, disciplined execution | Dashboard, Execute, MT5 Terminal |
| Analyst | Strategy validation before risking capital | QuantLab, Strategy Lab, Forward Tests |
| Learner | Structured ICT knowledge | Knowledge Base, Library |

### 2.2 Design Principles

1. **Broker is the only price truth.** Every price/candle/level/signal/backtest
   comes from the connected broker bridge. A feature with no broker data shows
   an honest "bridge offline" state — never a silently fabricated number.
2. **Deterministic risk.** Position sizing, daily loss limits, and trading
   lockouts are pure-Python functions in `risk_service.py` — immutable by AI,
   reviewable by humans, tested by unit tests.
3. **Provider-agnostic broker link.** The app talks to a bridge over one HTTP
   contract; which broker sits behind it (MT5 terminal, cTrader Open API,
   cTrader FIX) is a runtime setting, not code.
4. **Advisory AI with citations.** LLM outputs carry provenance and are
   validated before persistence (no raw LLM JSON straight into the DB).
5. **Local-first secrets.** Broker credentials live in the bridge's `.env` on
   the operator's machine, never in the repo, never in the cloud app.

---

## 3. High-Level Design

```
                         ┌────────────────────────────────────────┐
                         │            OPERATOR'S BROWSER           │
                         │   React SPA (Vite, Tailwind, shadcn)    │
                         └───────────────┬────────────────────────┘
                                         │ HTTPS /api/*  (X-Api-Key)
                         ┌───────────────▼────────────────────────┐
                         │     FASTAPI APP  (Vercel serverless)    │
                         │  routers → services → SQLite/Postgres   │
                         │  quote_service (single price truth)     │
                         │  risk_service (immutable safety rules)  │
                         │  signal / strategist / journal / KB     │
                         └───────────────┬────────────────────────┘
                                         │ HTTPS over tunnel
                                         │ (X-Bridge-Key shared secret)
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
   ┌──────────▼─────────┐   ┌────────────▼───────────┐   ┌─────────▼─────────┐
   │  mt5-bridge        │   │  ctrader-bridge        │   │  (future bridges) │
   │  MetaTrader5 pkg   │   │  CT_TRANSPORT selects: │   │  same contract    │
   │  (Windows terminal)│   │  • openapi (protobuf)  │   │                   │
   │                    │   │  • fix (FIX 4.4, deflt)│   │                   │
   └──────────┬─────────┘   └────────────┬───────────┘   └───────────────────┘
              │ MT5 terminal API         │ TLS to cServer
              ▼                          ▼
        MT5 broker acct            cTrader account (demo 5900854)
```

**Bridge selection:** `BRIDGE_PROVIDER` env or Settings → Bridge Connection
(`ctrader` default | `mt5`). Inside the cTrader bridge, `CT_TRANSPORT`
selects `fix` (default — FIX 4.4, account password only, no terminal,
Linux/macOS-friendly) or `openapi` (protobuf, needs app credentials).

---

## 4. Application Architecture

### 4.1 Repository Layout (shipping components only)

| Path | Role |
|---|---|
| `app/routers/` | 19 FastAPI routers — thin HTTP layer, no business logic |
| `app/services/` | Business logic: `quote_service` (price truth), `risk_service` (immutable), `mt5_price_service`/`mt5_trades_service` (bridge client), `signal_engine`, `strategist`, `journal`, `kb`, … |
| `app/core/config.py` | Env-driven settings, `BRIDGE_PROVIDER` |
| `frontend/src/` | React SPA: pages (Dashboard, Signals, Execute, Analytics, QuantLab, Settings, …), `hooks/useMt5.ts` (bridge status polling) |
| `ctrader-bridge/` | Standalone Flask sidecar: `ctrader_bridge.py` (HTTP contract), `fix_client.py` (FIX 4.4), `ctrader_client.py` (Open API), `config.py`, `telegram_bot.py` |
| `mt5-bridge/` | Legacy MT5 sidecar (Windows-only). Same HTTP contract |
| `tests/` | 230 pytest cases |
| `vercel.json` | SPA + `/api` routing, cron for Telegram poll |

### 4.2 The Bridge HTTP Contract (both bridges implement it)

```
GET  /                     → status { mt5_connected, mt5_login, mt5_server, provider }
GET  /tick/<symbol>        → { symbol, price(mid), bid, ask, last, spread, time, source }
GET  /candles/<symbol>?timeframe&count
GET  /symbols              → tradable symbol names
GET  /symbol/<symbol>      → contract spec (digits, point, volume min/max/step)
GET  /account              → balance/equity/margin snapshot
GET  /positions            → open positions
GET  /history?days=        → closed deals
POST /order-check          → validate WITHOUT placing (SL/TP side, volume, margin)
POST /trade                → market order (human-approved only)
POST /pending              → limit/stop order
POST /close  /partial-close  /modify  /cancel-pending
GET  /fetch?url=           → residential-IP fetch sidecar (bridge-key protected)
```

All mutating/data routes require `X-Bridge-Key`. `/` is deliberately open so
the app's status probe works without a key.

### 4.3 cTrader FIX Transport (`ctrader-bridge/fix_client.py`)

- Two FIX 4.4 sessions over TLS to the cServer: **price** (SenderSubID=QUOTE)
  and **trade** (SenderSubID=TRADE, TargetSubID=QUOTE — server-enforced).
- Logon = account password (tags 553/554). No developer app, no OAuth token.
- Symbol map built from SecurityList (`35=x`): tag 55 = numeric ID,
  tag 1007 = name, tag 1008 = digits. All outbound messages use numeric IDs.
- Market data: `35=V` snapshot+subscribe per symbol; ticks cached and
  aggregated into OHLC candles in-memory.
- SL/TP model: FIX 4.4 has no position-attach, so protection is sibling
  stop/limit orders keyed to the position (tracked in `_clord_map`).

**Honest FIX limitations (by protocol, not by bug):**
- No historical candles → candles accumulate from bridge start (warm-up)
- No deal-history query → `/history` returns `[]`
- No balance query → `/account` money fields are `null`, never invented

### 4.4 Safety Architecture (AGENTS.md hard rules)

- `risk_service.py` sizing math, daily loss limits, lockout logic: **immutable**
  without `/review` + `/cso` + human sign-off in the PR description.
- `execution_service.py` stop-loss enforcement: same protection level.
- AI never places/modifies/cancels orders. `/trade` exists for the UI's
  human-approved flow; order-check is the advisory validation gate.
- DB schema protections: no dropping/renaming columns in `trades`,
  `daily_risk_ledger`, `trading_plans`; audit fields are untouchable.

---

## 5. Development Phase — How We Build

Workflow (per AGENTS.md, gstack TechCEO loop):

```
/office-hours → /spec → /plan-eng-review → implement → /review → /qa → /ship
```

Concretely, for every change:
1. **Specify** the exact behavior + data flow before code.
2. **Implement** behind the existing contracts (bridge HTTP contract, quote
   service shape) so providers stay swappable.
3. **Unit tests** for every conversion/normalizer/guard (see §6).
4. **Review** with the gstack pre-landing checklist (SQL safety, race
   conditions, LLM trust boundary, shell injection, enum completeness).
5. **Security** (`/cso` scope) for anything touching risk/execution/bridge.
6. **Ship:** `npm --prefix frontend run build` → commit (incl. `frontend/dist`)
   → push → Vercel deploy → `scripts/smoke.sh`.

### 5.1 What the cTrader integration actually took (retro)

Real bugs found during live integration, all fixed and committed:

| # | Bug | Lesson |
|---|---|---|
| 1 | Open API placeholder access token rejected | Validate credentials shape before wiring |
| 2 | FIX header fields after body → server Logout | cServer requires strict header order |
| 3 | `bytes` vs `str` comparisons (simplefix) | Protocol libs return bytes; decode at the boundary |
| 4 | Trade session SubID semantics | SenderSubID=TRADE but TargetSubID=QUOTE (asymmetric) |
| 5 | Server wants numeric symbol IDs in tag 55 | Read SecurityList first, never assume name addressing |
| 6 | **Inverted SL/TP side validation (both clients)** | Would have rejected every valid order — caught by live order-check, not by tests (test gap, see §7) |
| 7 | FIX tick missing `price` field → UI showed 0 | Contract parity must be verified field-by-field against the consumer |

---

## 6. Test Phase

### 6.1 Current state (measured 2026-09-05)

| Suite | Result | Duration |
|---|---|---|
| Backend pytest (`tests/`, 27 files) | **230 passed, 0 failed** | 70s |
| cTrader bridge (`test_bridge.py`) | **11 passed** | <1s |
| Production smoke (`scripts/smoke.sh`) | **SMOKE OK** | ~5s |
| Live FIX verification | logon, /symbols (830), /tick EURUSD, /candles, /order-check (accept + reject paths), /positions — all pass against demo account 5900854 | manual |

### 6.2 Test layers

1. **Unit** — conversions (lots↔volume, money digits), normalizers (tick/
   candle/position shapes), risk math, SL/TP side validation.
2. **Contract** — every bridge response shape the app parses has a pinned
   fixture test (this is what caught nothing in the FIX client — see gap §7).
3. **Route/integration** — FastAPI TestClient over routers with bridge mocked.
4. **Guard tests** — `test_mt5_guard.py`, `test_bridge_provider.py`: safety
   invariants are tested, not just documented.
5. **Smoke** — post-deploy live check of the Vercel app.

### 6.3 Test gaps (actioned in the plan, §8)

- `fix_client.py` has **zero unit tests** — the SL/TP inversion (bug #6) and
  tick-shape mismatch (bug #7) both reached production because of this.
- `backend/` (dormant parallel backend) has zero tests and ships nothing —
  flagged for removal in the plan.
- No automated browser QA of the Analytics/Research pages (gstack `/qa`
  equivalent) — currently manual.

---

## 7. Security Posture (CSO audit summary, 2026-09-05)

| Area | Status |
|---|---|
| Secrets in repo | ✅ None — `.env*` gitignored; only `.env.example` templates tracked. `scripts/grep-loop.sh` is itself a secret scanner |
| Shell injection | ✅ No `shell=True`/`os.system`/`eval` in `app/` or bridges |
| Bridge auth | ✅ `X-Bridge-Key` on all data/mutation routes |
| App auth | ✅ `X-Api-Key` header on API; frontend stores key in localStorage |
| SSRF (`/fetch`) | ⚠️ Bridge-key protected but **no host allowlist** — could reach internal-network URLs from the bridge host. Low (key-gated, operator-owned host), fix scheduled |
| Credential handling | ⚠️ Demo cTrader password was pasted in chat during setup (rotate when convenient); stored only in gitignored `.env` |
| TLS | ✅ FIX sessions use TLS with SNI (port 5211) |
| Dependency pins | ⚠️ `ctrader-open-api==0.9.2` needs `--no-deps` (protobuf pin conflict) — documented in requirements; FIX path (simplefix, pure Python) is the default so this only affects the openapi transport |

---

## 8. Phased Plan — What's Missing & What's Next

### Phase A — Stabilize the cTrader FIX line (this week)

| # | Item | Why |
|---|---|---|
| A1 | Unit tests for `fix_client.py`: tick shape, candle aggregation, SL/TP side validation (both directions), symbol-ID mapping, order field encoding | Prevents regressions of bugs #6/#7 |
| A2 | `/fetch` host allowlist (block RFC1918/loopback/link-local) | Closes the one open SSRF note |
| A3 | Persistent tunnel: named Cloudflare tunnel replaces quick-tunnel | Quick-tunnel URL churns on restart; app needs re-pasting (login flow started, awaiting Cloudflare auth) |
| A4 | Account balance via FIX: probe for broker-specific balance tags; if absent, document and hide equity widgets in FIX mode | Honest UI, no null clutter |

### Phase B — Product integration debt (from PROGRESS.md P0–P4)

| # | Item |
|---|---|
| B1 | Journal & Plan pages: wire to persistence APIs (currently pure UI) |
| B2 | Analytics auto-journal save; Settings theme toggle wiring |
| B3 | Delete/archive dormant `backend/` and Gen-0 `server.js`/`lib/`/`ICT_Trading_OS_v7.html` |
| B4 | Unify the two Kelly implementations; standardize price timestamps to UTC ISO |
| B5 | Add row-level locking to concurrent partial/full close |

### Phase C — cTrader depth (weeks 3-4)

| # | Item |
|---|---|
| C1 | Candle warm-up: preload recent history from the broker's web API on bridge start (or accept and display warm-up state in UI) |
| C2 | Deal history sync: poll ExecutionReports into a local ledger so `/history` works in FIX mode |
| C3 | Production hardening: run bridge under a real WSGI server + supervisor; systemd/launchd unit |
| C4 | Live-account readiness checklist (only after weeks of clean demo forward tests) |

### Phase D — Scale & polish (later)

- CI pipeline: pytest + frontend build + smoke on every push (P5)
- Vercel-native frontend build (stop committing `dist/`)
- Multi-account support (second cTrader account or prop-firm account)
- Browser-QA automation for Analytics/Research

---

## 9. Is the Application Serving Its Purpose?

**Mostly yes — with honest caveats.**

| Purpose | Verdict |
|---|---|
| Live market state from my broker | ✅ Working — cTrader FIX bridge feeds prices, ticks, candles to every surface |
| Disciplined, risk-checked execution | ✅ Architecture enforces it (advisory → human approval → deterministic risk rules). Order-check validation proven live |
| No-terminal, Linux-capable broker link | ✅ Achieved — the original "replace MT5" goal. FIX runs anywhere Python runs |
| Strategy validation (backtest/forward test) | ✅ Engines exist and produce measured, honest verdicts (incl. negative ones — the strategist says STAND ASIDE when nothing fits) |
| Journal/analytics loop | ⚠️ Partial — pages exist but journal/plan persistence wiring is incomplete (B1) |
| Knowledge compounding (KB/RAG) | ✅ Working |

**The gap between "demo-connected" and "trading-ready":** Phase A items
(tests, persistent tunnel, balance display) plus weeks of clean forward
tests on the demo account. The app is a solid advisory + journal system
today; execution should stay demo-only until Phase A lands.

---

## 10. Appendix — Operational Runbook

```bash
# Bridge (operator's machine)
cd ctrader-bridge
.venv/bin/python ctrader_bridge.py          # port 5001
./cloudflared tunnel --url http://localhost:5001   # quick tunnel (URL churns)

# App deploy
npm --prefix frontend run build
vercel --prod --yes
bash scripts/smoke.sh

# Tests
uv run pytest tests/ -q                     # backend
ctrader-bridge/.venv/bin/python -m pytest ctrader-bridge/test_bridge.py -q
```

Settings → Bridge Connection: engine switch (cTrader FIX / MT5) + runtime
bridge URL with Save & Test. Provider persists in the app DB — no redeploy
needed when the tunnel URL changes.
