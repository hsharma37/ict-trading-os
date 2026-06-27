"""
Background tasks for the ICT Trading OS.

Currently stubs. Will be populated with:
- Transcript ingestion
- Embedding generation
- Alert scanning
- Market data backfills
"""
from app.jobs import celery_app


@celery_app.task(bind=True, max_retries=3)
def ingest_transcript(self, source_url: str, source_type: str = 