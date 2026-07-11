"""FastAPI Application - ICT Trading OS Backend."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.auth import auth_middleware, validate_auth_config
from app.routers import market, ict, signals, trades, quant, orders, plans, kb, bot, playground, analytics, alerts, research, telegram, mt5, news
from app.routers import settings as settings_router

validate_auth_config()

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

# Strip /api prefix when running on Vercel (frontend uses /api base URL)
@app.middleware("http")
async def strip_api_prefix(request: Request, call_next):
    if request.url.path == "/api":
        request.scope["path"] = "/"
    elif request.url.path.startswith("/api/"):
        request.scope["path"] = request.url.path[4:]
    response = await call_next(request)
    return response

# Production safety API-key auth middleware.
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

@app.get("/health")
def health():
    from datetime import datetime
    from app.core.database import db
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db.get_stats(),
        "storage": db.storage_info(),
    }

# Serve React SPA for root path (Vercel routes / to FastAPI by default)
@app.get("/")
async def serve_root():
    return FileResponse("public/index.html")

# Serve React SPA for any non-API path (fallback for direct SPA URL access)
@app.get("/{path:path}")
async def serve_spa(path: str):
    return FileResponse("public/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
