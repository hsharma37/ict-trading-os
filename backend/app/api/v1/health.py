from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings

router = APIRouter()


@router.get("/", summary="Health check")
async def health_check():
    return JSONResponse(
        content={
            "status": "ok",
            "version": "1.0.0",
            "environment": settings.log_level,
        }
    )
