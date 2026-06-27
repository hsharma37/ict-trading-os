"""
Knowledge Base Service — RAG pipeline, document ingestion, and semantic search.

Uses Haystack for document processing and pgvector for embedding storage.
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from sqlmodel import Session, select
from sqlalchemy import func

from app.database import get_db
from app.models.kb import KBSource, KBChunk
from app.config import settings

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """
    Service for managing the ICT knowledge base.
    Handles document ingestion, chunking, embedding, and retrieval.
    """

    def __init__(self, db: Session):
        self.db = db

    # ────────────────────────────────────────────────
    # Source Management
    # ────────────────────────────────────────────────

    def create_source(
        self,
        user_id: UUID,
        source_type: str,
        title: str,
        url: Optional[str] = None,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KBSource:
        """Create a new knowledge base source."""
        source = KBSource(
            id=uuid4(),
            user_id=user_id,
            source_type=source_type,
            title=title,
            url=url,
            content=content,
            metadata=metadata or {},
            chunk_count=0,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        logger.info(f"Created KB source: {title} ({source_type})")
        return source

    def get_source(self, source_id: UUID) -> Optional[KBSource]:
        """Get a source by ID."""
        return self.db.get(KBSource, source_id)

    def list_sources(self, user_id: UUID, source_type: Optional[str] = None) -> List[KBSource]:
        """List all sources for a user, optionally filtered by type."""
        statement = select(KBSource).where(KBSource.user_id == user_id)
        if source_type:
            statement = statement.where(KBSource.source_type == source_type)
        statement = statement.order_by(KBSource.created_at.desc())
        return self.db.exec(statement).all()

    def delete_source(self, source_id: UUID) -> bool:
        """Delete a source and all its chunks."""
        source = self.db.get(KBSource, source_id)
        if not source:
            return False
        self.db.delete(source)
        self.db.commit()
        logger.info(f"Deleted KB source: {source_id}")
        return True

    # ────────────────────────────────────────────────
    # Chunk Management
    # ────────────────────────────────────────────────

    def create_chunks(self, source_id: UUID, chunks: List[Dict[str, Any]]) -> List[KBChunk]:
        """
        Create chunks for a source with embeddings.

        chunks: List of {"chunk_index": int, "content": str, "embedding": List[float], "metadata": dict}
        """
        db_chunks = []
        for chunk_data in chunks:
            chunk = KBChunk(
                id=uuid4(),
                source_id=source_id,
                chunk_index=chunk_data["chunk_index"],
                content=chunk_data["content"],
                embedding=chunk_data.get("embedding"),
                metadata=chunk_data.get("metadata", {}),
            )
            self.db.add(chunk)
            db_chunks.append(chunk)

        # Update source chunk count
        source = self.db.get(KBSource, source_id)
        if source:
            source.chunk_count = len(chunks)

        self.db.commit()
        for chunk in db_chunks:
            self.db.refresh(chunk)

        logger.info(f"Created {len(chunks)} chunks for source {source_id}")
        return db_chunks

    def search_chunks(
        self,
        user_id: UUID,
        query_embedding: List[float],
        top_k: int = 5,
        source_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over chunks using cosine similarity via pgvector.
        """
        # Build the query using pgvector's <=> operator (cosine distance)
        # Lower distance = higher similarity
        from sqlalchemy import text

        # Filter by user through source join
        sql = """
        SELECT
            c.id,
            c.chunk_index,
            c.content,
            c.metadata,
            c.source_id,
            s.title,
            s.source_type,
            1 - (c.embedding <=> :embedding) as similarity
        FROM kb_chunks c
        JOIN kb_sources s ON c.source_id = s.id
        WHERE s.user_id = :user_id
        """

        params = {
            "embedding": str(query_embedding),  # pgvector accepts array literal
            "user_id": str(user_id),
        }

        if source_type:
            sql += " AND s.source_type = :source_type"
            params["source_type"] = source_type

        sql += """
        ORDER BY c.embedding <=> :embedding
        LIMIT :top_k
        """
        params["top_k"] = top_k

        # Execute raw query
        result = self.db.exec(text(sql), params=params)
        rows = result.fetchall()

        results = []
        for row in rows:
            results.append({
                "chunk_id": row.id,
                "chunk_index": row.chunk_index,
                "content": row.content,
                "metadata": row.metadata,
                "source_id": row.source_id,
                "source_title": row.title,
                "source_type": row.source_type,
                "similarity": float(row.similarity) if row.similarity else 0.0,
            })

        return results

    def get_chunks_by_source(self, source_id: UUID) -> List[KBChunk]:
        """Get all chunks for a source."""
        statement = select(KBChunk).where(KBChunk.source_id == source_id).order_by(KBChunk.chunk_index)
        return self.db.exec(statement).all()

    # ────────────────────────────────────────────────
    # Full Text Search (fallback)
    # ────────────────────────────────────────────────

    def search_text(
        self,
        user_id: UUID,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Full-text search over chunk content using PostgreSQL tsvector.
        """
        from sqlalchemy import text

        sql = """
        SELECT
            c.id,
            c.chunk_index,
            c.content,
            c.metadata,
            c.source_id,
            s.title,
            s.source_type,
            ts_rank(to_tsvector('english', c.content), plainto_tsquery('english', :query)) as rank
        FROM kb_chunks c
        JOIN kb_sources s ON c.source_id = s.id
        WHERE s.user_id = :user_id
        AND to_tsvector('english', c.content) @@ plainto_tsquery('english', :query)
        ORDER BY rank DESC
        LIMIT :top_k
        """

        result = self.db.exec(
            text(sql),
            params={
                "query": query,
                "user_id": str(user_id),
                "top_k": top_k,
            }
        )
        rows = result.fetchall()

        results = []
        for row in rows:
            results.append({
                "chunk_id": row.id,
                "chunk_index": row.chunk_index,
                "content": row.content,
                "metadata": row.metadata,
                "source_id": row.source_id,
                "source_title": row.title,
                "source_type": row.source_type,
                "rank": float(row.rank) if row.rank else 0.0,
            })

        return results
