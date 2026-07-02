from pathlib import Path

from app.core.database import (
    PGVECTOR_DIMENSIONS,
    POSTGRES_COLLECTION_TABLES,
    _vector_literal,
    db,
    runtime_requires_postgres,
)
from app.services.plan_service import plan_service

def test_db_insert_and_find():
    db.insert('test_signals', {'id': 'sig1', 'symbol': 'EURUSD', 'score': 3})
    docs = db.find('test_signals', symbol='EURUSD')
    assert len(docs) >= 1
    assert any(d['symbol'] == 'EURUSD' for d in docs)

def test_db_find_one():
    db.insert('test_settings', {'id': 'global', 'theme': 'dark'})
    doc = db.find_one('test_settings', 'global')
    assert doc is not None
    assert doc['theme'] == 'dark'

def test_db_update():
    db.insert('test_settings', {'id': 'global', 'theme': 'dark'})
    db.update('test_settings', 'global', {'theme': 'light'})
    doc = db.find_one('test_settings', 'global')
    assert doc['theme'] == 'light'
    assert doc["version"] == 2


def test_db_update_if_version_rejects_stale_writes():
    db.insert('test_settings', {'id': 'versioned', 'theme': 'dark'})
    updated = db.update_if_version('test_settings', 'versioned', 1, {'theme': 'light'})
    assert updated["theme"] == "light"
    assert updated["version"] == 2

    stale = db.update_if_version('test_settings', 'versioned', 1, {'theme': 'stale'})
    assert stale == {}
    doc = db.find_one('test_settings', 'versioned')
    assert doc["theme"] == "light"
    assert doc["version"] == 2

def test_db_stats():
    stats = db.get_stats()
    assert isinstance(stats, dict)


def test_active_db_uses_sqlite_only_as_test_fallback():
    info = db.storage_info()
    assert info["backend"] == "sqlite"
    assert info["pgvector"] is False


def test_runtime_requires_postgres_for_production_preview_and_vercel():
    assert runtime_requires_postgres("production") is True
    assert runtime_requires_postgres("preview") is True
    assert runtime_requires_postgres("development", is_vercel=True) is True
    assert runtime_requires_postgres("development") is False
    assert runtime_requires_postgres("production", allow_sqlite_runtime=True) is False


def test_postgres_collection_map_covers_core_product_state():
    assert {
        "kb_sources",
        "kb_chunks",
        "plans",
        "trades",
        "journal_entries",
        "market_snapshots",
        "risk_settings",
        "audit_logs",
        "settings",
    }.issubset(POSTGRES_COLLECTION_TABLES)


def test_pgvector_literal_uses_expected_embedding_dimension():
    vector = [0.1] * PGVECTOR_DIMENSIONS
    literal = _vector_literal(vector)
    assert literal.startswith("[0.1,0.1")
    assert literal.endswith("]")
    assert literal.count(",") == PGVECTOR_DIMENSIONS - 1


def test_migration_defines_pgvector_and_durable_tables():
    sql = Path("migrations/001_postgres_pgvector_foundation.sql").read_text()
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    for table in [
        "kb_sources",
        "kb_chunks",
        "trade_plans",
        "trades",
        "journal_entries",
        "market_snapshots",
        "risk_settings",
        "audit_logs",
        "workspace_settings",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert "embedding vector(384)" in sql


def test_trade_plan_persists_through_active_store():
    plan = plan_service.create_plan({
        "symbol": "EURUSD",
        "bias": "BEARISH",
        "entry_zone": 1.08,
        "stop_loss": 1.085,
        "take_profit_1": 1.07,
        "strategy": "ICT",
        "narrative": "Liquidity sweep into FVG, wait for confirmation.",
        "tags": ["liquidity", "fvg"],
        "session": "NY AM",
    })

    stored = db.find_one("plans", plan["id"])
    assert stored["symbol"] == "EURUSD"
    assert stored["bias"] == "BEARISH"
    assert stored["narrative"].startswith("Liquidity sweep")
