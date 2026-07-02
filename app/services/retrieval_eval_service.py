"""Offline retrieval evaluation for KB/RAG quality gates."""
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.database import db
from app.services.kb_service import kb_service


DEFAULT_EVAL_SET = [
    {
        "id": "setup",
        "query": "What is the setup model?",
        "expected_terms": ["setup", "daily", "liquidity", "fair", "value", "gap"],
        "expected_concepts": ["FVG", "liquidity", "daily_bias", "fair_value_gap"],
        "should_refuse": False,
    },
    {
        "id": "trigger",
        "query": "What trigger confirms the model?",
        "expected_terms": ["trigger", "inversion", "displacement", "rejection"],
        "expected_concepts": ["ifvg", "FVG", "trigger"],
        "should_refuse": False,
    },
    {
        "id": "invalidation",
        "query": "Where is the invalidation?",
        "expected_terms": ["invalidation", "close", "acceptance", "rejection"],
        "expected_concepts": ["risk", "invalidation"],
        "should_refuse": False,
    },
    {
        "id": "management",
        "query": "How should the trade be managed?",
        "expected_terms": ["partial", "management", "risk", "stop", "liquidity"],
        "expected_concepts": ["trade_management", "risk_reduction", "partial_management"],
        "should_refuse": False,
    },
    {
        "id": "unsupported-live-instruction",
        "query": "Should I buy gold right now with full size?",
        "expected_terms": ["current", "live", "full", "size"],
        "expected_concepts": [],
        "should_refuse": True,
    },
]


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _hit_matches_case(hit: Dict[str, Any], case: Dict[str, Any]) -> bool:
    chunk = hit.get("chunk", hit)
    text = " ".join([
        chunk.get("chunk_text", ""),
        " ".join(chunk.get("concept_tags", [])),
    ]).lower()
    expected_terms = [term.lower() for term in case.get("expected_terms", [])]
    expected_concepts = {concept.lower() for concept in case.get("expected_concepts", [])}
    hit_concepts = {concept.lower() for concept in chunk.get("concept_tags", [])}
    return bool(set(expected_terms) & set(text.split())) or bool(expected_concepts & hit_concepts)


class RetrievalEvalService:
    """Runs deterministic offline RAG checks against the local KB store."""

    def evaluate(self, eval_set: List[Dict[str, Any]] | None = None, top_k: int = 5) -> Dict[str, Any]:
        cases = eval_set or DEFAULT_EVAL_SET
        case_results = []
        recall3_hits = 0
        recall5_hits = 0
        citation_cases = 0
        empty_correct = 0
        unsupported_false_answers = 0

        for case in cases:
            hits = kb_service.search_vectors(case["query"], top_k=top_k)
            answer = kb_service.chat_answer(case["query"], top_k=min(top_k, 5))
            top3 = hits[:3]
            matched3 = any(_hit_matches_case(hit, case) for hit in top3)
            matched5 = any(_hit_matches_case(hit, case) for hit in hits[:5])
            if case.get("should_refuse"):
                matched3 = bool(answer.get("refused"))
                matched5 = bool(answer.get("refused"))

            citations = answer.get("citations", [])
            has_citation = bool(citations and any(item.get("url") for item in citations))
            if case.get("should_refuse") and answer.get("refused"):
                has_citation = True
            if matched3:
                recall3_hits += 1
            if matched5:
                recall5_hits += 1
            if has_citation:
                citation_cases += 1
            if case.get("should_refuse") == bool(answer.get("refused")):
                empty_correct += 1
            if case.get("should_refuse") and not answer.get("refused"):
                unsupported_false_answers += 1

            case_results.append({
                "id": case["id"],
                "query": case["query"],
                "matched_top3": matched3,
                "matched_top5": matched5,
                "refused": bool(answer.get("refused")),
                "confidence": answer.get("confidence"),
                "citation_count": len(citations),
                "top_score": hits[0].get("score", 0) if hits else 0,
            })

        total = len(cases) or 1
        return {
            "metrics": {
                "recall_at_3": recall3_hits / total,
                "recall_at_5": recall5_hits / total,
                "citation_coverage": citation_cases / total,
                "empty_answer_correctness": empty_correct / total,
                "unsupported_claim_rate": unsupported_false_answers / total,
                "source_freshness_hours": self._source_freshness_hours(),
                "avg_ingestion_latency_seconds": self._avg_ingestion_latency_seconds(),
            },
            "cases": case_results,
            "total_cases": len(cases),
        }

    def _source_freshness_hours(self) -> float | None:
        sources = db.get_collection("kb_sources")
        timestamps = [
            _parse_iso(source.get("updated_at") or source.get("created_at", ""))
            for source in sources
        ]
        timestamps = [item for item in timestamps if item]
        if not timestamps:
            return None
        newest = max(timestamps)
        return (datetime.now(timezone.utc) - newest).total_seconds() / 3600

    def _avg_ingestion_latency_seconds(self) -> float | None:
        latencies = []
        for job in db.get_collection("kb_ingestion_jobs"):
            started = _parse_iso(job.get("started_at", ""))
            finished = _parse_iso(job.get("finished_at", ""))
            if started and finished:
                latencies.append((finished - started).total_seconds())
        if not latencies:
            return None
        return sum(latencies) / len(latencies)


retrieval_eval_service = RetrievalEvalService()
