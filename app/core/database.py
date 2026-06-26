"""Database layer - In-memory for Vercel free tier, Supabase optional."""
from typing import Dict, List, Any
from datetime import datetime
import os

# In-memory storage (resets on cold start - fine for demo/signals)
_memory_store = {
    "trades": [],
    "plans": [],
    "journal": [],
    "signals": [],
    "kb_sources": [],
    "users": []
}

class InMemoryDB:
    """Simple in-memory database for Vercel serverless."""

    @staticmethod
    def get_collection(name: str) -> List[Dict]:
        return _memory_store.setdefault(name, [])

    @staticmethod
    def insert(name: str, doc: Dict) -> Dict:
        doc["id"] = doc.get("id", f"{name[:3].upper()}-{int(datetime.utcnow().timestamp()*1000)}")
        doc["created_at"] = datetime.utcnow().isoformat()
        _memory_store[name].append(doc)
        return doc

    @staticmethod
    def find(name: str, **filters) -> List[Dict]:
        results = _memory_store.get(name, [])
        for key, value in filters.items():
            results = [r for r in results if r.get(key) == value]
        return results

    @staticmethod
    def find_one(name: str, doc_id: str) -> Dict:
        for doc in _memory_store.get(name, []):
            if doc.get("id") == doc_id:
                return doc
        return {}

    @staticmethod
    def update(name: str, doc_id: str, updates: Dict) -> Dict:
        for doc in _memory_store.get(name, []):
            if doc.get("id") == doc_id:
                doc.update(updates)
                doc["updated_at"] = datetime.utcnow().isoformat()
                return doc
        return {}


db = InMemoryDB()
