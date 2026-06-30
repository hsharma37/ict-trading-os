"""Optional API key authentication middleware."""
import os
from fastapi import Request
from fastapi.responses import JSONResponse

API_KEY = os.getenv("API_KEY", "")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}

async def auth_middleware(request: Request, call_next):
    """HTTP middleware that optionally validates X-Api-Key header.
    
    Set AUTH_ENABLED=true and API_KEY=<your-key> to enforce authentication.
    Public paths (/health, /docs, etc.) are always accessible without a key.
    """
    if not AUTH_ENABLED:
        response = await call_next(request)
        return response

    path = request.url.path
    if path in PUBLIC_PATHS:
        response = await call_next(request)
        return response

    api_key = request.headers.get("X-Api-Key", "")
    if not api_key or api_key != API_KEY:
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized. Provide X-Api-Key header."}
        )

    response = await call_next(request)
    return response


def verify_api_key(x_api_key: str = None):
    """Synchronous dependency for explicit route-level auth."""
    if not AUTH_ENABLED:
        return True
    if not x_api_key:
        raise ValueError("X-Api-Key header required")
    if x_api_key != API_KEY:
        raise ValueError("Invalid API key")
    return x_api_key
