from app.services.kb_service import kb_service
from app.services.youtube_service import VideoAnalysis, VideoMetadata, VideoTranscript


def test_youtube_auto_transcribe_persists_chunks_and_is_idempotent(monkeypatch):
    video_url = "https://youtu.be/pq9WuZ9q4Bg?si=test"
    video_id = "pq9WuZ9q4Bg"
    transcript = (
        "Fair value gap and liquidity sweep setup. "
        "Order block mitigation with risk management. "
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
                {"text": "Fair value gap and liquidity sweep setup.", "start": 12, "duration": 4},
                {"text": "Order block mitigation with risk management.", "start": 45, "duration": 5},
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
    assert status["last_source"]["url"] == video_url
    assert status["last_source"]["chunk_count"] == second["chunk_count"]

    hits = kb_service.search_vectors("liquidity sweep fair value gap", top_k=3)
    assert hits
    assert hits[0]["source_title"] == "ICT short setup"

    answer = kb_service.chat_answer("What setup does the video describe?", top_k=2)
    assert answer["context_chunks"] > 0
    assert answer["sources"][0]["url"] == video_url

    removed = kb_service.remove_source(status["last_source"]["id"])
    assert removed["removed"] is True
    assert kb_service.status()["source_count"] == 0
    assert kb_service.status()["chunk_count"] == 0
