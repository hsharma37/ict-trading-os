"""Durable document storage for the active TradingOS API.

The application still uses a small document-store interface across services. This
module keeps that API stable while adding a production Postgres backend with
pgvector support for KB chunks.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings


POSTGRES_COLLECTION_TABLES = {
    "kb_sources": "kb_sources",
    "kb_chunks": "kb_chunks",
    "plans": "trade_plans",
    "trades": "trades",
    "journal_entries": "journal_entries",
    "market_snapshots": "market_snapshots",
    "risk_settings": "risk_settings",
    "audit_logs": "audit_logs",
    "settings": "workspace_settings",
}

PGVECTOR_DIMENSIONS = 384
SCHEMA_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_doc_id(collection: str) -> str:
    return f"{collection[:3].upper()}-{int(datetime.now(timezone.utc).timestamp() * 1000)}-{uuid.uuid4().hex[:6]}"


def runtime_requires_postgres(
    app_env: str,
    *,
    is_vercel: bool = False,
    allow_sqlite_runtime: bool = False,
    require_postgres: bool = False,
) -> bool:
    """Return whether this runtime must refuse SQLite fallback."""
    if allow_sqlite_runtime:
        return False
    return require_postgres or app_env in {"production", "preview"} or is_vercel


def _vector_literal(values: List[float]) -> str:
    """Format a pgvector literal from a Python list."""
    return "[" + ",".join(str(float(value)) for value in values) + "]"


class SQLiteDB:
    """SQLite-backed document store for local development and tests.

    SQLite is intentionally treated as a dev-only fallback. Production and
    Vercel runtimes require Postgres unless ALLOW_SQLITE_RUNTIME=true is set.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS docs (
                collection TEXT NOT NULL,
                id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                PRIMARY KEY (collection, id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_collection ON docs(collection)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_created ON docs(created_at)")
        conn.commit()
        conn.close()

    def get_collection(self, name: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT data FROM docs WHERE collection = ? ORDER BY created_at DESC", (name,))
        rows = [json.loads(r["data"]) for r in cursor.fetchall()]
        conn.close()
        return rows

    def insert(self, name: str, doc: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = doc.get("id") or _new_doc_id(name)
        doc["id"] = doc_id
        now = _utc_now()
        doc["created_at"] = doc.get("created_at") or now
        doc["version"] = int(doc.get("version") or 1)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO docs (collection, id, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (name, doc_id, json.dumps(doc), doc["created_at"], doc.get("updated_at", "")),
        )
        conn.commit()
        conn.close()
        return doc

    def find(self, name: str, **filters: Any) -> List[Dict[str, Any]]:
        results = self.get_collection(name)
        for key, value in filters.items():
            results = [r for r in results if r.get(key) == value]
        return results

    def find_one(self, name: str, doc_id: str) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT data FROM docs WHERE collection = ? AND id = ?", (name, doc_id))
        row = cursor.fetchone()
        conn.close()
        return json.loads(row["data"]) if row else {}

    def update(self, name: str, doc_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.find_one(name, doc_id)
        if not existing:
            return {}
        existing.update(updates)
        existing["updated_at"] = _utc_now()
        existing["version"] = int(existing.get("version") or 1) + 1
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE docs SET data = ?, updated_at = ? WHERE collection = ? AND id = ?",
            (json.dumps(existing), existing["updated_at"], name, doc_id),
        )
        conn.commit()
        conn.close()
        return existing

    def update_if_version(self, name: str, doc_id: str, expected_version: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT data FROM docs WHERE collection = ? AND id = ?", (name, doc_id)).fetchone()
            if not row:
                conn.rollback()
                return {}
            existing = json.loads(row["data"])
            current_version = int(existing.get("version") or 1)
            if current_version != int(expected_version):
                conn.rollback()
                return {}
            existing.update(updates)
            existing["updated_at"] = _utc_now()
            existing["version"] = current_version + 1
            conn.execute(
                "UPDATE docs SET data = ?, updated_at = ? WHERE collection = ? AND id = ?",
                (json.dumps(existing), existing["updated_at"], name, doc_id),
            )
            conn.commit()
            return existing
        finally:
            conn.close()

    def delete(self, name: str, doc_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("DELETE FROM docs WHERE collection = ? AND id = ?", (name, doc_id))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def get_stats(self) -> Dict[str, int]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT collection, COUNT(*) as count FROM docs GROUP BY collection")
        stats = {r["collection"]: r["count"] for r in cursor.fetchall()}
        conn.close()
        return stats

    def storage_info(self) -> Dict[str, Any]:
        return {
            "backend": "sqlite",
            "path": self.db_path,
            "durable": not os.path.abspath(self.db_path).startswith("/tmp/"),
            "pgvector": False,
        }

    def search_kb_chunks_by_embedding(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        return []


class PostgresDB:
    """Postgres-backed document store with domain tables and pgvector search."""

    def __init__(self, database_url: str):
        if not database_url:
            raise RuntimeError("DATABASE_URL is required for Postgres storage")
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
        except ImportError as exc:
            raise RuntimeError(
                "DATABASE_URL is set, but psycopg is not installed. Run `pip install -r requirements.txt`."
            ) from exc

        self.database_url = database_url
        self._psycopg = psycopg
        self._dict_row = dict_row
        self._jsonb = Jsonb
        self.pgvector_enabled = False
        self._init_db()

    def _connect(self):
        conn = self._psycopg.connect(
            self.database_url,
            autocommit=True,
            row_factory=self._dict_row,
        )
        if settings.DATABASE_SCHEMA:
            if not SCHEMA_NAME_RE.match(settings.DATABASE_SCHEMA):
                raise RuntimeError("DATABASE_SCHEMA must be a simple Postgres identifier")
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {settings.DATABASE_SCHEMA}, extensions, public")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                    cur.execute("SELECT to_regtype('vector') IS NOT NULL AS available")
                    self.pgvector_enabled = bool(cur.fetchone()["available"])
                except Exception:
                    self.pgvector_enabled = False
                self._create_tables(cur)
                if self.pgvector_enabled:
                    try:
                        cur.execute(
                            f"ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS embedding vector({PGVECTOR_DIMENSIONS})"
                        )
                        cur.execute(
                            "CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding "
                            "ON kb_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
                        )
                    except Exception:
                        self.pgvector_enabled = False

    def _create_tables(self, cur) -> None:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_documents (
                collection TEXT NOT NULL,
                id TEXT NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ,
                PRIMARY KEY (collection, id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_app_documents_collection ON app_documents(collection)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_app_documents_data_gin ON app_documents USING gin(data)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS kb_sources (
                id TEXT PRIMARY KEY,
                title TEXT,
                url TEXT,
                source_type TEXT,
                tags TEXT[] NOT NULL DEFAULT '{}',
                concepts TEXT[] NOT NULL DEFAULT '{}',
                confidence_score NUMERIC,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_sources_url ON kb_sources(url) WHERE url IS NOT NULL AND url <> ''")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kb_sources_data_gin ON kb_sources USING gin(data)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS kb_chunks (
                id TEXT PRIMARY KEY,
                source_id TEXT REFERENCES kb_sources(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL DEFAULT 0,
                chunk_text TEXT NOT NULL DEFAULT '',
                tokens TEXT[] NOT NULL DEFAULT '{}',
                lexical_vector JSONB NOT NULL DEFAULT '{}',
                embedding_json JSONB NOT NULL DEFAULT '[]',
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kb_chunks_source_id ON kb_chunks(source_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_kb_chunks_data_gin ON kb_chunks USING gin(data)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS trade_plans (
                id TEXT PRIMARY KEY,
                symbol TEXT,
                bias TEXT,
                status TEXT,
                strategy TEXT,
                session_name TEXT,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trade_plans_symbol_status ON trade_plans(symbol, status)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                symbol TEXT,
                side TEXT,
                status TEXT,
                plan_id TEXT,
                risk_pct NUMERIC,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol_status ON trades(symbol, status)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS journal_entries (
                id TEXT PRIMARY KEY,
                trade_id TEXT,
                plan_id TEXT,
                symbol TEXT,
                session_name TEXT,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_journal_entries_symbol ON journal_entries(symbol)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id TEXT PRIMARY KEY,
                symbol TEXT,
                timeframe TEXT,
                session_name TEXT,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_market_snapshots_symbol_created ON market_snapshots(symbol, created_at DESC)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS risk_settings (
                id TEXT PRIMARY KEY,
                mode TEXT,
                kill_switch BOOLEAN NOT NULL DEFAULT FALSE,
                max_daily_loss NUMERIC,
                max_position_size NUMERIC,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                actor_id TEXT,
                action TEXT,
                entity_type TEXT,
                entity_id TEXT,
                risk_decision TEXT,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspace_settings (
                id TEXT PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
        """)

    def _table_for(self, collection: str) -> Optional[str]:
        return POSTGRES_COLLECTION_TABLES.get(collection)

    def _domain_values(self, collection: str, doc: Dict[str, Any]) -> Dict[str, Any]:
        if collection == "kb_sources":
            return {
                "title": doc.get("title"),
                "url": doc.get("url"),
                "source_type": doc.get("source_type"),
                "tags": doc.get("tags") or [],
                "concepts": doc.get("concepts") or [],
                "confidence_score": doc.get("confidence_score"),
                "chunk_count": doc.get("chunk_count") or 0,
            }
        if collection == "kb_chunks":
            embedding = doc.get("embedding") or []
            values = {
                "source_id": doc.get("source_id"),
                "chunk_index": doc.get("chunk_index") or 0,
                "chunk_text": doc.get("chunk_text") or "",
                "tokens": doc.get("tokens") or [],
                "lexical_vector": self._jsonb(doc.get("vector") or {}),
                "embedding_json": self._jsonb(embedding),
            }
            if self.pgvector_enabled:
                values["embedding"] = _vector_literal(embedding) if len(embedding) == PGVECTOR_DIMENSIONS else None
            return values
        if collection == "plans":
            return {
                "symbol": doc.get("symbol"),
                "bias": doc.get("bias"),
                "status": doc.get("status"),
                "strategy": doc.get("strategy"),
                "session_name": doc.get("session"),
            }
        if collection == "trades":
            return {
                "symbol": doc.get("symbol"),
                "side": doc.get("side"),
                "status": doc.get("status"),
                "plan_id": doc.get("plan_id"),
                "risk_pct": doc.get("risk_pct"),
            }
        if collection == "journal_entries":
            return {
                "trade_id": doc.get("trade_id"),
                "plan_id": doc.get("plan_id"),
                "symbol": doc.get("symbol"),
                "session_name": doc.get("session"),
            }
        if collection == "market_snapshots":
            return {
                "symbol": doc.get("symbol"),
                "timeframe": doc.get("timeframe"),
                "session_name": doc.get("session"),
            }
        if collection == "risk_settings":
            return {
                "mode": doc.get("mode"),
                "kill_switch": bool(doc.get("kill_switch", False)),
                "max_daily_loss": doc.get("max_daily_loss"),
                "max_position_size": doc.get("max_position_size"),
            }
        if collection == "audit_logs":
            return {
                "actor_id": doc.get("actor_id"),
                "action": doc.get("action"),
                "entity_type": doc.get("entity_type"),
                "entity_id": doc.get("entity_id"),
                "risk_decision": doc.get("risk_decision"),
            }
        return {}

    def _write_domain(self, collection: str, doc: Dict[str, Any], *, update: bool = False) -> Dict[str, Any]:
        table = self._table_for(collection)
        if not table:
            raise ValueError(f"Collection {collection} is not mapped to a domain table")

        doc_id = doc["id"]
        values = {
            "id": doc_id,
            "data": self._jsonb(doc),
            "created_at": doc.get("created_at") or _utc_now(),
            "updated_at": doc.get("updated_at"),
            **self._domain_values(collection, doc),
        }

        if update:
            set_columns = [key for key in values if key != "id"]
            assignments = ", ".join(f"{key} = %s" for key in set_columns)
            params = [values[key] for key in set_columns] + [doc_id]
            sql = f"UPDATE {table} SET {assignments} WHERE id = %s"
        else:
            columns = list(values.keys())
            placeholders = ", ".join(["%s"] * len(columns))
            sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
            params = [values[key] for key in columns]

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
        return doc

    def get_collection(self, name: str) -> List[Dict[str, Any]]:
        table = self._table_for(name)
        with self._connect() as conn:
            with conn.cursor() as cur:
                if table:
                    cur.execute(f"SELECT data FROM {table} ORDER BY created_at DESC")
                else:
                    cur.execute(
                        "SELECT data FROM app_documents WHERE collection = %s ORDER BY created_at DESC",
                        (name,),
                    )
                return [row["data"] for row in cur.fetchall()]

    def insert(self, name: str, doc: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = doc.get("id") or _new_doc_id(name)
        doc["id"] = doc_id
        doc["created_at"] = doc.get("created_at") or _utc_now()
        doc["version"] = int(doc.get("version") or 1)
        table = self._table_for(name)
        if table:
            return self._write_domain(name, doc)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO app_documents (collection, id, data, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (name, doc_id, self._jsonb(doc), doc["created_at"], doc.get("updated_at")),
                )
        return doc

    def find(self, name: str, **filters: Any) -> List[Dict[str, Any]]:
        results = self.get_collection(name)
        for key, value in filters.items():
            results = [r for r in results if r.get(key) == value]
        return results

    def find_one(self, name: str, doc_id: str) -> Dict[str, Any]:
        table = self._table_for(name)
        with self._connect() as conn:
            with conn.cursor() as cur:
                if table:
                    cur.execute(f"SELECT data FROM {table} WHERE id = %s", (doc_id,))
                else:
                    cur.execute(
                        "SELECT data FROM app_documents WHERE collection = %s AND id = %s",
                        (name, doc_id),
                    )
                row = cur.fetchone()
                return row["data"] if row else {}

    def update(self, name: str, doc_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.find_one(name, doc_id)
        if not existing:
            return {}
        existing.update(updates)
        existing["updated_at"] = _utc_now()
        existing["version"] = int(existing.get("version") or 1) + 1

        table = self._table_for(name)
        if table:
            return self._write_domain(name, existing, update=True)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE app_documents SET data = %s, updated_at = %s WHERE collection = %s AND id = %s",
                    (self._jsonb(existing), existing["updated_at"], name, doc_id),
                )
        return existing

    def update_if_version(self, name: str, doc_id: str, expected_version: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.find_one(name, doc_id)
        if not existing:
            return {}
        current_version = int(existing.get("version") or 1)
        if current_version != int(expected_version):
            return {}
        existing.update(updates)
        existing["updated_at"] = _utc_now()
        existing["version"] = current_version + 1

        table = self._table_for(name)
        if table:
            values = {
                "data": self._jsonb(existing),
                "updated_at": existing["updated_at"],
                **self._domain_values(name, existing),
            }
            set_columns = list(values.keys())
            assignments = ", ".join(f"{key} = %s" for key in set_columns)
            params = [values[key] for key in set_columns] + [doc_id, expected_version]
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE {table} SET {assignments} "
                        "WHERE id = %s AND COALESCE((data->>'version')::int, 1) = %s",
                        params,
                    )
                    if cur.rowcount == 0:
                        return {}
            return existing

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE app_documents SET data = %s, updated_at = %s "
                    "WHERE collection = %s AND id = %s AND COALESCE((data->>'version')::int, 1) = %s",
                    (self._jsonb(existing), existing["updated_at"], name, doc_id, expected_version),
                )
                if cur.rowcount == 0:
                    return {}
        return existing

    def delete(self, name: str, doc_id: str) -> bool:
        table = self._table_for(name)
        with self._connect() as conn:
            with conn.cursor() as cur:
                if table:
                    cur.execute(f"DELETE FROM {table} WHERE id = %s", (doc_id,))
                else:
                    cur.execute(
                        "DELETE FROM app_documents WHERE collection = %s AND id = %s",
                        (name, doc_id),
                    )
                return cur.rowcount > 0

    def get_stats(self) -> Dict[str, int]:
        stats: Dict[str, int] = {}
        with self._connect() as conn:
            with conn.cursor() as cur:
                for collection, table in POSTGRES_COLLECTION_TABLES.items():
                    cur.execute(f"SELECT COUNT(*) AS count FROM {table}")
                    count = int(cur.fetchone()["count"])
                    if count:
                        stats[collection] = count
                cur.execute("SELECT collection, COUNT(*) AS count FROM app_documents GROUP BY collection")
                for row in cur.fetchall():
                    stats[row["collection"]] = int(row["count"])
        return stats

    def storage_info(self) -> Dict[str, Any]:
        return {
            "backend": "postgres",
            "durable": True,
            "pgvector": self.pgvector_enabled,
            "mapped_collections": sorted(POSTGRES_COLLECTION_TABLES.keys()),
        }

    def search_kb_chunks_by_embedding(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.pgvector_enabled or len(query_embedding) != PGVECTOR_DIMENSIONS:
            return []
        vector = _vector_literal(query_embedding)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT data, 1 - (embedding <=> %s::vector) AS score "
                    "FROM kb_chunks "
                    "WHERE embedding IS NOT NULL "
                    "ORDER BY embedding <=> %s::vector "
                    "LIMIT %s",
                    (vector, vector, top_k),
                )
                return [{"chunk": row["data"], "score": float(row["score"])} for row in cur.fetchall()]


def create_db():
    if settings.STORAGE_BACKEND in {"postgres", "postgresql"} or (
        settings.STORAGE_BACKEND == "auto" and settings.DATABASE_URL
    ):
        return PostgresDB(settings.DATABASE_URL)

    if runtime_requires_postgres(
        settings.APP_ENV,
        is_vercel=settings.IS_VERCEL,
        allow_sqlite_runtime=settings.ALLOW_SQLITE_RUNTIME,
        require_postgres=settings.REQUIRE_POSTGRES,
    ):
        raise RuntimeError(
            "Postgres DATABASE_URL is required for production, preview, and Vercel runtimes. "
            "Refusing to store KB/trading state in SQLite or /tmp."
        )

    return SQLiteDB(settings.DATABASE_PATH)


class LazyDB:
    """Lazy proxy that delays DB creation until first use, avoiding import-time
    failures on Vercel where env vars may not be available at module load.
    """
    def __init__(self):
        self._db = None

    def _get_db(self):
        if self._db is None:
            self._db = create_db()
        return self._db

    def __getattr__(self, name):
        return getattr(self._get_db(), name)

    def __setattr__(self, name, value):
        if name == "_db":
            super().__setattr__(name, value)
        else:
            setattr(self._get_db(), name, value)

    def __getitem__(self, key):
        return self._get_db()[key]

    def __setitem__(self, key, value):
        self._get_db()[key] = value

    def __contains__(self, key):
        return key in self._get_db()

    def __iter__(self):
        return iter(self._get_db())

    def __len__(self):
        return len(self._get_db())

    def __repr__(self):
        if self._db is None:
            return "LazyDB(not initialized)"
        return repr(self._db)


db = LazyDB()
