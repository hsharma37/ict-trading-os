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

from app.main import app as fastapi_app

# The `app` variable is what Vercel's Python runtime looks for.
app = fastapi_app
