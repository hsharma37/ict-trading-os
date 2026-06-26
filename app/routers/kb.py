"""Knowledge Base Router."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.kb_service import kb_service

router = APIRouter(prefix="/kb", tags=["Knowledge Base"])

class KBSourceCreate(BaseModel):
    title: str
    url: str
    transcript: Optional[str] = ""
    tags: Optional[str] = ""
    source_type: Optional[str] = "generic"

class AutoTranscribeRequest(BaseModel):
    url: str
    tags: Optional[str] = ""

@router.post("/sources")
def add_source(source: KBSourceCreate):
    return kb_service.add_source(source.title, source.url, source.transcript, source.tags, source.source_type)

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
def search_embeddings(query: str):
    return kb_service.search_vectors(query)

@router.post("/auto-transcribe")
def auto_transcribe(request: AutoTranscribeRequest):
    return kb_service.auto_transcribe(request.url, request.tags)

@router.get("/recommend")
def recommend(query: str):
    return kb_service.recommend(query)

@router.get("/status")
def status():
    return kb_service.status()

@router.post("/support")
def support(confluences: list[str]):
    return kb_service.support_for_confluences(confluences)
