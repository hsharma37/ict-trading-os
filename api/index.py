"""Vercel serverless entry point for ICT Trading OS backend."""
import os
import sys

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set defaults before importing app modules so the db singleton picks them up.
# Production and preview values should be configured in Vercel environments.
os.environ.setdefault("DATABASE_PATH", "/tmp/ictos.db")
os.environ.setdefault("PRICE_CACHE_DIR", "/tmp")

from app.main import app as fastapi_app

# The `app` variable is what Vercel's Python runtime looks for
app = fastapi_app
