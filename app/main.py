"""FastAPI Application - ICT Trading OS Backend."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import market, ict, signals, trades, quant, orders, plans, kb, bot

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Live market data, ICT pattern detection, signals, and quant analytics"
)

origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router)
app.include_router(ict.router)
app.include_router(signals.router)
app.include_router(trades.router)
app.include_router(quant.router)
app.include_router(orders.router)
app.include_router(plans.router)
app.include_router(kb.router)
app.include_router(bot.router)

@app.get("/")
def root():
    return {
        "name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "operational",
        "endpoints": {
            "market": "/market", "ict_analysis": "/ict", "signals": "/signals",
            "trades": "/trades", "quant_lab": "/quant"
        }
    }

@app.get("/health")
def health():
    from datetime import datetime
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
