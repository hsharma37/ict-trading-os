"""
AI Service — LLM interactions, setup grading, journal review, and concept extraction.

Uses Ollama for local LLM inference with LiteLLM-style routing.
"""
import logging
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from uuid import UUID

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """
    Service for AI-powered features in the ICT Trading OS.
    Handles LLM calls, setup grading, journal review, and chat.
    """

    def __init__(self, ollama_host: Optional[str] = None, model: Optional[str] = None):
        self.ollama_host = ollama_host or settings.ollama_host
        self.model = model or settings.ollama_model
        self.embedding_model = settings.embedding_model
        self._client = httpx.AsyncClient(timeout=120.0)

    # ────────────────────────────────────────────────
    # LLM Core
    # ────────────────────────────────────────────────

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Send a chat completion request to Ollama.

        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        """
        url = f"{self.ollama_host}/api/chat"
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }

        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Ollama chat error: {e}")
            raise

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        system: Optional[str] = None,
    ) -> str:
        """
        Generate text from a single prompt using Ollama.
        """
        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "temperature": temperature,
            "stream": False,
        }
        if system:
            payload["system"] = system

        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")
        except httpx.HTTPError as e:
            logger.error(f"Ollama generate error: {e}")
            raise

    # ────────────────────────────────────────────────
    # Embeddings
    # ────────────────────────────────────────────────

    async def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        """
        Generate embeddings for text using Ollama.
        """
        url = f"{self.ollama_host}/api/embeddings"
        payload = {
            "model": model or self.embedding_model,
            "prompt": text,
        }

        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("embedding", [])
        except httpx.HTTPError as e:
            logger.error(f"Ollama embedding error: {e}")
            raise

    async def embed_batch(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.
        """
        embeddings = []
        for text in texts:
            emb = await self.embed(text, model)
            embeddings.append(emb)
        return embeddings

    # ────────────────────────────────────────────────
    # AI Use Cases
    # ────────────────────────────────────────────────

    async def grade_setup(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        narrative: str,
        confluence_tags: List[str],
        killzones: List[str],
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        AI-powered pre-trade setup grading.
        Returns a structured assessment with score and feedback.
        """
        system_prompt = """You are an expert ICT (Inner Circle Trader) trading coach. 
Your role is to objectively grade trading setups based on ICT concepts.
You must be strict but fair. Focus on:
- PD Array alignment (premium/discount, fair value)
- Market Structure Shift (MSS) confirmation
- Fair Value Gap (FVG) confluence
- Order Block (OB) quality and location
- Liquidity sweep validation
- Killzone timing
- Risk-to-reward ratio

Respond ONLY in JSON format with this structure:
{
  "overall_grade": 1-10,
  "confidence_score": 0.0-1.0,
  "grade_breakdown": {
    "pd_array": 1-10,
    "market_structure": 1-10,
    "fvg_confluence": 1-10,
    "order_block": 1-10,
    "liquidity": 1-10,
    "timing": 1-10,
    "risk_reward": 1-10
  },
  "strengths": ["..."],
  "weaknesses": ["..."],
  "recommendations": ["..."],
  "risk_warnings": ["..."],
  "execution_notes": "..."
}"""

        user_prompt = f"""Grade this ICT trading setup:

Symbol: {symbol}
Direction: {direction}
Entry Price: {entry_price}
Stop Loss: {stop_loss}
Take Profit: {take_profit}
Risk-to-Reward: {abs(take_profit - entry_price) / abs(entry_price - stop_loss):.2f}

Narrative: {narrative}

Confluence Tags: {', '.join(confluence_tags) if confluence_tags else 'None'}
Killzones: {', '.join(killzones) if killzones else 'None'}

{context or ''}

Provide your grade and detailed feedback."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = await self.chat(messages, temperature=0.3)
        content = response.get("message", {}).get("content", "")

        # Try to parse JSON from the response
        try:
            # Find JSON in the response (Ollama sometimes wraps it in markdown)
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(content)
            return result
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse AI grading response as JSON: {content[:200]}...")
            return {
                "overall_grade": 5,
                "confidence_score": 0.5,
                "grade_breakdown": {},
                "strengths": ["AI response could not be parsed"],
                "weaknesses": ["Please review manually"],
                "recommendations": [content[:500]],
                "risk_warnings": [],
                "execution_notes": "AI parsing failed — review raw output",
                "raw_response": content,
            }

    async def review_journal(
        self,
        trade_summary: str,
        pre_trade_notes: Optional[str] = None,
        post_trade_notes: Optional[str] = None,
        setup_grade: Optional[int] = None,
        execution_grade: Optional[int] = None,
        management_grade: Optional[int] = None,
        pnl: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        AI-powered journal review and narrative generation.
        """
        system_prompt = """You are an expert trading psychologist and ICT mentor.
Review the trader's journal entry and provide:
1. An objective trade narrative
2. Pattern analysis (what worked, what didn't)
3. Emotional/behavioral insights
4. Actionable improvements
5. Related concept references from ICT methodology

Respond ONLY in JSON format:
{
  "trade_narrative": "...",
  "pattern_analysis": {
    "what_worked": ["..."],
    "what_didnt_work": ["..."],
    "missed_opportunities": ["..."]
  },
  "emotional_insights": "...",
  "behavioral_patterns": ["..."],
  "actionable_improvements": ["..."],
  "ict_concepts_applied": ["..."],
  "ict_concepts_missed": ["..."],
  "next_trade_focus": ["..."]
}"""

        user_prompt = f"""Review this trade journal entry:

Trade Summary: {trade_summary}

Pre-Trade Notes: {pre_trade_notes or 'N/A'}
Post-Trade Notes: {post_trade_notes or 'N/A'}

Self-Grades:
- Setup: {setup_grade or 'N/A'}/10
- Execution: {execution_grade or 'N/A'}/10
- Management: {management_grade or 'N/A'}/10

PnL: ${pnl if pnl is not None else 'N/A'}
Tags: {', '.join(tags) if tags else 'None'}

Provide a comprehensive review."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = await self.chat(messages, temperature=0.4)
        content = response.get("message", {}).get("content", "")

        try:
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(content)
            return result
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse journal review response as JSON")
            return {
                "trade_narrative": content[:500],
                "pattern_analysis": {"what_worked": [], "what_didnt_work": [], "missed_opportunities": []},
                "emotional_insights": "Parsing failed — see raw response",
                "behavioral_patterns": [],
                "actionable_improvements": ["Review raw AI output"],
                "ict_concepts_applied": [],
                "ict_concepts_missed": [],
                "next_trade_focus": [],
                "raw_response": content,
            }

    async def chat_rag(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        RAG-enhanced chat: answer a question using retrieved context.
        """
        # Build context from retrieved chunks
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            context_parts.append(
                f"[{i}] {chunk.get('source_title', 'Unknown')} ({chunk.get('source_type', 'Unknown')}):\n"
                f"{chunk.get('content', '')}"
            )

        context_text = "\n\n".join(context_parts)

        system_prompt = """You are an expert ICT (Inner Circle Trader) mentor and educator.
Answer questions based ONLY on the provided context from the knowledge base.
If the context doesn't contain enough information, say so explicitly.
Always cite your sources using [1], [2], etc.
Be concise but thorough. Use ICT terminology correctly."""

        user_prompt = f"""Context from knowledge base:

{context_text}

---

Question: {question}

Answer based on the context above."""

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        if chat_history:
            messages.extend(chat_history)

        messages.append({"role": "user", "content": user_prompt})

        response = await self.chat(messages, temperature=0.3)
        content = response.get("message", {}).get("content", "")

        return {
            "answer": content,
            "sources": [
                {
                    "source_id": chunk.get("source_id"),
                    "source_title": chunk.get("source_title"),
                    "source_type": chunk.get("source_type"),
                    "chunk_index": chunk.get("chunk_index"),
                    "similarity": chunk.get("similarity"),
                }
                for chunk in context_chunks
            ],
            "context_count": len(context_chunks),
        }

    # ────────────────────────────────────────────────
    # Cleanup
    # ────────────────────────────────────────────────

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
