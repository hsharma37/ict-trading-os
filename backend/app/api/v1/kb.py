from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlmodel import Session
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging

from app.database import get_db
from app.services.knowledge_service import KnowledgeBaseService
from app.services.ai_service import AIService
from app.services.rag_orchestrator import LangGraphRAGOrchestrator
from app.services.document_processor import chunk_text_semantic, format_transcript_for_kb, extract_youtube_id

logger = logging.getLogger(__name__)
router = APIRouter()

# ────────────────────────────────────────────────
# Sources
# ────────────────────────────────────────────────

@router.post("/sources", status_code=201)
async def add_source(
    user_id: UUID,
    source_type: str,  # youtube, transcript, pdf, note
    title: str,
    url: Optional[str] = None,
    content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
):
    """
    Add a new knowledge base source.
    For transcripts, content should be the raw text.
    For YouTube, url should be the video URL.
    """
    kb = KnowledgeBaseService(db)

    # Extract YouTube ID if applicable
    if source_type == "youtube" and url:
        youtube_id = extract_youtube_id(url)
        if youtube_id:
            metadata = metadata or {}
            metadata["youtube_id"] = youtube_id

    source = kb.create_source(
        user_id=user_id,
        source_type=source_type,
        title=title,
        url=url,
        content=content,
        metadata=metadata,
    )

    return {
        "source_id": source.id,
        "title": source.title,
        "source_type": source.source_type,
        "status": "created",
    }


@router.get("/sources")
async def list_sources(
    user_id: UUID,
    source_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all knowledge base sources for a user."""
    kb = KnowledgeBaseService(db)
    sources = kb.list_sources(user_id, source_type)
    return [
        {
            "id": s.id,
            "title": s.title,
            "source_type": s.source_type,
            "url": s.url,
            "chunk_count": s.chunk_count,
            "metadata": s.metadata,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sources
    ]


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete a knowledge base source and all its chunks."""
    kb = KnowledgeBaseService(db)
    success = kb.delete_source(source_id)
    if not success:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"status": "deleted", "source_id": source_id}


# ────────────────────────────────────────────────
# Ingestion
# ────────────────────────────────────────────────

@router.post("/ingest", status_code=202)
async def ingest_content(
    user_id: UUID,
    source_type: str,
    title: str,
    content: Optional[str] = None,
    url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
):
    """
    Ingest content into the knowledge base: chunk, embed, and store.
    This is a synchronous version for small texts. For large documents,
    use the Celery background task endpoint.
    """
    kb = KnowledgeBaseService(db)
    ai = AIService()

    # Create source
    source = kb.create_source(
        user_id=user_id,
        source_type=source_type,
        title=title,
        url=url,
        content=content,
        metadata=metadata,
    )

    if not content:
        return {
            "source_id": source.id,
            "status": "created_without_content",
            "message": "Source created but no content to chunk. Add content later.",
        }

    # Clean and format content
    formatted = format_transcript_for_kb(content, title)

    # Chunk the content
    chunks = chunk_text_semantic(formatted, max_chunk_size=512, chunk_overlap=50)

    # Generate embeddings for each chunk
    chunk_data = []
    for chunk in chunks:
        try:
            embedding = await ai.embed(chunk["content"])
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
            # Store without embedding as fallback
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

    # Store chunks in database
    kb.create_chunks(source_id=source.id, chunks=chunk_data)

    await ai.close()

    return {
        "source_id": source.id,
        "status": "ingested",
        "chunks_created": len(chunk_data),
        "chunks_with_embeddings": sum(1 for c in chunk_data if c["embedding"] is not None),
    }


# ────────────────────────────────────────────────
# Search
# ────────────────────────────────────────────────

@router.post("/search")
async def search(
    user_id: UUID,
    query: str,
    top_k: int = 5,
    source_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Semantic search over the knowledge base.
    """
    kb = KnowledgeBaseService(db)
    ai = AIService()

    # Generate query embedding
    try:
        query_embedding = await ai.embed(query)
    except Exception as e:
        logger.error(f"Query embedding failed: {e}")
        # Fallback to full-text search
        results = kb.search_text(user_id, query, top_k)
        await ai.close()
        return {
            "query": query,
            "method": "fulltext_fallback",
            "results": results,
            "count": len(results),
        }

    # Semantic search
    results = kb.search_chunks(
        user_id=user_id,
        query_embedding=query_embedding,
        top_k=top_k,
        source_type=source_type,
    )

    await ai.close()

    return {
        "query": query,
        "method": "semantic",
        "results": results,
        "count": len(results),
    }


# ────────────────────────────────────────────────
# RAG Query
# ────────────────────────────────────────────────

@router.post("/query")
async def rag_query(
    user_id: UUID,
    query: str,
    top_k: int = 5,
    chat_history: Optional[List[Dict[str, str]]] = None,
    db: Session = Depends(get_db),
):
    """
    RAG query: retrieve relevant documents, then generate an AI answer.
    Uses the LangGraph adaptive RAG orchestrator.
    """
    kb = KnowledgeBaseService(db)
    ai = AIService()
    orchestrator = LangGraphRAGOrchestrator(kb, ai)

    result = await orchestrator.run(
        query=query,
        user_id=user_id,
        chat_history=chat_history,
    )

    await ai.close()

    return {
        "query": query,
        "answer": result["answer"],
        "sources": result["sources"],
        "retrieved_chunks": result["retrieved_chunks"],
        "is_relevant": result["is_relevant"],
        "hallucination_check": result["hallucination_check"],
        "requery_attempts": result["requery_attempts"],
        "error": result["error"],
    }


# ────────────────────────────────────────────────
# Background Ingestion (Celery)
# ────────────────────────────────────────────────

@router.post("/ingest-async", status_code=202)
async def ingest_async(
    user_id: UUID,
    source_type: str,
    title: str,
    content: Optional[str] = None,
    url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Queue a knowledge base ingestion task for background processing.
    Returns a task ID for tracking.
    """
    from app.jobs.tasks import ingest_knowledge_base_task

    task = ingest_knowledge_base_task.delay(
        user_id=str(user_id),
        source_type=source_type,
        title=title,
        content=content,
        url=url,
        metadata=metadata,
    )

    return {
        "task_id": task.id,
        "status": "queued",
        "message": "Ingestion task queued. Check /api/v1/kb/tasks/{task_id} for status.",
    }


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Check the status of a background ingestion task."""
    from celery.result import AsyncResult
    from app.jobs import celery_app

    result = AsyncResult(task_id, app=celery_app)

    return {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
        "result": result.result if result.successful() else None,
        "error": str(result.result) if result.failed() else None,
    }
