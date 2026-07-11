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

async def app(scope, receive, send):
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({
        "type": "http.response.body",
        "body": b'{"message": "Hello from api/index.py"}',
    })
