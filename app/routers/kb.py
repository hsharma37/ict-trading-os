"""
Knowledge Base Router — YouTube ingestion, analysis, semantic search, and AI chat.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, List
from app.services.kb_service import kb_service

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
    return kb_service.auto_transcribe(
        url=request.url,
        tags=request.tags,
        use_ai_analysis=request.use_ai_analysis,
        use_whisper=request.use_whisper,
    )

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

@router.get("/recommend")
def recommend(query: str):
    return kb_service.recommend(query)

@router.get("/status")
def status():
    return kb_service.status()

@router.post("/support")
def support(confluences: list[str]):
    return kb_service.support_for_confluences(confluences)
