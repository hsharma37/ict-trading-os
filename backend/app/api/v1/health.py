"""
Health check API — comprehensive system status.
"""
from fastapi import APIRouter, Depends
from sqlmodel import Session, text
from app.database import get_db, engine
from app.core.event_bus import event_bus
from app.services.fail_safe_service import check_mt5_connection_health

router = APIRouter()


@router.get("/", summary="Basic health check")
async def health():
    return {"status": "healthy", "service": "ict-trading-os"}


@router.get("/deep", summary="Deep health check")
async def deep_health(db: Session = Depends(get_db)):
    """Comprehensive health check including database, Redis, and MT5 bridge."""
    results = {
        "status": "healthy",
        "checks": {},
    }

    # Database
    try:
        db.execute(text("SELECT 1"))
        results["checks"]["database"] = {"status": "healthy"}
    except Exception as e:
        results["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        results["status"] = "unhealthy"

    # Redis
    try:
        redis_status = event_bus.get_connection_status()
        if redis_status.get("connected"):
            results["checks"]["redis"] = {"status": "healthy"}
        else:
            results["checks"]["redis"] = {"status": "unhealthy", "error": redis_status.get("error")}
            results["status"] = "unhealthy"
    except Exception as e:
        results["checks"]["redis"] = {"status": "unhealthy", "error": str(e)}
        results["status"] = "unhealthy"

    # MT5 Bridge
    try:
        mt5 = check_mt5_connection_health()
        if mt5.get("connected"):
            results["checks"]["mt5_bridge"] = {"status": "healthy"}
        else:
            results["checks"]["mt5_bridge"] = {"status": "unhealthy", "error": "Connection failed"}
    except Exception as e:
        results["checks"]["mt5_bridge"] = {"status": "unhealthy", "error": str(e)}

    return results


@router.get("/ready", summary="Readiness probe")
async def readiness(db: Session = Depends(get_db)):
    """Kubernetes-style readiness probe."""
    try:
        db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception as e:
        return {"ready": False, "error": str(e)}
