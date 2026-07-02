from app.services.kb_service import kb_service
from app.services.vector_store import SimpleVectorStore
from app.services.youtube_service import VideoAnalysis, VideoMetadata, VideoTranscript
from app.core.database import db
import time


def test_youtube_auto_transcribe_persists_chunks_and_is_idempotent(monkeypatch):
    video_url = "https://youtu.be/pq9WuZ9q4Bg?si=test"
    video_id = "pq9WuZ9q4Bg"
    transcript = (
        "Fair value gap and liquidity sweep setup creates the setup model. "
        "Order block mitigation gives the trigger after displacement. "
        "Invalidation is beyond the swept liquidity and risk management controls the trade. "
        "Management takes partials at opposing liquidity. "
    ) * 80

    metadata = VideoMetadata(
        video_id=video_id,
        title="ICT short setup",
        channel="ICT Test",
        duration=600,
        view_count=1000,
        upload_date="2026-07-01",
        url=video_url,
    )

    def fake_metadata(url):
        return metadata

    def fake_transcript(requested_video_id, languages=None, allow_whisper=True):
        assert requested_video_id == video_id
        assert allow_whisper is False
        return VideoTranscript(
            video_id=video_id,
            text=transcript,
            segments=[
                {"text": "Fair value gap and liquidity sweep setup creates the setup model.", "start": 12, "duration": 4},
                {"text": "Order block mitigation gives the trigger after displacement.", "start": 45, "duration": 5},
                {"text": "Invalidation is beyond the swept liquidity and risk management controls the trade.", "start": 90, "duration": 8},
                {"text": "Management takes partials at opposing liquidity.", "start": 130, "duration": 6},
            ],
            source="caption",
        )

    def fake_analysis(transcript_result, meta):
        return VideoAnalysis(
            video_id=video_id,
            title=meta.title,
            summary="ICT concepts extracted",
            key_concepts=["FVG", "Liquidity", "OB", "Risk Management"],
            timestamps=[{"time": "0:12", "concept": "FVG", "text": "Fair value gap"}],
            ict_relevance="high",
            trading_insights="FVG plus liquidity sweep.",
            sentiment="bearish",
            word_count=len(transcript_result.text.split()),
        )

    monkeypatch.setattr("app.services.kb_service.youtube_service.fetch_video_metadata", fake_metadata)
    monkeypatch.setattr("app.services.kb_service.youtube_service.fetch_video_transcript", fake_transcript)
    monkeypatch.setattr("app.services.kb_service.youtube_service.analyze_transcript", fake_analysis)

    first = kb_service.auto_transcribe(
        video_url,
        tags="ict,strategy",
        use_ai_analysis=False,
        use_whisper=False,
    )
    second = kb_service.auto_transcribe(
        video_url,
        tags="ict,strategy",
        use_ai_analysis=False,
        use_whisper=False,
    )

    assert first["source_count"] == 1
    assert second["source_count"] == 1
    assert second["chunk_count"] > 0

    status = kb_service.status()
    assert status["source_count"] == 1
    assert status["youtube_source_count"] == 1
    assert status["chunk_count"] == second["chunk_count"]
    assert status["last_source"]["url"] == f"https://www.youtube.com/watch?v={video_id}"
    assert status["last_source"]["original_url"] == video_url
    assert status["last_source"]["chunk_count"] == second["chunk_count"]
    assert status["concept_count"] >= 3
    assert status["last_source"]["content_hash"]
    assert status["last_source"]["analysis_artifacts"]["playbook_rules"]

    chunks = db.find("kb_chunks", source_id=status["last_source"]["id"])
    assert chunks
    assert all(chunk.get("citation", {}).get("url") == f"https://www.youtube.com/watch?v={video_id}" for chunk in chunks)
    assert all(chunk.get("timestamp") or chunk.get("span") for chunk in chunks)
    assert all(350 <= chunk.get("token_count", 0) <= 512 for chunk in chunks[:-1])

    hits = kb_service.search_vectors("liquidity sweep fair value gap invalidation management", top_k=3)
    assert hits
    assert hits[0]["source_title"] == "ICT short setup"
    assert hits[0]["source_url"] == f"https://www.youtube.com/watch?v={video_id}"
    assert hits[0]["citation"]["timestamp"]
    assert hits[0]["chunk_score"] == hits[0]["score"]
    assert "FVG" in hits[0]["concept_tags"]

    answer = kb_service.chat_answer("What setup, trigger, invalidation, and management does the video describe?", top_k=2)
    assert answer["context_chunks"] > 0
    assert answer["sources"][0]["url"] == f"https://www.youtube.com/watch?v={video_id}"

    removed = kb_service.remove_source(status["last_source"]["id"])
    assert removed["removed"] is True
    assert kb_service.status()["source_count"] == 0
    assert kb_service.status()["chunk_count"] == 0


def test_manual_source_upsert_refreshes_chunks_with_citations():
    source = kb_service.add_source(
        title="Manual ICT playbook",
        url="https://example.com/playbook?utm_source=noise",
        transcript="Liquidity sweep into fair value gap. Invalidation is above the high. " * 260,
        tags="manual,ict",
        source_type="manual",
    )
    updated = kb_service.add_source(
        title="Manual ICT playbook updated",
        url="https://example.com/playbook",
        transcript="Liquidity sweep into fair value gap with management at opposing liquidity. " * 260,
        tags="manual,ict",
        source_type="manual",
    )

    assert updated["id"] == source["id"]
    assert kb_service.status()["source_count"] == 1
    chunks = db.find("kb_chunks", source_id=source["id"])
    assert chunks
    assert all(chunk.get("source_content_hash") == updated["content_hash"] for chunk in chunks)
    assert all(chunk.get("citation", {}).get("title") == "Manual ICT playbook updated" for chunk in chunks)


def test_async_ingestion_job_persists_status(monkeypatch):
    video_url = "https://youtu.be/pq9WuZ9q4Bg?si=job"
    video_id = "pq9WuZ9q4Bg"
    transcript = "Liquidity sweep setup trigger invalidation management. " * 520

    metadata = VideoMetadata(
        video_id=video_id,
        title="ICT job source",
        channel="ICT Test",
        duration=600,
        view_count=1000,
        upload_date="2026-07-01",
        url=video_url,
    )

    monkeypatch.setattr("app.services.kb_service.youtube_service.fetch_video_metadata", lambda url: metadata)
    monkeypatch.setattr(
        "app.services.kb_service.youtube_service.fetch_video_transcript",
        lambda requested_video_id, languages=None, allow_whisper=True: VideoTranscript(
            video_id=video_id,
            text=transcript,
            segments=[
                {"text": "Liquidity sweep setup trigger invalidation management.", "start": 30, "duration": 5},
            ] * 520,
            source="caption",
        ),
    )
    monkeypatch.setattr(
        "app.services.kb_service.youtube_service.analyze_transcript",
        lambda transcript_result, meta: VideoAnalysis(
            video_id=video_id,
            title=meta.title,
            summary="Async extraction",
            key_concepts=["liquidity", "risk management"],
            timestamps=[{"time": "0:30", "concept": "liquidity", "text": "Liquidity sweep"}],
            ict_relevance="high",
            trading_insights="Manage risk.",
            sentiment="neutral",
            word_count=len(transcript_result.text.split()),
        ),
    )

    job = kb_service.enqueue_auto_transcribe(video_url, tags="job", use_ai_analysis=False, use_whisper=False)
    assert job["status"] == "QUEUED"

    saved = {}
    for _ in range(50):
        saved = kb_service.get_ingestion_job(job["id"])
        if saved.get("status") in {"SUCCEEDED", "FAILED"}:
            break
        time.sleep(0.05)

    assert saved["status"] == "SUCCEEDED"
    assert saved["result"]["source_count"] == 1
    assert saved["result"]["created"][0]["url"] == f"https://www.youtube.com/watch?v={video_id}"
    assert kb_service.status()["latest_ingestion_job"]["id"] == job["id"]


def test_vector_store_delegates_to_pgvector_backend(monkeypatch):
    class FakeDB:
        def __init__(self):
            self.called = False

        def search_kb_chunks_by_embedding(self, query_embedding, top_k=5):
            self.called = True
            assert query_embedding == [0.25, 0.75]
            assert top_k == 2
            return [
                {
                    "chunk": {
                        "id": "chunk-1",
                        "source_id": "source-1",
                        "chunk_text": "Liquidity sweep into fair value gap.",
                    },
                    "score": 0.91,
                }
            ]

        def get_collection(self, name):
            raise AssertionError("pgvector hits should avoid local collection scanning")

    fake_db = FakeDB()
    store = SimpleVectorStore()
    monkeypatch.setattr("app.services.vector_store.db", fake_db)
    monkeypatch.setattr(store, "_embed_text", lambda query: [0.25, 0.75])

    hits = store._search_embeddings("liquidity sweep", top_k=2)

    assert fake_db.called is True
    assert hits[0]["score"] == 0.91
    assert hits[0]["chunk"]["source_id"] == "source-1"
