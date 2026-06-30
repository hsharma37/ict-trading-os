import sqlite3
import json
import os
from typing import Dict, List, Any
from datetime import datetime

DB_PATH = os.getenv("DATABASE_PATH", "ictos.db")

class SQLiteDB:
    """SQLite-backed database that preserves the InMemoryDB interface.
    
    All collections are stored in a single 'docs' table with JSON serialization.
    This provides full persistence across restarts while keeping the API unchanged.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
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

    def get_collection(self, name: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT data FROM docs WHERE collection = ? ORDER BY created_at DESC", (name,))
        rows = [json.loads(r['data']) for r in cursor.fetchall()]
        conn.close()
        return rows

    def insert(self, name: str, doc: Dict) -> Dict:
        doc_id = doc.get("id") or f"{name[:3].upper()}-{int(datetime.utcnow().timestamp()*1000)}"
        doc["id"] = doc_id
        now = datetime.utcnow().isoformat()
        doc["created_at"] = doc.get("created_at") or now
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO docs (collection, id, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (name, doc_id, json.dumps(doc), doc["created_at"], "")
        )
        conn.commit()
        conn.close()
        return doc

    def find(self, name: str, **filters) -> List[Dict]:
        results = self.get_collection(name)
        for key, value in filters.items():
            results = [r for r in results if r.get(key) == value]
        return results

    def find_one(self, name: str, doc_id: str) -> Dict:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT data FROM docs WHERE collection = ? AND id = ?", (name, doc_id))
        row = cursor.fetchone()
        conn.close()
        return json.loads(row['data']) if row else {}

    def update(self, name: str, doc_id: str, updates: Dict) -> Dict:
        existing = self.find_one(name, doc_id)
        if not existing:
            return {}
        existing.update(updates)
        existing["updated_at"] = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE docs SET data = ?, updated_at = ? WHERE collection = ? AND id = ?",
            (json.dumps(existing), existing["updated_at"], name, doc_id)
        )
        conn.commit()
        conn.close()
        return existing

    def delete(self, name: str, doc_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("DELETE FROM docs WHERE collection = ? AND id = ?", (name, doc_id))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def get_stats(self) -> Dict:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT collection, COUNT(*) as count FROM docs GROUP BY collection")
        stats = {r['collection']: r['count'] for r in cursor.fetchall()}
        conn.close()
        return stats

db = SQLiteDB()
