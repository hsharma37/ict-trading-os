"""Vercel serverless entry point for ICT Trading OS backend."""
import os
import sys

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set runtime defaults before importing app modules so the db singleton picks
# them up. Durable trading/KB state must come from DATABASE_URL on Vercel.
os.environ.setdefault("TRADINGOS_RUNTIME", "vercel")
os.environ.setdefault("APP_ENV", os.getenv("VERCEL_ENV", "production"))
os.environ.setdefault("PRICE_CACHE_DIR", "/tmp")

# Debug: print env vars at import time (visible in Vercel function logs)
print(f"[ICTOS DEBUG] TRADINGOS_RUNTIME={os.getenv('TRADINGOS_RUNTIME')}")
print(f"[ICTOS DEBUG] APP_ENV={os.getenv('APP_ENV')}")
print(f"[ICTOS DEBUG] DATABASE_URL set={bool(os.getenv('DATABASE_URL'))}")
print(f"[ICTOS DEBUG] API_KEY set={bool(os.getenv('API_KEY'))}")
print(f"[ICTOS DEBUG] JWT_SECRET set={bool(os.getenv('JWT_SECRET'))}")

from app.main import app as fastapi_app

class ApiPrefixStripper:
    """Let Vercel expose the FastAPI app under /api without changing routes.

    Vercel rewrites change the destination path (e.g. /api/health -> /api/index).
    We use raw_path (original path before rewrites) to strip the /api prefix so
    FastAPI routes match correctly.
    """

    def __init__(self, wrapped_app):
        self.wrapped_app = wrapped_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            # raw_path is the original path before Vercel rewrites; path is the
            # rewritten destination.  Prefer raw_path so our routes match.
            raw_path = scope.get("raw_path")
            if raw_path:
                try:
                    effective = raw_path.decode("utf-8")
                except Exception:
                    effective = str(raw_path)
            else:
                effective = scope.get("path", "")

            if effective == "/api":
                scope["path"] = "/"
            elif effective.startswith("/api/"):
                scope["path"] = effective[4:]
        await self.wrapped_app(scope, receive, send)


# The `app` variable is what Vercel's Python runtime looks for.
app = ApiPrefixStripper(fastapi_app)
