"""Vercel serverless entry point for ICT Trading OS backend."""
import os
import sys

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force in-memory DB for Vercel serverless (no persistent filesystem)
os.environ.setdefault("DATABASE_PATH", ":memory:")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.main import app as fastapi_app

# The `app` variable is what Vercel's Python runtime looks for
app = fastapi_app

# Add CORS for the deployed frontend
origins = [
    "https://frontend-oe0raobgg-hsharma37s-projects.vercel.app",
    "https://frontend-two-indol-86.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
    "*",
]

# Remove any existing CORS middleware and add our own
# (FastAPI app may already have CORS from app/main.py)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
