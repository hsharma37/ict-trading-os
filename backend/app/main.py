"""
FastAPI application entry point.

Initializes the app, registers routers, sets up middleware,
and handles lifespan events (database, Redis, etc.).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import settings
from app.database import init_db
from app.api.v1 import (
    plans, trades, risk, journal, market, telegram, mt5, health,
    kb, agent, alert, analytics, research, suggestions, audit,
    fail_safe, websocket,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events:
    - Startup: create database tables (if not using Alembic exclusively)
    - Shutdown: clean up connections
    """
    # Startup
    init_db()
    yield
    # Shutdown


app = FastAPI(
    title="ICT Trading OS API",
    description="Backend for trading plans, execution, risk, journal, analytics, research, and alerts",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ────────────────────────────────────────────────
# Middleware
# ────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ────────────────────────────────────────────────
# API v1 Routers
# ────────────────────────────────────────────────
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(plans.router, prefix="/api/v1/plans", tags=["plans"])
app.include_router(trades.router, prefix="/api/v1/trades", tags=["trades"])
app.include_router(risk.router, prefix="/api/v1/risk", tags=["risk"])
app.include_router(journal.router, prefix="/api/v1/journal", tags=["journal"])
app.include_router(market.router, prefix="/api/v1/market", tags=["market"])
app.include_router(telegram.router, prefix="/api/v1/telegram", tags=["telegram"])
app.include_router(mt5.router, prefix="/api/v1/mt5", tags=["mt5"])
app.include_router(kb.router, prefix="/api/v1/kb", tags=["knowledge"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["agent"])
app.include_router(alert.router, prefix="/api/v1/alerts", tags=["alerts"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(research.router, prefix="/api/v1/research", tags=["research"])
app.include_router(suggestions.router, prefix="/api/v1/suggestions", tags=["suggestions"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
app.include_router(fail_safe.router, prefix="/api/v1/fail-safe", tags=["fail-safe"])
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])
