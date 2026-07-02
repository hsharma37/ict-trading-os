"""
Knowledge Base Router — YouTube ingestion, analysis, semantic search, and AI chat.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from app.services.kb_service import kb_service
from app.services.retrieval_eval_service import retrieval_eval_service

router = APIRouter(prefix="/kb", tags=["Knowledge Base"])

# ────────────────────────────────────────────────
# Schemas
# ────────────────────────────────────────────────

class KBSourceCreate(BaseModel):
    title: str
    url: str
    transcript: Optional[str] = ""
    tags: Optional[str] = ""
    source_type: Optional[str] = "generic"

class AutoTranscribeRequest(BaseModel):
    url: str = Field(..., description="YouTube video, playlist, or channel URL")
    tags: Optional[str] = ""
    use_ai_analysis: Optional[bool] = True
    use_whisper: Optional[bool] = True

class IngestionJobRequest(BaseModel):
    url: str = Field(..., description="YouTube video, playlist, or channel URL")
    tags: Optional[str] = ""
    use_ai_analysis: Optional[bool] = True
    use_whisper: Optional[bool] = True

class ChatRequest(BaseModel):
    query: str = Field(..., description="Question to ask the knowledge base")
    use_vectors: Optional[bool] = True
    top_k: Optional[int] = 5

class AnalyzeChannelRequest(BaseModel):
    channel_url: str = Field(..., description="YouTube channel URL")
    max_videos: Optional[int] = 20

# ────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────

@router.post("/sources")
def add_source(source: KBSourceCreate):
    return kb_service.add_source(
        source.title, source.url, source.transcript, source.tags, source.source_type
    )

@router.get("/sources")
def list_sources():
    return kb_service.list_sources()

@router.get("/sources/{source_id}")
def get_source(source_id: str):
    return kb_service.find_source(source_id)

@router.delete("/sources/{source_id}")
def remove_source(source_id: str):
    return kb_service.remove_source(source_id)

@router.get("/search")
def search(query: str):
    return kb_service.search(query)

@router.get("/search-embeddings")
def search_embeddings(query: str, top_k: int = 5):
    return kb_service.search_vectors(query, top_k=top_k)

@router.post("/auto-transcribe")
def auto_transcribe(request: AutoTranscribeRequest):
    """
    Auto-transcribe a YouTube video, playlist, or channel.
    Supports optional AI analysis and whisper audio fallback.
    """
    try:
        return kb_service.auto_transcribe(
            url=request.url,
            tags=request.tags,
            use_ai_analysis=request.use_ai_analysis,
            use_whisper=request.use_whisper,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@router.post("/ingestion-jobs")
def create_ingestion_job(request: IngestionJobRequest):
    """
    Queue a durable YouTube ingestion job and return its status document.
    """
    try:
        return kb_service.enqueue_auto_transcribe(
            url=request.url,
            tags=request.tags,
            use_ai_analysis=request.use_ai_analysis,
            use_whisper=request.use_whisper,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/ingestion-jobs")
def list_ingestion_jobs(limit: int = 20):
    return kb_service.list_ingestion_jobs(limit=limit)

@router.get("/ingestion-jobs/{job_id}")
def get_ingestion_job(job_id: str):
    job = kb_service.get_ingestion_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return job

@router.post("/chat")
def chat(request: ChatRequest):
    """
    Ask the knowledge base a question. Uses RAG to retrieve relevant chunks
    and synthesize an answer from ingested sources.
    """
    return kb_service.chat_answer(
        query=request.query,
        use_vectors=request.use_vectors,
        top_k=request.top_k,
    )

@router.get("/eval")
def run_retrieval_quality(top_k: int = 5):
    return retrieval_eval_service.evaluate(top_k=top_k)

@router.get("/recommend")
def recommend(query: str):
    return kb_service.recommend(query)

@router.get("/status")
def status():
    return kb_service.status()

@router.post("/support")
def support(confluences: list[str]):
    return kb_service.support_for_confluences(confluences)
