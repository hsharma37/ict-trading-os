"""FastAPI Application - ICT Trading OS Backend."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.auth import auth_middleware
from app.routers import market, ict, signals, trades, quant, orders, plans, kb, bot, playground, analytics, alerts, research, telegram, mt5, news
from app.routers import settings as settings_router

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

# Optional API key auth middleware (enabled via AUTH_ENABLED env var)
app.middleware("http")(auth_middleware)

app.include_router(market.router)
app.include_router(ict.router)
app.include_router(signals.router)
app.include_router(trades.router)
app.include_router(quant.router)
app.include_router(orders.router)
app.include_router(plans.router)
app.include_router(kb.router)
app.include_router(bot.router)
app.include_router(playground.router)
app.include_router(analytics.router)
app.include_router(alerts.router)
app.include_router(research.router)
app.include_router(telegram.router)
app.include_router(mt5.router)
app.include_router(news.router)
app.include_router(settings_router.router)

@app.get("/")
def root():
    return {
        "name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "operational",
        "endpoints": {
            "market": "/market", "ict_analysis": "/ict", "signals": "/signals",
            "trades": "/trades", "quant_lab": "/quant", "telegram": "/telegram"
        }
    }

@app.get("/health")
def health():
    from datetime import datetime
    from app.core.database import db
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db.get_stats()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
