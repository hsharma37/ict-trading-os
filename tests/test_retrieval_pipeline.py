from app.services.kb_service import kb_service
from app.services.retrieval_eval_service import retrieval_eval_service
from app.services.vector_store import SimpleVectorStore


def seed_retrieval_source():
    transcript = (
        "The setup uses daily bias and a sellside liquidity draw into a fair value gap. "
        "The trigger is an inversion fair value gap with displacement and rejection. "
        "Invalidation is a body close or acceptance where rejection was expected. "
        "Management reduces risk, moves the stop, takes partials below liquidity, and journals screenshots. "
        "Risk reduction and partial management keep the model from becoming a live trade instruction. "
    ) * 80
    return kb_service.add_source(
        title="pq9WuZ9q4Bg ICT retrieval seed",
        url="https://youtu.be/pq9WuZ9q4Bg?si=batch4",
        transcript=transcript,
        tags="ifvg,fair_value_gap,sellside_liquidity,macro_window,daily_bias,risk_reduction,partial_management",
        source_type="youtube",
        metadata={"video_id": "pq9WuZ9q4Bg", "channel": "ICT Test"},
        transcript_segments=[
            {"text": "The setup uses daily bias and a sellside liquidity draw into a fair value gap.", "start": 10, "duration": 8},
            {"text": "The trigger is an inversion fair value gap with displacement and rejection.", "start": 45, "duration": 8},
            {"text": "Invalidation is a body close or acceptance where rejection was expected.", "start": 80, "duration": 7},
            {"text": "Management reduces risk, moves the stop, takes partials below liquidity, and journals screenshots.", "start": 120, "duration": 10},
        ] * 80,
    )


def test_deterministic_hash_embedding_is_stable_and_pgvector_sized():
    store = SimpleVectorStore()
    first = store._hash_embedding("liquidity sweep fair value gap")
    second = store._hash_embedding("liquidity sweep fair value gap")
    different = store._hash_embedding("journal screenshot evidence")

    assert len(first) == 384
    assert first == second
    assert first != different
    assert store.embedding_info()["dimensions"] == 384


def test_chat_answer_contract_cites_supported_answers_and_refuses_unsupported_trade_calls():
    seed_retrieval_source()

    supported = kb_service.chat_answer(
        "What setup, trigger, invalidation, and management does the video describe?",
        top_k=4,
    )
    assert supported["refused"] is False
    assert supported["confidence"] in {"medium", "high"}
    assert supported["citations"]
    assert supported["citations"][0]["url"] == "https://www.youtube.com/watch?v=pq9WuZ9q4Bg"
    assert "safety" not in supported["answer"].lower() or supported["safety_disclaimer"]

    unsupported = kb_service.chat_answer("Should I buy gold right now with full size?", top_k=4)
    assert unsupported["refused"] is True
    assert unsupported["confidence"] == "low"
    assert unsupported["missing_context"]
    assert "Educational only" in unsupported["safety_disclaimer"]


def test_offline_retrieval_eval_reports_metrics_for_ci():
    seed_retrieval_source()

    result = retrieval_eval_service.evaluate(top_k=5)
    metrics = result["metrics"]

    assert result["total_cases"] >= 5
    assert metrics["recall_at_3"] >= 0.6
    assert metrics["recall_at_5"] >= 0.8
    assert metrics["citation_coverage"] >= 0.8
    assert metrics["empty_answer_correctness"] >= 0.8
    assert metrics["unsupported_claim_rate"] == 0
    assert metrics["source_freshness_hours"] is not None
