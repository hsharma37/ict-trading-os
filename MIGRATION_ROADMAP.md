# ICT Trading OS — Migration Roadmap

> **Version**: 1.0  
> **Date**: 2026-06-26  
> **Status**: Phase 1 Ready

---

## Overview

This document defines the **4-phase migration** from the current HTML-first prototype (`ICT_Trading_OS_v7.html`) to a modern **React + FastAPI + PostgreSQL + AI** architecture.

Each phase is designed to be **independently deployable and functional**, so you can use the system at every milestone without waiting for the full rewrite.

---

## Phase 0: Current State (Baseline)

### What Exists Today

| Component | Status | Notes |
|-----------|--------|-------|
| `ICT_Trading_OS_v7.html` | ✅ Single-file dashboard | All UI, logic, and state in one HTML file (~300KB) |
| `server.js` | ✅ Basic API | Market data, trade CRUD, MT5 proxy |
| `mt5bridgeScript.py` | ✅ MT5 bridge | Order execution + Telegram notifications |
| `.env` + `.env.example` | ✅ Config | Manual env variable management |
| Knowledge Base | ✅ localStorage only | Transcript chunks survive browser restart |
| Lot Calculator | ✅ Leverage 1-100x | Slider-based, affects all calculations |
| Telegram | ✅ Bot integration | Test endpoint + debug logging |
| SQLite | ⚠️ Ad-hoc | No migrations, no schema definition |

### Pain Points to Solve

1. **Business logic lives in HTML/JS** — position sizing, risk rules, and planner logic are browser-side.
2. **No schema evolution** — adding a new field means manual localStorage or SQLite patching.
3. **No real-time updates** — manual refresh for price, trades, and alerts.
4. **AI is ad-hoc** — no structured RAG pipeline, no vector search, no agent orchestration.
5. **Testing is manual** — no unit tests, no CI, no reproducible builds.
6. **Single file limit** — ~300KB HTML is becoming unmaintainable; adding features is painful.
7. **No concurrent access** — SQLite locks, no multi-process safety.

---

## Phase 1: Product Foundation (Weeks 1-4)

**Goal**: Extract the current UI into a proper React frontend, move domain logic into FastAPI, replace SQLite with PostgreSQL, and establish real-time updates via WebSockets.

### 1.1 Project Structure

```
ict-os/
├── docker-compose.yml          # Local orchestration
├── .env                        # Centralized config
├── .env.example                # Template for new setups
├── Makefile                    # Common dev commands
│
├── frontend/                   # React + Vite + TypeScript
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── main.tsx            # App entry
│   │   ├── App.tsx             # Router + layout
│   │   ├── components/         # Reusable UI components
│   │   │   ├── ui/             # shadcn/ui primitives
│   │   │   ├── charts/         # TradingView + ECharts wrappers
│   │   │   ├── tables/         # TanStack Table configs
│   │   │   └── forms/          # Form components
│   │   ├── pages/              # Route-level pages
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Plan.tsx
│   │   │   ├── Execute.tsx
│   │   │   ├── Journal.tsx
│   │   │   ├── Knowledge.tsx
│   │   │   ├── Analytics.tsx
│   │   │   └── Settings.tsx
│   │   ├── hooks/              # Custom React hooks
│   │   │   ├── useMarketData.ts
│   │   │   ├── useTrades.ts
│   │   │   └── useWebSocket.ts
│   │   ├── stores/             # Zustand stores
│   │   │   ├── uiStore.ts
│   │   │   └── authStore.ts
│   │   ├── api/                # TanStack Query + API clients
│   │   │   ├── client.ts       # Axios/fetch setup
│   │   │   ├── queries/        # Query definitions
│   │   │   └── mutations/      # Mutation definitions
│   │   ├── types/              # TypeScript interfaces
│   │   └── utils/              # Helpers, formatters
│   └── public/
│       └── favicon.ico
│
├── backend/                    # FastAPI + SQLModel + Alembic
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── alembic/
│   │   ├── env.py
│   │   ├── versions/           # Migration files
│   │   └── script.py.mako
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app entry
│   │   ├── config.py           # Pydantic settings
│   │   ├── database.py         # SQLModel engine + session
│   │   ├── models/             # SQLModel table definitions
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── plan.py
│   │   │   ├── trade.py
│   │   │   ├── journal.py
│   │   │   └── kb.py
│   │   ├── schemas/            # Pydantic request/response models
│   │   │   ├── __init__.py
│   │   │   ├── plan_schemas.py
│   │   │   ├── trade_schemas.py
│   │   │   └── journal_schemas.py
│   │   ├── api/                # Route definitions
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── plans.py
│   │   │   │   ├── trades.py
│   │   │   │   ├── risk.py
│   │   │   │   ├── journal.py
│   │   │   │   ├── market.py
│   │   │   │   ├── analytics.py
│   │   │   │   ├── telegram.py
│   │   │   │   └── mt5.py
│   │   │   └── websocket.py    # WebSocket endpoints
│   │   ├── services/           # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── planner_service.py
│   │   │   ├── execution_service.py
│   │   │   ├── risk_service.py
│   │   │   ├── journal_service.py
│   │   │   ├── market_data_service.py
│   │   │   ├── telegram_service.py
│   │   │   └── analytics_service.py
│   │   ├── core/               # Shared utilities
│   │   │   ├── __init__.py
│   │   │   ├── exceptions.py
│   │   │   ├── security.py
│   │   │   └── logging.py
│   │   └── tests/              # Pytest suite
│   │       ├── __init__.py
│   │       ├── test_plans.py
│   │       ├── test_trades.py
│   │       └── test_risk.py
│   └── scripts/
│       ├── init_db.py          # Seed initial data
│       └── migrate_data.py     # Migrate from old SQLite/localStorage
│
├── mt5-bridge/                 # MT5 bridge (refactored from current)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── mt5_bridge.py           # Main bridge script
│   ├── telegram_bot.py         # Telegram notification handler
│   └── config.py               # Bridge config
│
└── infra/                      # Docker, nginx, compose
    ├── docker/
    │   ├── Dockerfile.frontend
    │   └── Dockerfile.backend
    └── nginx/
        └── nginx.conf
```

### 1.2 Milestones

#### Week 1: Scaffold + Database

- [ ] Initialize monorepo with `frontend/` and `backend/` directories
- [ ] Set up Docker Compose with PostgreSQL + Redis + pgvector
- [ ] Create SQLModel models for: `User`, `TradingPlan`, `Trade`, `JournalEntry`, `DailyRiskLedger`
- [ ] Initialize Alembic and create baseline migration
- [ ] Create FastAPI skeleton with health check endpoint
- [ ] Set up Vite + React + TypeScript + Tailwind + shadcn/ui
- [ ] Configure TanStack Query and Zustand
- [ ] Create shared API client with typed endpoints

#### Week 2: Core API + Frontend Shell

- [ ] Implement `planner_service` + `/api/v1/plans` CRUD
- [ ] Implement `execution_service` + `/api/v1/trades` CRUD + close
- [ ] Implement `risk_service` + `/api/v1/risk/validate` + lot-size calculator
- [ ] Implement `journal_service` + `/api/v1/journal` CRUD + grading
- [ ] Build React layout (sidebar, topbar, route pages)
- [ ] Build Dashboard page with market widget + active trades summary
- [ ] Build Plan page with form, bias selector, killzone picker
- [ ] Build Execute page with order entry form + lot calculator
- [ ] Connect frontend to all API endpoints via TanStack Query

#### Week 3: Realtime + MT5 Bridge Integration

- [ ] Add WebSocket endpoint for price updates (`/ws/market/{symbol}`)
- [ ] Add WebSocket endpoint for trade updates (`/ws/trades`)
- [ ] Implement Redis pub/sub for cross-process event broadcasting
- [ ] Refactor `mt5bridgeScript.py` into `mt5-bridge/` service
- [ ] Connect MT5 bridge to FastAPI via API calls (or shared Redis)
- [ ] Add Telegram notification integration into `telegram_service`
- [ ] Build Journal page with entry list, stats, and grade panel
- [ ] Add real-time price ticker in top bar
- [ ] Add live trade status updates in dashboard

#### Week 4: Polish + Data Migration

- [ ] Migrate data from old SQLite/localStorage to PostgreSQL
- [ ] Add `analytics_service` with expectancy + session stats endpoints
- [ ] Build Analytics page with expectancy cards + session stats
- [ ] Build Settings page with risk config, MT5 config, Telegram config
- [ ] Add comprehensive error handling + loading states
- [ ] Write Pytest tests for all services
- [ ] Add Docker health checks + restart policies
- [ ] Document local setup in `README.md`
- [ ] **Phase 1 Release**: Fully functional React + FastAPI + PostgreSQL app

### 1.3 Phase 1 Deliverables

| Deliverable | Description |
|------------|-------------|
| Docker Compose stack | `docker compose up` spins up full local system |
| React frontend | All current v7 screens rebuilt as components |
| FastAPI backend | Typed REST API + WebSocket streams |
| PostgreSQL database | Full schema with Alembic migrations |
| MT5 bridge | Refactored as standalone service |
| Telegram | Integrated notification service |
| Tests | Pytest coverage for core services |

---

## Phase 2: Knowledge + AI Brain (Weeks 5-8)

**Goal**: Add the AI-powered knowledge system — transcript ingestion, RAG query, vector search, and AI chat for ICT concepts.

### 2.1 Milestones

#### Week 5: Ingestion Pipeline

- [ ] Set up Ollama in Docker Compose (`ollama` service)
- [ ] Add `kb_sources` and `kb_chunks` tables with pgvector `VECTOR` columns
- [ ] Build transcript ingestion service (YouTube + manual text)
- [ ] Implement semantic chunking (512 tokens, 50 overlap)
- [ ] Generate embeddings via Ollama (`nomic-embed-text`)
- [ ] Store chunks + embeddings in pgvector
- [ ] Build Knowledge page with source uploader + source list
- [ ] Add Celery worker for async ingestion jobs
- [ ] Add `POST /api/v1/kb/ingest` endpoint (async)
- [ ] Add `GET /api/v1/kb/sources` endpoint

#### Week 6: RAG + Search

- [ ] Implement semantic search over `kb_chunks` using pgvector cosine similarity
- [ ] Build `POST /api/v1/kb/search` endpoint (search only, no LLM)
- [ ] Integrate Haystack retriever pipeline
- [ ] Build Knowledge page search panel with results + snippets
- [ ] Add filtering by source, date, and concept tags
- [ ] Add search highlighting and relevance scores
- [ ] Implement `POST /api/v1/kb/query` endpoint (RAG — search + LLM answer)
- [ ] Connect RAG endpoint to LangGraph orchestrator (basic version)
- [ ] Build AI chat panel in Knowledge page

#### Week 7: LangGraph Orchestration

- [ ] Design full LangGraph RAG workflow: `query → retrieve → grade → answer → self-correct`
- [ ] Implement query router (is this a factual ICT question?)
- [ ] Implement retrieval grading (are documents relevant?)
- [ ] Implement answer generation with source grounding
- [ ] Implement hallucination check (does answer match sources?)
- [ ] Implement self-correction loop (retry with different query if needed)
- [ ] Connect LangGraph to Ollama LLM (`llama3.1:8b` or similar)
- [ ] Add LangSmith tracing (optional, for debugging)
- [ ] Build AI chat UI with streaming responses

#### Week 8: AI Use Cases

- [ ] Implement `POST /api/v1/agent/grade-setup` (setup grading)
- [ ] Implement `POST /api/v1/agent/journal-review` (journal narrative generation)
- [ ] Implement `POST /api/v1/agent/chat` (general AI chat)
- [ ] Build AI panels in Plan page (setup grading assistant)
- [ ] Build AI panels in Journal page (review narrative)
- [ ] Add AI-generated "related concepts" links in KB search results
- [ ] Add AI-powered setup weakness/strength explainer
- [ ] Write tests for all AI services (mock LLM for CI)
- [ ] **Phase 2 Release**: Full RAG + AI chat + setup grading + journal review

### 2.2 Phase 2 Deliverables

| Deliverable | Description |
|------------|-------------|
| Ollama integration | Local LLM + embedding model serving |
| Haystack pipeline | Document ingestion, chunking, embedding, retrieval |
| LangGraph RAG | Query → retrieve → grade → answer → self-correct |
| pgvector search | Semantic cosine similarity over transcript chunks |
| AI chat panel | Streaming chat with source citations |
| Setup grading | AI-powered pre-trade setup assessment |
| Journal review | AI-generated trade review narratives |
| Celery workers | Async ingestion and background jobs |

---

## Phase 3: Analytics + Research Engine (Weeks 9-12)

**Goal**: Add quantitative analytics, research tools, and backtesting capabilities.

### 3.1 Milestones

#### Week 9: Analytics Engine

- [ ] Build `analytics_service` with core metrics: expectancy, win rate, R-factor, avg R
- [ ] Add session heatmap analytics (time-of-day, day-of-week performance)
- [ ] Add confluence scoring analytics (which concepts correlate with wins)
- [ ] Add drawdown analysis and equity curve simulation
- [ ] Implement `GET /api/v1/analytics/expectancy` endpoint
- [ ] Implement `GET /api/v1/analytics/sessions` endpoint
- [ ] Implement `GET /api/v1/analytics/heatmap` endpoint
- [ ] Build Analytics page with interactive charts (ECharts)
- [ ] Add export to CSV/JSON for external analysis
- [ ] Add date-range filtering on all analytics endpoints

#### Week 10: Research Stack (vectorbt)

- [ ] Integrate `vectorbt` for fast backtesting and signal analysis
- [ ] Build `research_service` with hypothesis testing framework
- [ ] Add ICT-derived indicator backtesting (MSS, FVG, OB detection)
- [ ] Add parameter sweep and optimization tools
- [ ] Build Research page with backtest configuration + results
- [ ] Add Sharpe, Sortino, Calmar ratio calculations
- [ ] Add Monte Carlo simulation for trade sequences
- [ ] Add walk-forward analysis framework
- [ ] Connect research results to planner recommendations

#### Week 11: Backtrader Integration

- [ ] Integrate `Backtrader` for event-driven strategy simulation
- [ ] Add broker-style strategy simulation (slippage, commission, fill models)
- [ ] Add multi-timeframe analysis support
- [ ] Build strategy template system (users can write custom strategies)
- [ ] Add strategy performance comparison (A/B testing)
- [ ] Connect backtest results to journal entries (auto-tag lessons)
- [ ] Add equity curve + trade distribution visualizations
- [ ] Write tests for research + backtest services

#### Week 12: Advanced Analytics

- [ ] Add Kelly Criterion calculator (position sizing optimization)
- [ ] Add risk-of-ruin simulation
- [ ] Add portfolio-level analytics (if multi-asset trading)
- [ ] Add "what-if" scenario analysis (change stop, TP, entry)
- [ ] Add AI-powered pattern recognition in journal entries
- [ ] Add automated weekly/monthly performance reports
- [ ] Add sentiment analysis integration (news/social)
- [ ] **Phase 3 Release**: Full analytics + research + backtesting suite

### 3.3 Phase 3 Deliverables

| Deliverable | Description |
|------------|-------------|
| Analytics engine | Expectancy, heatmaps, confluence scoring, drawdowns |
| vectorbt integration | Fast backtesting and signal research |
| Backtrader integration | Event-driven strategy simulation |
| Research page | Backtest config, results, strategy templates |
| Kelly Criterion | Position sizing optimization tool |
| Monte Carlo | Trade sequence simulation |
| Performance reports | Automated weekly/monthly summaries |

---

## Phase 4: Execution Hardening + Automation (Weeks 13-16)

**Goal**: Harden the execution layer, add alert automation, event bus, and fail-safe guards for semi-automated decision support.

### 4.1 Milestones

#### Week 13: Event Bus + Alert System

- [ ] Implement centralized event bus (Redis pub/sub + Python dataclasses)
- [ ] Define all event types: `TradeOpened`, `TradeClosed`, `AlertTriggered`, `DailyRiskBreached`, `PriceUpdate`
- [ ] Build `alert_service` with rule engine (price thresholds, pattern detection, risk events)
- [ ] Add `POST /api/v1/alerts/rules` endpoint for creating alert rules
- [ ] Add `GET /api/v1/alerts/active` endpoint for monitoring alerts
- [ ] Build Alert Manager page (rules, history, active alerts)
- [ ] Add WebSocket channel for real-time alert delivery (`/ws/alerts`)
- [ ] Add alert severity levels (info, warning, critical)
- [ ] Add alert routing (in-app, Telegram, email)

#### Week 14: Execution Hardening

- [ ] Add pre-trade validation checklist (all risk rules must pass)
- [ ] Add replayable audit log (every order, modification, cancellation logged)
- [ ] Add order state machine (pending → validated → submitted → filled → closed)
- [ ] Add MT5 bridge health monitoring (heartbeat, reconnect)
- [ ] Add broker account sync (positions, balance, margin verification)
- [ ] Add fail-safe guards: daily lockout, max drawdown halt, connection loss halt
- [ ] Add manual override system (with confirmation + audit logging)
- [ ] Add trade execution latency monitoring
- [ ] Add slippage recording and analysis

#### Week 15: Semi-Automated Decision Support

- [ ] Build "signal → suggestion → human approval → execution" workflow
- [ ] Add AI-generated setup confidence scores (not execution triggers)
- [ ] Add confluence scoring automation (auto-check planned vs actual)
- [ ] Add pre-trade risk summary popup (must be acknowledged)
- [ ] Add "paper trading" mode (all signals logged, no real execution)
- [ ] Add strategy comparison mode (run A/B tests in parallel)
- [ ] Add bot coaching recommendations (rule-based, not AI)
- [ ] Add daily/weekly review prompts with AI-generated insights

#### Week 16: Production Hardening

- [ ] Add comprehensive logging (structured JSON logs)
- [ ] Add metrics collection (Prometheus-compatible)
- [ ] Add health checks for all services
- [ ] Add graceful shutdown handling
- [ ] Add database connection pooling + retry logic
- [ ] Add Redis connection resilience
- [ ] Add rate limiting on API endpoints
- [ ] Add input sanitization and SQL injection prevention
- [ ] Write integration tests (end-to-end with Docker Compose)
- [ ] Write load tests for WebSocket connections
- [ ] Add CI/CD pipeline (GitHub Actions: test, build, push)
- [ ] Add backup strategy for PostgreSQL (pg_dump + S3/remote)
- [ ] **Phase 4 Release**: Production-ready trading workstation with fail-safes

### 4.2 Phase 4 Deliverables

| Deliverable | Description |
|------------|-------------|
| Event bus | Redis pub/sub with typed events |
| Alert system | Rule-based alerts with WebSocket delivery |
| Execution hardening | Audit logs, state machines, fail-safes |
| Semi-automation | Signal → suggestion → approval → execution |
| Paper trading | Test mode with full logging |
| Production ops | Logging, metrics, health checks, CI/CD |
| Integration tests | End-to-end tests via Docker Compose |

---

## Timeline Summary

| Phase | Duration | Focus | Key Output |
|-------|----------|-------|------------|
| **Phase 1** | Weeks 1-4 | Foundation | React + FastAPI + PostgreSQL + WebSockets + MT5 bridge |
| **Phase 2** | Weeks 5-8 | AI Brain | Ollama + RAG + LangGraph + Haystack + AI chat |
| **Phase 3** | Weeks 9-12 | Analytics | vectorbt + Backtrader + research engine + performance reports |
| **Phase 4** | Weeks 13-16 | Hardening | Event bus + alerts + fail-safes + semi-automation + production ops |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| **Complexity overwhelm** | Each phase is independently deployable; stop after any phase and still have a working system |
| **Data loss during migration** | Keep old SQLite/localStorage as backup; migrate with scripts; test on copy first |
| **Ollama performance on Mac** | Use smaller models (8B) first; upgrade to vLLM later if latency is unacceptable |
| **MT5 bridge instability** | Maintain current bridge as fallback; new bridge is additive, not replacement |
| **Frontend rebuild scope** | Rebuild one screen at a time; old HTML stays functional until React equivalent is ready |
| **Database migration complexity** | Use Alembic from day 1; write migration scripts for each schema change; never hand-edit |
| **AI hallucination in trading** | Never let AI decide execution; AI is advisory only; deterministic rules enforce all safety |

---

## Success Criteria by Phase

### Phase 1 Success
- [ ] `docker compose up` starts full stack in < 2 minutes
- [ ] All current v7 features work in React frontend
- [ ] PostgreSQL persists all data across restarts
- [ ] WebSocket delivers live price updates < 1s latency
- [ ] MT5 bridge connects and executes orders
- [ ] Telegram sends notifications for trades
- [ ] 80%+ Pytest coverage on services

### Phase 2 Success
- [ ] YouTube transcript ingestion completes in < 5 minutes per video
- [ ] Semantic search returns relevant results in < 2 seconds
- [ ] RAG query answers ICT questions with source citations
- [ ] AI setup grading provides actionable feedback
- [ ] AI journal review generates coherent narratives
- [ ] Ollama runs fully offline (no external API calls)
- [ ] Celery processes ingestion jobs without blocking API

### Phase 3 Success
- [ ] Expectancy calculation matches manual spreadsheet to 2 decimal places
- [ ] vectorbt backtest runs 1000 trades in < 30 seconds
- [ ] Backtrader strategy simulation produces accurate fill records
- [ ] Session heatmap shows actionable time-of-day patterns
- [ ] Kelly calculator suggests safe position sizes
- [ ] Research results auto-export to journal tags

### Phase 4 Success
- [ ] Alert system triggers within 5 seconds of condition met
- [ ] Daily risk lockout prevents any trade after limit breached
- [ ] Audit log captures every state change with timestamp + user
- [ ] Paper trading mode produces identical logs to live mode
- [ ] System recovers gracefully from MT5 bridge disconnect
- [ ] CI/CD pipeline passes all tests before every deploy
- [ ] Database backup runs automatically daily

---

## Next Steps

1. **Review this roadmap** — confirm priorities, adjust timelines, flag any concerns
2. **Approve Phase 1 scope** — confirm the 4-week foundation sprint is the right start
3. **Initialize repo** — create branch `phase-1/foundation` and begin scaffolding
4. **Set up Docker** — verify PostgreSQL + Redis + pgvector work on your Mac
5. **First task**: Create the monorepo structure and Docker Compose file

---

**Related Documents**:
- `ARCHITECTURE.md` — Full technical architecture, stack decisions, and service definitions
- `README.md` — Current project overview and API endpoints
- `TELEGRAM_SETUP.md` — Telegram bot configuration guide
- `MACBOOK-SETUP-GUIDE.md` — Mac-specific setup instructions
