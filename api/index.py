"""Vercel serverless entry point for ICT Trading OS backend."""
import os
import sys
import urllib.parse

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
    We pass the original path via __original_path query parameter so we can
    restore the correct path for FastAPI routing.
    """

    def __init__(self, wrapped_app):
        self.wrapped_app = wrapped_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            query_string = scope.get("query_string", b"").decode()
            params = urllib.parse.parse_qs(query_string)

            if "__original_path" in params:
                original_path = params["__original_path"][-1]
                if original_path == "/api":
                    scope["path"] = "/"
                elif original_path.startswith("/api/"):
                    scope["path"] = original_path[4:]
                else:
                    scope["path"] = original_path
            elif scope.get("path", "").startswith("/api/"):
                # Fallback: strip /api prefix
                scope["path"] = scope["path"][4:]
        await self.wrapped_app(scope, receive, send)


# The `app` variable is what Vercel's Python runtime looks for.
app = ApiPrefixStripper(fastapi_app)
