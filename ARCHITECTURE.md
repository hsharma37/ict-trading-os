# ICT Trading OS — Target Architecture

> **Version**: 1.0  
> **Date**: 2026-06-26  
> **Status**: Draft — ready for Phase 1 implementation

---

## 1. Executive Summary

The current `ict-trading-os` is a single-file HTML dashboard with mixed JavaScript logic, ad-hoc state management, and limited backend API coverage. This document defines the target architecture to transform it into a **professional, maintainable, local-first trading workstation** with a clean separation between frontend presentation, backend domain logic, and AI services.

### Core Principles

1. **Python owns the domain logic** — trading plans, risk rules, journal scoring, signal generation, and alerting.
2. **Frontend is a thin client** — React + TypeScript renders forms, charts, tables, and AI panels; it does not make trading decisions.
3. **Deterministic rules guard capital** — position sizing, stop-loss enforcement, daily lockouts, and execution safety checks are hardcoded Python rules, never delegated to AI.
4. **AI augments decision-making** — RAG over transcripts, sentiment analysis, setup grading, and journal narrative generation are AI-powered but advisory-only.
5. **Local-first, open-source stack** — Ollama, pgvector, Haystack, LangGraph, and FastAPI run entirely on your machine.

---

## 2. Technology Stack

### 2.1 Frontend

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | React 18 + TypeScript | Component-based UI with strict typing |
| Build Tool | Vite | Fast dev server, optimized production builds |
| State (Server) | TanStack Query | Server-state caching, sync, background refetch |
| State (Client) | Zustand | Lightweight local UI state |
| Tables | TanStack Table / AG Grid Community | Trade grids, journal views, plan lists |
| Charts | TradingView Lightweight Charts | Candlestick + indicator overlays |
| Secondary Charts | Apache ECharts | Analytics, heatmaps, distribution plots |
| Components | shadcn/ui + Radix UI | Accessible, composable UI primitives |
| Styling | Tailwind CSS | Utility-first design system |
| Forms | React Hook Form + Zod | Type-safe validation |

> **Why Vite + React over Next.js?**  
> Your app is a dashboard/workstation, not a public content site. SSR is unnecessary; Vite gives a simpler build pipeline and faster HMR for a SPA.

### 2.2 Backend

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API Framework | FastAPI | REST + WebSocket endpoints, auto-generated OpenAPI docs |
| Data Models | SQLModel / Pydantic | Typed ORM-style schemas + validation |
| Migrations | Alembic | Schema versioning and evolution |
| Database | PostgreSQL 15+ | Primary relational store |
| Vector Extension | pgvector | Embedding storage for RAG |
| Cache + Pub/Sub | Redis 7 | Task coordination, session cache, WebSocket broadcast |
| Background Jobs | Celery + Redis | Transcript ingestion, embedding generation, alert scans |
| Task Results | Celery + PostgreSQL | Persistent job result store |
| WebSocket | FastAPI native | Live price updates, order fills, alert delivery |
| Realtime Bus | Redis pub/sub | Cross-process event broadcasting |

### 2.3 AI & RAG Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Local LLM | Ollama | macOS-optimized local model serving |
| Inference Scale | vLLM (future) | Faster batched serving if needed |
| Embeddings | Nomic Embed / BGE via Ollama | Local, privacy-preserving text embeddings |
| RAG Orchestration | Haystack | Document pipelines, retrievers, QA |
| Agent Workflows | LangGraph | Stateful routing: query → retrieve → grade → answer → self-correct |
| Model Routing | LiteLLM | Unified OpenAI-compatible API over Ollama, vLLM, or hosted |
| Vector Store | pgvector (primary) | Postgres-native embeddings |
| Vector Store (future) | Qdrant | If retrieval scale or filtering grows |

### 2.4 Quant & Research Stack

| Tool | Use Case |
|------|----------|
| vectorbt | Fast exploratory research, portfolio stats, signal backtesting |
| Backtrader | Event-driven backtesting, trade lifecycle simulation |
| Qlib (future) | ML-driven factor research, institutional-style workflows |
| Riskfolio-Lib | Portfolio risk experiments, CVaR, drawdown analysis |

### 2.5 Infrastructure & Deployment

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Local Orchestration | Docker Compose | One-command local stack: Postgres, Redis, API, frontend, AI workers |
| Reverse Proxy | Caddy / Nginx | TLS termination, WebSocket routing |
| Process Manager | PM2 (dev) / systemd (prod) | Long-running services |
| Future Cloud | VPS (Hetzner / DigitalOcean) | Lightweight remote hosting if needed |

---

## 3. System Architecture

### 3.1 High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │   Dashboard SPA │  │   Planner SPA   │  │  Journal SPA    │              │
│  │   (React/Vite)  │  │   (React/Vite)  │  │  (React/Vite)   │              │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │
│           │                    │                    │                       │
│           └────────────────────┴────────────────────┘                       │
│                              │                                               │
│                              ▼                                               │
│                    ┌─────────────────┐                                      │
│                    │  TanStack Query │  ← Server-state cache                 │
│                    │    + Zustand    │  ← Client UI state                    │
│                    └────────┬────────┘                                      │
└─────────────────────────────┼───────────────────────────────────────────────┘
                              │
                              │ HTTPS / WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                     │
│                    ┌─────────────────┐                                      │
│                    │   FastAPI App   │                                      │
│                    │  REST + WS Router│                                      │
│                    └────────┬────────┘                                      │
│                             │                                                │
│         ┌───────────────────┼───────────────────┐                           │
│         ▼                   ▼                   ▼                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │   REST API  │    │  WebSocket  │    │   Webhook   │                     │
│  │  /api/v1/*  │    │  /ws/stream │    │  /webhooks/*│                     │
│  └─────────────┘    └─────────────┘    └─────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SERVICE LAYER (Python)                             │
│                                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │  Planner    │ │  Execution  │ │    Risk     │ │   Journal   │          │
│  │  Service    │ │  Service    │ │  Service    │ │  Service    │          │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘          │
│                                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │  Analytics  │ │  Telegram   │ │  Market     │ │  Knowledge  │          │
│  │  Service    │ │  Service    │ │  Data Svc   │ │  Service    │          │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘          │
│                                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                          │
│  │   Agent     │ │  Sentiment  │ │   Alert     │                          │
│  │  Service    │ │  Service    │ │  Service    │                          │
│  └─────────────┘ └─────────────┘ └─────────────┘                          │
│                                                                              │
│  ┌─────────────────────────────────────────┐                               │
│  │         LangGraph Orchestrator          │  ← AI workflow engine          │
│  │  query → retrieve → grade → answer →    │  ← Self-correcting RAG         │
│  │  self_correct → source_check            │                               │
│  └─────────────────────────────────────────┘                               │
│                                                                              │
│  ┌─────────────────────────────────────────┐                               │
│  │         Haystack Pipeline               │  ← Document ingestion,         │
│  │  PDF/YouTube → chunk → embed → store    │  ← retrievers, QA              │
│  └─────────────────────────────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA & EVENT LAYER                                 │
│                                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │  PostgreSQL │ │   Redis     │ │  pgvector   │ │  (Qdrant)   │          │
│  │  (Primary)  │ │  (Cache/    │ │  (Embeds)   │ │  (Future)   │          │
│  │             │ │   Pub/Sub)  │ │             │ │             │          │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘          │
│                                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                            │
│  │   Celery    │ │   Redis     │ │  PostgreSQL │                            │
│  │  (Workers)  │ │  (Broker)   │ │  (Result)   │                            │
│  └─────────────┘ └─────────────┘ └─────────────┘                            │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL LAYER                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │   Yahoo     │ │    MT5      │ │  Telegram   │ │   Ollama    │          │
│  │  Finance    │ │   Bridge    │ │   Bot API   │ │  (Local)    │          │
│  │   API       │ │  (Python)   │ │             │ │             │          │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘          │
│                                                                              │
│  ┌─────────────┐ ┌─────────────┐                                           │
│  │   YouTube   │ │  TradingView│                                           │
│  │   Data API  │ │  Lightweight│                                           │
│  │             │ │   Charts    │                                           │
│  └─────────────┘ └─────────────┘                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Service Definitions

| Service | Responsibility | Key Endpoints / Topics |
|---------|-------------|----------------------|
| **planner_service** | Daily/weekly trading plans, bias worksheets, confluence scoring | `POST /plans`, `GET /plans/{id}`, `PATCH /plans/{id}/bias` |
| **execution_service** | Order lifecycle, MT5 bridge proxy, fill tracking | `POST /trades`, `POST /trades/{id}/close`, `GET /trades` |
| **risk_service** | Position sizing, daily loss limits, lockouts, margin checks | `POST /risk/validate`, `GET /risk/daily-status`, `GET /risk/lot-size` |
| **journal_service** | Trade journaling, review scoring, pattern tagging | `POST /journal/entries`, `GET /journal/stats`, `POST /journal/{id}/grade` |
| **analytics_service** | Expectancy, session heatmaps, confluence analytics, win rate | `GET /analytics/expectancy`, `GET /analytics/sessions`, `GET /analytics/heatmap` |
| **telegram_service** | Bot commands, alert delivery, order confirmation messages | `POST /telegram/send`, `POST /telegram/alert`, Webhook handler |
| **market_data_service** | Price feeds, candle history, symbol metadata, calendar events | `GET /market/price/{symbol}`, `GET /market/history/{symbol}`, WS `/ws/price/{symbol}` |
| **knowledge_service** | Transcript ingestion, chunking, embedding, search, RAG retrieval | `POST /kb/sources`, `GET /kb/search`, `POST /kb/ingest`, `POST /kb/query` |
| **agent_service** | AI chat, setup grading, journal narrative, concept extraction | `POST /agent/chat`, `POST /agent/grade-setup`, `POST /agent/journal-review` |
| **sentiment_service** | News sentiment, social scraping, fear/greed indicators | `POST /sentiment/analyze`, `GET /sentiment/summary` |
| **alert_service** | Signal generation, condition monitoring, alert routing | `POST /alerts/rules`, `GET /alerts/active`, `WS /ws/alerts` |

---

## 4. Database Schema (Core Entities)

### 4.1 PostgreSQL Tables

```sql
-- Users (single-user mode for now, extensible)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Trading Plans
CREATE TABLE trading_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    date DATE NOT NULL,
    session TEXT CHECK (session IN ('london', 'ny', 'asia', 'combined')),
    bias_direction TEXT CHECK (bias_direction IN ('bullish', 'bearish', 'neutral')),
    narrative TEXT,
    confluence_tags TEXT[],
    killzones TEXT[],
    max_trades INTEGER DEFAULT 3,
    daily_loss_limit DECIMAL(12,2),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Trades (executions)
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    plan_id UUID REFERENCES trading_plans(id),
    symbol TEXT NOT NULL,
    direction TEXT CHECK (direction IN ('long', 'short')),
    entry_price DECIMAL(18,8),
    stop_loss DECIMAL(18,8),
    take_profit_1 DECIMAL(18,8),
    take_profit_2 DECIMAL(18,8),
    take_profit_3 DECIMAL(18,8),
    lot_size DECIMAL(12,6),
    leverage INTEGER DEFAULT 1,
    risk_amount DECIMAL(12,2),
    status TEXT CHECK (status IN ('pending', 'open', 'closed', 'cancelled')),
    outcome TEXT CHECK (outcome IN ('win', 'loss', 'breakeven', 'open')),
    pnl DECIMAL(12,2),
    pnl_pips DECIMAL(12,2),
    exit_price DECIMAL(18,8),
    exit_time TIMESTAMPTZ,
    entry_time TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Journal Entries
CREATE TABLE journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id UUID REFERENCES trades(id),
    user_id UUID REFERENCES users(id),
    pre_trade_notes TEXT,
    post_trade_notes TEXT,
    emotion_score INTEGER CHECK (emotion_score BETWEEN 1 AND 10),
    setup_grade INTEGER CHECK (setup_grade BETWEEN 1 AND 10),
    execution_grade INTEGER CHECK (execution_grade BETWEEN 1 AND 10),
    management_grade INTEGER CHECK (management_grade BETWEEN 1 AND 10),
    tags TEXT[],
    lessons TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Knowledge Base Sources
CREATE TABLE kb_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    source_type TEXT CHECK (source_type IN ('youtube', 'transcript', 'pdf', 'note')),
    title TEXT NOT NULL,
    url TEXT,
    content TEXT,
    metadata JSONB,
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- KB Chunks (for pgvector)
CREATE TABLE kb_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES kb_sources(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768),  -- Nomic embed dimension
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Alerts / Signals
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    symbol TEXT NOT NULL,
    alert_type TEXT CHECK (alert_type IN ('price', 'ict_pattern', 'sentiment', 'risk', 'custom')),
    condition JSONB NOT NULL,
    message TEXT,
    is_active BOOLEAN DEFAULT true,
    triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Daily Risk Ledger
CREATE TABLE daily_risk_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    date DATE NOT NULL,
    starting_balance DECIMAL(12,2),
    daily_loss_limit DECIMAL(12,2),
    current_loss DECIMAL(12,2) DEFAULT 0,
    trades_taken INTEGER DEFAULT 0,
    max_trades INTEGER DEFAULT 3,
    is_locked BOOLEAN DEFAULT false,
    lock_reason TEXT,
    UNIQUE(user_id, date)
);
```

### 4.2 Redis Key Patterns

| Pattern | Purpose | TTL |
|---------|---------|-----|
| `price:{symbol}` | Latest price cache | 60s |
| `session:{user_id}` | User session data | 24h |
| `ws:connections` | Active WebSocket connection registry | — |
| `alerts:pending` | Pending alert queue | — |
| `celery:task:*` | Background job metadata | — |

---

## 5. AI / RAG Architecture

### 5.1 LangGraph Workflow — Adaptive RAG for ICT Knowledge

```
User Query
    │
    ▼
┌─────────────────┐
│  Query Router   │  ← "Is this a factual ICT question?"
│  (LLM classifier)│
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐  ┌─────────┐
│ RAG   │  │  Direct │
│ Path  │  │  LLM    │
└───┬───┘  └─────────┘
    │
    ▼
┌─────────────────┐
│  Document       │  ← Haystack retriever over pgvector
│  Retrieval      │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌─────────┐  ┌─────────┐
│ Relevant│  │ Irrelevant│
│  Docs   │  │  Docs     │
└────┬────┘  └────┬────┘
     │            │
     ▼            ▼
┌─────────┐  ┌─────────────┐
│  Grade  │  │  Web Search │  ← (future expansion)
│  Check  │  │  Fallback   │
└────┬────┘  └─────────────┘
     │
     ▼
┌─────────────┐
│  Generate   │  ← LLM synthesizes answer with sources
│  Answer     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Hallucination│  ← Check if answer is grounded in docs
│  Check      │
└──────┬──────┘
       │
  ┌────┴────┐
  ▼         ▼
┌──────┐  ┌─────────┐
│ Pass │  │  Fail   │
│      │  │  → Retry│
└──┬───┘  └────┬────┘
   │           │
   ▼           ▼
┌──────────┐  ┌─────────┐
│  Return  │  │  Max    │
│  Answer  │  │  Retries│
│  + Sources│  │  → Error│
└──────────┘  └─────────┘
```

### 5.2 Haystack Pipeline — Transcript Ingestion

```
YouTube URL / Transcript Text
    │
    ▼
┌─────────────────┐
│  Fetch / Parse  │  ← YouTube transcript extraction or PDF parsing
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Preprocess     │  ← Clean, normalize, remove timestamps
│  (Cleaner)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Split / Chunk  │  ← Semantic chunking (512 tokens, 50 overlap)
│  (DocumentSplitter)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Embed          │  ← Nomic Embed via Ollama
│  (Embedder)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Store          │  ← pgvector upsert
│  (DocumentStore)│
└─────────────────┘
```

### 5.3 AI Use Cases (What AI Does / Does NOT Do)

| ✅ AI Handles | ❌ AI Does NOT Handle |
|-------------|----------------------|
| Querying ICT transcripts & notes | Position sizing calculations |
| Summarizing journal patterns | Loss-limit enforcement |
| Explaining setup weaknesses/strengths | Stop/target validation |
| Extracting concepts from videos | Daily lockout decisions |
| Generating trader review narratives | Order execution authorization |
| Surfacing related KB examples | Live execution safety checks |
| Alert explanation text | Risk rule validation |
| Sentiment analysis | Capital allocation decisions |

---

## 6. API Design (FastAPI)

### 6.1 REST Endpoints — Core v1

```
GET    /health                    → System status
POST   /auth/token              → JWT token (single-user for now)

-- Plans
GET    /api/v1/plans            → List plans
POST   /api/v1/plans            → Create plan
GET    /api/v1/plans/{id}      → Get plan
PATCH  /api/v1/plans/{id}      → Update plan
DELETE /api/v1/plans/{id}      → Delete plan

-- Trades / Execution
GET    /api/v1/trades           → List trades
POST   /api/v1/trades           → Create trade
GET    /api/v1/trades/{id}      → Get trade
POST   /api/v1/trades/{id}/close → Close trade
POST   /api/v1/trades/{id}/partial → Partial close

-- Risk
POST   /api/v1/risk/validate    → Validate trade against risk rules
GET    /api/v1/risk/daily-status → Daily risk ledger status
POST   /api/v1/risk/lot-size    → Calculate lot size (leverage-aware)

-- Journal
GET    /api/v1/journal          → Journal entries
POST   /api/v1/journal          → Create entry
GET    /api/v1/journal/stats    → Aggregate stats
POST   /api/v1/journal/{id}/grade → Self-grade entry

-- Market Data
GET    /api/v1/market/price/{symbol}      → Live price
GET    /api/v1/market/history/{symbol}    → Candle history
GET    /api/v1/market/calendar            → Economic calendar

-- Analytics
GET    /api/v1/analytics/expectancy       → Expectancy metrics
GET    /api/v1/analytics/sessions         → Session performance
GET    /api/v1/analytics/heatmap          → Confluence heatmap
GET    /api/v1/analytics/kelly           → Kelly criterion

-- Knowledge Base
POST   /api/v1/kb/sources       → Add source
GET    /api/v1/kb/sources       → List sources
DELETE /api/v1/kb/sources/{id}  → Remove source
POST   /api/v1/kb/search        → Semantic search
POST   /api/v1/kb/query         → RAG query (AI answer)

-- Agent / AI
POST   /api/v1/agent/chat       → AI chat session
POST   /api/v1/agent/grade-setup → Setup grading
POST   /api/v1/agent/journal-review → Journal review

-- Telegram
POST   /api/v1/telegram/send    → Send message
POST   /api/v1/telegram/alert   → Send alert
POST   /api/v1/telegram/test    → Test connection

-- MT5 Bridge
POST   /api/v1/mt5/trade        → Proxy trade to MT5
GET    /api/v1/mt5/account      → MT5 account info
GET    /api/v1/mt5/positions    → Open positions
GET    /api/v1/mt5/status       → Bridge status

-- Alerts
GET    /api/v1/alerts           → Active alerts
POST   /api/v1/alerts           → Create alert rule
DELETE /api/v1/alerts/{id}      → Delete alert
```

### 6.2 WebSocket Channels

| Channel | Path | Events |
|---------|------|--------|
| Price Stream | `/ws/market/{symbol}` | `price_update`, `candle_close` |
| Trade Updates | `/ws/trades` | `trade_opened`, `trade_closed`, `fill_update` |
| Alert Stream | `/ws/alerts` | `alert_triggered`, `alert_dismissed` |
| System Status | `/ws/system` | `heartbeat`, `service_status` |

### 6.3 Pydantic Models (Example)

```python
from sqlmodel import SQLModel, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Literal
from uuid import UUID, uuid4

class TradingPlan(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    date: date
    session: Literal["london", "ny", "asia", "combined"] = "combined"
    bias_direction: Literal["bullish", "bearish", "neutral"] = "neutral"
    narrative: Optional[str] = None
    confluence_tags: List[str] = Field(default_factory=list, sa_column=List[str])
    killzones: List[str] = Field(default_factory=list, sa_column=List[str])
    max_trades: int = 3
    daily_loss_limit: Decimal = Field(max_digits=12, decimal_places=2)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TradeBase(SQLModel):
    symbol: str
    direction: Literal["long", "short"]
    entry_price: Decimal = Field(max_digits=18, decimal_places=8)
    stop_loss: Decimal = Field(max_digits=18, decimal_places=8)
    take_profit_1: Optional[Decimal] = Field(max_digits=18, decimal_places=8)
    take_profit_2: Optional[Decimal] = Field(max_digits=18, decimal_places=8)
    take_profit_3: Optional[Decimal] = Field(max_digits=18, decimal_places=8)
    lot_size: Decimal = Field(max_digits=12, decimal_places=6)
    leverage: int = 1
    risk_amount: Decimal = Field(max_digits=12, decimal_places=2)

class Trade(TradeBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    plan_id: Optional[UUID] = Field(foreign_key="trading_plans.id")
    status: Literal["pending", "open", "closed", "cancelled"] = "pending"
    outcome: Optional[Literal["win", "loss", "breakeven"]] = None
    pnl: Optional[Decimal] = Field(max_digits=12, decimal_places=2)
    pnl_pips: Optional[Decimal] = Field(max_digits=12, decimal_places=2)
    exit_price: Optional[Decimal] = Field(max_digits=18, decimal_places=8)
    exit_time: Optional[datetime] = None
    entry_time: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## 7. Frontend Architecture

### 7.1 Route Structure

```
/                       → Dashboard (overview, market, active trades)
/plan                   → Daily Plan (bias, killzones, narrative)
/execute                → Execution Console (order entry, MT5 status)
/journal                → Journal (entries, stats, review flow)
/knowledge              → Knowledge Base (sources, search, RAG chat)
/analytics              → Analytics (expectancy, heatmaps, session stats)
/alerts                 → Alert Manager (rules, history, active)
/settings               → Settings (risk params, MT5 config, Telegram)
```

### 7.2 Component Hierarchy (Example)

```
App
├── Layout
│   ├── Sidebar (navigation)
│   ├── TopBar (market ticker, connection status)
│   └── MainContent
│       ├── DashboardPage
│       │   ├── MarketWidget (price, mini-chart)
│       │   ├── ActiveTradesWidget
│       │   ├── PlanSummaryWidget
│       │   └── AlertFeedWidget
│       ├── PlanPage
│       │   ├── PlanForm
│       │   ├── BiasSelector
│       │   ├── KillzonePicker
│       │   └── ConfluenceChecklist
│       ├── ExecutePage
│       │   ├── OrderEntryForm
│       │   ├── LotCalculator (leverage-aware)
│       │   ├── RiskPreview
│       │   └── MT5StatusPanel
│       ├── JournalPage
│       │   ├── EntryList
│       │   ├── EntryDetail
│       │   ├── StatsCards
│       │   └── GradePanel
│       ├── KnowledgePage
│       │   ├── SourceUploader
│       │   ├── SourceList
│       │   ├── SearchPanel
│       │   └── AIChatPanel
│       ├── AnalyticsPage
│       │   ├── ExpectancyChart
│       │   ├── SessionHeatmap
│       │   ├── ConfluenceMatrix
│       │   └── KellyPanel
│       └── SettingsPage
│           ├── RiskConfigForm
│           ├── MT5ConfigForm
│           ├── TelegramConfigForm
│           └── AIConfigForm
```

### 7.3 State Management Strategy

| State Type | Store | Example |
|------------|-------|---------|
| Server State | TanStack Query | Trades, plans, journal entries, market data |
| Local UI State | Zustand | Sidebar collapse, modal open, active tab |
| Form State | React Hook Form | Order entry form, plan form |
| Global Cache | TanStack Query | Symbol metadata, price history |
| WebSocket Data | Zustand + React | Live price ticks, alert triggers |

---

## 8. Event & Messaging Architecture

### 8.1 Event Types

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal
from uuid import UUID

@dataclass
class TradeOpenedEvent:
    trade_id: UUID
    symbol: str
    direction: Literal["long", "short"]
    entry_price: Decimal
    lot_size: Decimal
    leverage: int
    risk_amount: Decimal
    timestamp: datetime
    source: Literal["manual", "mt5", "api"]

@dataclass
class TradeClosedEvent:
    trade_id: UUID
    exit_price: Decimal
    pnl: Decimal
    pnl_pips: Decimal
    outcome: Literal["win", "loss", "breakeven"]
    exit_time: datetime
    timestamp: datetime

@dataclass
class AlertTriggeredEvent:
    alert_id: UUID
    symbol: str
    alert_type: str
    message: str
    triggered_at: datetime
    severity: Literal["info", "warning", "critical"]

@dataclass
class DailyRiskBreachedEvent:
    user_id: UUID
    date: datetime
    daily_loss: Decimal
    limit: Decimal
    reason: str
    timestamp: datetime

@dataclass
class PriceUpdateEvent:
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    timestamp: datetime
```

### 8.2 Event Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Trade Service │────▶│  Event Bus      │────▶│  Telegram Svc   │
│   (execution)   │     │  (Redis pub/sub) │     │  (notification) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ├────▶┌─────────────────┐
                               │     │  WebSocket Hub  │
                               │     │  (broadcast)    │
                               │     └─────────────────┘
                               │
                               ├────▶┌─────────────────┐
                               │     │  Journal Svc    │
                               │     │  (auto-log)     │
                               │     └─────────────────┘
                               │
                               ├────▶┌─────────────────┐
                               │     │  Analytics Svc  │
                               │     │  (agg update)   │
                               │     └─────────────────┘
                               │
                               └────▶┌─────────────────┐
                                     │  Alert Svc      │
                                     │  (cascade rules)│
                                     └─────────────────┘
```

---

## 9. Security & Safety

### 9.1 Trading Safety Rules (Hardcoded in Python)

| Rule | Implementation | Layer |
|------|---------------|-------|
| Daily Loss Limit | `daily_risk_ledger` table + `risk_service` | API validation |
| Max Trades Per Day | `max_trades` on plan + ledger counter | API validation |
| Stop-Loss Required | `stop_loss` is non-nullable in `Trade` model | DB + API |
| Leverage Cap | Max 100x, validated against account margin | `risk_service` |
| Lockout Enforcement | `is_locked` boolean on daily ledger | `risk_service` |
| Order Size Validation | Lot size within broker limits | `risk_service` |
| Killzone Validation | Only trade during planned killzones | `planner_service` |

### 9.2 Authentication & Authorization (Future-Ready)

| Layer | Approach |
|-------|----------|
| Current (Phase 1) | Single-user, no auth (local-only) |
| Phase 3 | JWT tokens, `users` table, role-based access |
| API Keys | Per-service API keys for MT5 bridge, Telegram |
| WebSocket | Token-based auth on upgrade |

---

## 10. Deployment & Operations

### 10.1 Docker Compose (Local Development)

```yaml
# docker-compose.yml (Phase 1)
version: "3.8"
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: ictos
      POSTGRES_PASSWORD: ictos
      POSTGRES_DB: ictos
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://ictos:ictos@postgres:5432/ictos
      REDIS_URL: redis://redis:6379/0
    depends_on: [postgres, redis]
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      VITE_API_URL: http://localhost:8000
    volumes:
      - ./frontend:/app

  celery-worker:
    build: ./backend
    command: celery -A app.jobs worker --loglevel=info
    environment:
      DATABASE_URL: postgresql://ictos:ictos@postgres:5432/ictos
      REDIS_URL: redis://redis:6379/0
    depends_on: [postgres, redis]

  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes:
      - ollama_data:/root/.ollama

volumes:
  postgres_data:
  ollama_data:
```

### 10.2 Environment Variables

```bash
# .env
DATABASE_URL=postgresql://ictos:ictos@localhost:5432/ictos
REDIS_URL=redis://localhost:6379/0

# API
API_HOST=0.0.0.0
API_PORT=8000
API_SECRET_KEY=your-secret-key-here

# Frontend
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws

# AI
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
EMBEDDING_MODEL=nomic-embed-text:latest

# MT5 Bridge
MT5_BRIDGE_URL=http://localhost:5000

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=db+postgresql://ictos:ictos@localhost:5432/ictos
```

---

## 11. Technology Comparison: Before vs After

| Aspect | Current (HTML v7) | Target (React + FastAPI) |
|--------|-------------------|-------------------------|
| **UI** | Single 300KB HTML file | Modular React SPA with components |
| **State** | ad-hoc JS objects, localStorage | TanStack Query + Zustand + PostgreSQL |
| **API** | Hand-rolled JS fetch | Typed FastAPI with OpenAPI docs |
| **Database** | SQLite, ad-hoc schemas | PostgreSQL + Alembic migrations |
| **Vector Search** | None | pgvector + Haystack |
| **AI** | Embedded ad-hoc | LangGraph + Ollama + LiteLLM |
| **Realtime** | Manual polling | WebSockets + Redis pub/sub |
| **Background Jobs** | None | Celery + Redis |
| **Testing** | Manual browser testing | Pytest + Vitest + CI/CD ready |
| **Deployment** | Static file + manual server | Docker Compose + reproducible builds |
| **Scalability** | Single file limit | Modular service expansion |

---

## 12. References & Resources

| Resource | Link |
|----------|------|
| FastAPI + SQLModel + Alembic | https://sqlmodel.tiangolo.com/ |
| TanStack Query | https://tanstack.com/query/latest |
| Zustand | https://github.com/pmndrs/zustand |
| shadcn/ui | https://ui.shadcn.com/ |
| TradingView Lightweight Charts | https://tradingview.github.io/lightweight-charts/ |
| Apache ECharts | https://echarts.apache.org/ |
| Haystack | https://haystack.deepset.ai/ |
| LangGraph | https://langchain-ai.github.io/langgraph/ |
| Ollama | https://ollama.com/ |
| pgvector | https://github.com/pgvector/pgvector |
| vectorbt | https://vectorbt.dev/ |
| Backtrader | https://www.backtrader.com/ |
| LiteLLM | https://docs.litellm.ai/ |
| Celery | https://docs.celeryproject.org/ |

---

## 13. Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-26 | Vite + React over Next.js | SPA dashboard, no SSR needs, simpler build |
| 2026-06-26 | SQLModel over SQLAlchemy raw | Pydantic integration, cleaner FastAPI models |
| 2026-06-26 | Haystack over LlamaIndex | Focus on QA/retrieval over multi-source connectors |
| 2026-06-26 | pgvector over Qdrant (Phase 1) | Single DB, simpler ops, swap later if needed |
| 2026-06-26 | Ollama over vLLM (Phase 1) | macOS native, easiest local setup |
| 2026-06-26 | Celery over RQ | More mature ecosystem, better task result backend |
| 2026-06-26 | No auth in Phase 1 | Single-user local app, add JWT in Phase 3 |

---

**Next Document**: See `MIGRATION_ROADMAP.md` for the phased implementation plan.
