"""Vercel Serverless Entry Point for ICT Trading OS API."""
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

# Vercel expects 'app' variable at module level
# FastAPI app is exported from app.main
