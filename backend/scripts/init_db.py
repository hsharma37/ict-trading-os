"""
Initialize the database with seed data.

Creates a default user for single-user mode.
Run with: python -m scripts.init_db
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from uuid import uuid4
from sqlmodel import Session

from app.database import engine, init_db
from app.models.user import User


def seed_user(email: str = 