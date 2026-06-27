"""
Background tasks for the ICT Trading OS.

Currently stubs. Will be populated with:
- Transcript ingestion
- Embedding generation
- Alert scanning
- Market data backfills
"""
from app.jobs import celery_app
import logging
from uuid import uuid4, UUID
import asyncio

from app.services.knowledge_service import KnowledgeBaseService
from app.services.ai_service import AIService
from app.services.document_processor import chunk_text_semantic, format_transcript_for_kb

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def ingest_knowledge_base_task(self, user_id: str, source_type: str, title: str, content: str = None, url: str = None, metadata: dict = None):
    """
    Celery task to ingest content into the knowledge base.
    Chunks, embeds, and stores in the background.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        logger.info(f"Starting KB ingestion task for: {title}")

        kb = KnowledgeBaseService(db)
        ai = AIService()

        # Create source
        source = kb.create_source(
            user_id=UUID(user_id),
            source_type=source_type,
            title=title,
            url=url,
            content=content,
            metadata=metadata or {},
        )

        if not content:
            return {
                "source_id": str(source.id),
                "status": "created_without_content",
                "chunks": 0,
            }

        # Format and chunk content
        formatted = format_transcript_for_kb(content, title)
        chunks = chunk_text_semantic(formatted, max_chunk_size=512, chunk_overlap=50)

        # Generate embeddings and store chunks
        chunk_data = []
        for chunk in chunks:
            try:
                # Run async embed in sync context
                embedding = asyncio.get_event_loop().run_until_complete(
                    ai.embed(chunk["content"])
                )
                chunk_data.append({
                    "chunk_index": chunk["chunk_index"],
                    "content": chunk["content"],
                    "embedding": embedding,
                    "metadata": {
                        "word_count": chunk["word_count"],
                        "char_count": chunk["char_count"],
                    },
                })
            except Exception as e:
                logger.error(f"Embedding failed for chunk {chunk['chunk_index']}: {e}")
                chunk_data.append({
                    "chunk_index": chunk["chunk_index"],
                    "content": chunk["content"],
                    "embedding": None,
                    "metadata": {
                        "word_count": chunk["word_count"],
                        "char_count": chunk["char_count"],
                        "embedding_error": str(e),
                    },
                })

        kb.create_chunks(source_id=source.id, chunks=chunk_data)

        # Close AI service
        asyncio.get_event_loop().run_until_complete(ai.close())

        return {
            "source_id": str(source.id),
            "status": "completed",
            "chunks_created": len(chunk_data),
            "chunks_with_embeddings": sum(1 for c in chunk_data if c["embedding"] is not None),
        }

    except Exception as e:
        logger.error(f"KB ingestion task failed: {e}")
        self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def generate_embeddings_task(self, chunk_ids: list, model: str = None):
    """
    Celery task to generate embeddings for a batch of chunks.
    """
    from app.database import SessionLocal
    from sqlalchemy import select
    from app.models.kb import KBChunk

    db = SessionLocal()
    try:
        ai = AIService()
        updated = 0

        for chunk_id in chunk_ids:
            chunk = db.exec(select(KBChunk).where(KBChunk.id == UUID(chunk_id))).first()
            if chunk and not chunk.embedding:
                try:
                    embedding = asyncio.get_event_loop().run_until_complete(
                        ai.embed(chunk.content)
                    )
                    chunk.embedding = embedding
                    db.add(chunk)
                    updated += 1
                except Exception as e:
                    logger.error(f"Embedding failed for chunk {chunk_id}: {e}")

        db.commit()
        asyncio.get_event_loop().run_until_complete(ai.close())

        return {
            "status": "completed",
            "chunks_processed": len(chunk_ids),
            "chunks_updated": updated,
        }

    except Exception as e:
        logger.error(f"Embedding task failed: {e}")
        self.retry(exc=e, countdown=60)
    finally:
        db.close()
