"""Production safety API-key authentication middleware."""
import secrets
from typing import Optional

from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.spa import spa_index_response

# /telegram/poll-source is hit by an external scheduler (Vercel cron or the
# always-on bridge) that can't carry the app's X-Api-Key; it's guarded instead
# by the optional CRON_SECRET bearer checked inside the handler.
PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc",
                "/telegram/poll-source", "/planner/run-due"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PROTECTED_PREFIXES = (
    "/alerts",
    "/bot",
    "/kb/sources",
    "/kb/auto-transcribe",
    "/kb/eval",
    "/kb/ingestion-jobs",
    "/kb/support",
    "/market/manual-price",
    "/mt5",
    "/orders",
    "/plans",
    "/settings",
    "/telegram",
    "/trades",
)

# React Router client-side routes (frontend/src/App.tsx). A few of these
# (/mt5, /settings, /telegram) share a bare-path name with a protected API
# prefix above -- e.g. GET /settings is both "load the Settings page shell"
# and a real protected endpoint returning settings data. Path alone can't
# tell them apart; see _is_spa_navigation for how this is resolved safely.
SPA_ROUTES = {
    "/", "/mt5", "/execute", "/analytics", "/research", "/signals",
    "/telegram", "/knowledge", "/library", "/whatsup", "/settings",
}


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


def _is_spa_navigation(request: Request) -> bool:
    """True when this looks like a browser loading a page, not an API call.

    Some SPA client routes collide by name with a protected API prefix (see
    SPA_ROUTES). A bare GET to one of these paths is ambiguous from the path
    alone: it could mean "render the app shell for this route" or "fetch the
    protected JSON at this exact path". The Accept header reliably tells
    them apart without weakening the actual auth check: real browser
    navigations always prominently request text/html; this app's own API
    client (axios) never does, and an attacker spoofing this header only
    ever gets routed to the static SPA shell in exchange -- never the real
    protected route, since this check short-circuits before FastAPI would
    otherwise dispatch to it.
    """
    if request.method.upper() != "GET":
        return False
    if _normalize_path(request.url.path) not in SPA_ROUTES:
        return False
    return "text/html" in request.headers.get("accept", "")


async def auth_middleware(request: Request, call_next):
    """Validate X-Api-Key for production-like sensitive or mutating routes."""
    if _is_spa_navigation(request):
        return spa_index_response() or JSONResponse(
            status_code=404, content={"error": "index.html not found"}
        )

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
