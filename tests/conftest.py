import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_db_file = tempfile.NamedTemporaryFile(prefix="tradingos-test-", suffix=".db", delete=False)
_db_file.close()
_cache_dir = tempfile.TemporaryDirectory(prefix="tradingos-test-cache-")

os.environ["DATABASE_PATH"] = _db_file.name
os.environ["PRICE_CACHE_DIR"] = _cache_dir.name
os.environ.setdefault("AUTH_ENABLED", "false")

from app.core.database import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    collections = [
        "test_settings",
        "test_signals",
        "settings",
        "kb_sources",
        "kb_chunks",
        "kb_ingestion_jobs",
        "plans",
        "trades",
        "journal_entries",
        "risk_settings",
        "audit_logs",
        "market_snapshots",
    ]
    for collection in collections:
        for doc in db.find(collection):
            db.delete(collection, doc["id"])
    yield
    for collection in collections:
        for doc in db.find(collection):
            db.delete(collection, doc["id"])


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db_file():
    yield
    try:
        os.remove(_db_file.name)
    except FileNotFoundError:
        pass
    _cache_dir.cleanup()
