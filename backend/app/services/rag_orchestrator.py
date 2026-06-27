"""
LangGraph Orchestrator — Adaptive RAG workflow for ICT knowledge queries.

Implements the query → retrieve → grade → answer → self-correct pipeline.
"""
import logging
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from dataclasses import dataclass

from app.services.knowledge_service import KnowledgeBaseService
from app.services.ai_service import AIService
from app.services.document_processor import chunk_text

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────
# State Definitions (LangGraph-style)
# ────────────────────────────────────────────────

class RAGState(TypedDict):
    """State for the adaptive RAG workflow."""
    query: str
    query_embedding: Optional[List[float]]
    retrieved_chunks: List[Dict[str, Any]]
    relevance_scores: List[float]
    is_relevant: bool
    answer: Optional[str]
    sources: List[Dict[str, Any]]
    hallucination_check: Optional[Dict[str, Any]]
    needs_requery: bool
    requery_attempts: int
    max_requery_attempts: int
    error: Optional[str]


@dataclass
class RAGConfig:
    """Configuration for the RAG pipeline."""
    top_k: int = 5
    relevance_threshold: float = 0.7
    max_requery_attempts: int = 2
    temperature: float = 0.3


class LangGraphRAGOrchestrator:
    """
    Adaptive RAG orchestrator using a LangGraph-style pipeline.

    Workflow:
    1. query → 2. retrieve → 3. grade → 4. answer → 5. hallucination_check → 6. self_correct
    """

    def __init__(
        self,
        kb_service: KnowledgeBaseService,
        ai_service: AIService,
        config: Optional[RAGConfig] = None,
    ):
        self.kb = kb_service
        self.ai = ai_service
        self.config = config or RAGConfig()

    # ────────────────────────────────────────────────
    # Step 1: Query Embedding
    # ────────────────────────────────────────────────

    async def _embed_query(self, state: RAGState) -> RAGState:
        """Generate embedding for the query."""
        try:
            embedding = await self.ai.embed(state["query"])
            state["query_embedding"] = embedding
            logger.debug(f"Query embedded: {len(embedding)} dims")
        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            state["error"] = f"Embedding failed: {str(e)}"
        return state

    # ────────────────────────────────────────────────
    # Step 2: Document Retrieval
    # ────────────────────────────────────────────────

    async def _retrieve(self, state: RAGState) -> RAGState:
        """Retrieve relevant chunks from the knowledge base."""
        if state.get("error"):
            return state

        if not state.get("query_embedding"):
            state["error"] = "No query embedding available"
            return state

        try:
            # Get user_id from context (should be passed in state)
            # For now, use a placeholder that will be replaced by the caller
            user_id = state.get("user_id")
            if not user_id:
                state["error"] = "No user_id in state"
                return state

            chunks = self.kb.search_chunks(
                user_id=user_id,
                query_embedding=state["query_embedding"],
                top_k=self.config.top_k,
            )
            state["retrieved_chunks"] = chunks
            logger.info(f"Retrieved {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            state["error"] = f"Retrieval failed: {str(e)}"
        return state

    # ────────────────────────────────────────────────
    # Step 3: Relevance Grading
    # ────────────────────────────────────────────────

    async def _grade_relevance(self, state: RAGState) -> RAGState:
        """Grade whether retrieved chunks are relevant to the query."""
        if state.get("error"):
            return state

        chunks = state.get("retrieved_chunks", [])
        if not chunks:
            state["is_relevant"] = False
            state["needs_requery"] = True
            return state

        # Simple threshold-based grading
        # In a more advanced version, use an LLM to grade relevance
        scores = []
        for chunk in chunks:
            similarity = chunk.get("similarity", 0)
            scores.append(similarity)

        avg_score = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0

        state["relevance_scores"] = scores

        # Determine if documents are relevant enough
        if max_score >= self.config.relevance_threshold or avg_score >= 0.5:
            state["is_relevant"] = True
            state["needs_requery"] = False
        else:
            state["is_relevant"] = False
            state["needs_requery"] = True

        logger.info(f"Relevance: avg={avg_score:.3f}, max={max_score:.3f}, relevant={state['is_relevant']}")
        return state

    # ────────────────────────────────────────────────
    # Step 4: Answer Generation
    # ────────────────────────────────────────────────

    async def _generate_answer(self, state: RAGState) -> RAGState:
        """Generate answer using retrieved context."""
        if state.get("error"):
            return state

        if not state.get("is_relevant"):
            state["answer"] = (
                "I couldn't find relevant information in your knowledge base to answer this question. "
                "Try adding more sources or rephrasing your question."
            )
            return state

        try:
            result = await self.ai.chat_rag(
                question=state["query"],
                context_chunks=state["retrieved_chunks"],
            )
            state["answer"] = result["answer"]
            state["sources"] = result["sources"]
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            state["error"] = f"Answer generation failed: {str(e)}"
        return state

    # ────────────────────────────────────────────────
    # Step 5: Hallucination Check
    # ────────────────────────────────────────────────

    async def _check_hallucination(self, state: RAGState) -> RAGState:
        """Check if the generated answer is grounded in the retrieved documents."""
        if state.get("error") or not state.get("answer"):
            return state

        # Simple heuristic: check if answer contains key phrases from sources
        # In a more advanced version, use an LLM to verify grounding
        answer = state["answer"].lower()
        chunks = state.get("retrieved_chunks", [])

        grounding_score = 0.0
        total_checks = 0

        for chunk in chunks:
            content = chunk.get("content", "").lower()
            # Extract key phrases (simple: words > 5 chars)
            words = [w for w in content.split() if len(w) > 5]
            if words:
                matches = sum(1 for w in words if w in answer)
                score = matches / len(words)
                grounding_score += score
                total_checks += 1

        avg_grounding = grounding_score / total_checks if total_checks > 0 else 0

        state["hallucination_check"] = {
            "grounding_score": avg_grounding,
            "is_grounded": avg_grounding > 0.1,  # At least 10% of key terms appear
        }

        if not state["hallucination_check"]["is_grounded"] and state["requery_attempts"] < state["max_requery_attempts"]:
            state["needs_requery"] = True

        logger.info(f"Hallucination check: grounding={avg_grounding:.3f}, grounded={state['hallucination_check']['is_grounded']}")
        return state

    # ────────────────────────────────────────────────
    # Step 6: Self-Correction (Re-query)
    # ────────────────────────────────────────────────

    async def _self_correct(self, state: RAGState) -> RAGState:
        """Reformulate query and retry if answer is not grounded or relevant."""
        if not state.get("needs_requery"):
            return state

        if state["requery_attempts"] >= state["max_requery_attempts"]:
            state["answer"] = (
                "I couldn't generate a reliable answer after multiple attempts. "
                "Please check your knowledge base or rephrase your question."
            )
            state["needs_requery"] = False
            return state

        # Increment attempt counter
        state["requery_attempts"] += 1

        # Try full-text search as fallback
        try:
            user_id = state.get("user_id")
            if user_id:
                text_results = self.kb.search_text(
                    user_id=user_id,
                    query=state["query"],
                    top_k=self.config.top_k,
                )
                if text_results:
                    state["retrieved_chunks"] = text_results
                    state["needs_requery"] = False
                    # Retry answer generation with new chunks
                    return await self._generate_answer(state)
        except Exception as e:
            logger.warning(f"Re-query fallback failed: {e}")

        state["needs_requery"] = False
        return state

    # ────────────────────────────────────────────────
    # Main Pipeline
    # ────────────────────────────────────────────────

    async def run(
        self,
        query: str,
        user_id: Any,  # UUID or string
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Run the full adaptive RAG pipeline.

        Returns:
            {
                "answer": str,
                "sources": List[dict],
                "retrieved_chunks": int,
                "is_relevant": bool,
                "hallucination_check": dict,
                "requery_attempts": int,
                "error": str | None,
            }
        """
        # Initialize state
        state: RAGState = {
            "query": query,
            "query_embedding": None,
            "retrieved_chunks": [],
            "relevance_scores": [],
            "is_relevant": False,
            "answer": None,
            "sources": [],
            "hallucination_check": None,
            "needs_requery": False,
            "requery_attempts": 0,
            "max_requery_attempts": self.config.max_requery_attempts,
            "error": None,
            "user_id": user_id,
        }

        # Execute pipeline steps
        steps = [
            self._embed_query,
            self._retrieve,
            self._grade_relevance,
            self._generate_answer,
            self._check_hallucination,
            self._self_correct,
        ]

        for step in steps:
            try:
                state = await step(state)
            except Exception as e:
                logger.error(f"Pipeline step {step.__name__} failed: {e}")
                state["error"] = f"Pipeline step failed: {str(e)}"
                break

        return {
            "answer": state["answer"] or "No answer generated",
            "sources": state["sources"],
            "retrieved_chunks": len(state["retrieved_chunks"]),
            "is_relevant": state["is_relevant"],
            "hallucination_check": state["hallucination_check"],
            "requery_attempts": state["requery_attempts"],
            "error": state["error"],
        }
