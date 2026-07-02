"""Production safety API-key authentication middleware."""
import secrets
from typing import Optional

from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import settings

PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PROTECTED_PREFIXES = (
    "/alerts",
    "/bot",
    "/kb/sources",
    "/kb/auto-transcribe",
    "/kb/support",
    "/market/manual-price",
    "/mt5",
    "/orders",
    "/plans",
    "/settings",
    "/telegram",
    "/trades",
)


def validate_auth_config() -> None:
    """Validate auth-related runtime configuration."""
    settings.validate_runtime_security()


def _normalize_path(path: str) -> str:
    if path == "/api":
        return "/"
    if path.startswith("/api/"):
        return path[4:]
    return path


def _path_matches_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def should_require_api_key(method: str, path: str) -> bool:
    """Return whether this request must carry the configured API key."""
    path = _normalize_path(path)
    if method.upper() == "OPTIONS" or path in PUBLIC_PATHS:
        return False
    if not settings.auth_required():
        return False
    if settings.AUTH_ENABLED:
        return True
    if method.upper() in UNSAFE_METHODS:
        return True
    return any(_path_matches_prefix(path, prefix) for prefix in PROTECTED_PREFIXES)


def _api_key_is_valid(api_key: str) -> bool:
    return bool(api_key and settings.API_KEY and secrets.compare_digest(api_key, settings.API_KEY))


async def auth_middleware(request: Request, call_next):
    """Validate X-Api-Key for production-like sensitive or mutating routes."""
    if not should_require_api_key(request.method, request.url.path):
        response = await call_next(request)
        return response

    api_key = request.headers.get("X-Api-Key", "")
    if not _api_key_is_valid(api_key):
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized. Provide X-Api-Key header."},
        )

    response = await call_next(request)
    return response


def verify_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key")):
    """Synchronous dependency for explicit route-level auth."""
    if not settings.auth_required():
        return True
    if not _api_key_is_valid(x_api_key or ""):
        raise HTTPException(status_code=401, detail="Unauthorized. Provide X-Api-Key header.")
    return x_api_key
