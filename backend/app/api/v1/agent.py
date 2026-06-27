from fastapi import APIRouter, Depends
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging

from app.services.ai_service import AIService

logger = logging.getLogger(__name__)
router = APIRouter()

# ────────────────────────────────────────────────
# AI Chat
# ────────────────────────────────────────────────

@router.post("/chat")
async def chat(
    message: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
):
    """
    General AI chat with the ICT mentor.
    """
    ai = AIService()

    messages = chat_history or []
    messages.append({"role": "user", "content": message})

    system_prompt = """You are an expert ICT (Inner Circle Trader) mentor and trading psychologist.
You help traders understand ICT concepts, improve their trading, and develop discipline.
Be encouraging but honest. Focus on:
- ICT methodology (PD arrays, market structure, order blocks, fair value gaps, liquidity)
- Risk management and psychology
- Trade review and improvement
- Concept explanation and application

Keep responses concise and actionable."""

    messages.insert(0, {"role": "system", "content": system_prompt})

    try:
        response = await ai.chat(messages, model=model, temperature=temperature)
        content = response.get("message", {}).get("content", "")

        return {
            "response": content,
            "model": model or ai.model,
            "temperature": temperature,
        }
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        return {"error": str(e)}
    finally:
        await ai.close()


# ────────────────────────────────────────────────
# Setup Grading
# ────────────────────────────────────────────────

@router.post("/grade-setup")
async def grade_setup(
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    narrative: str = "",
    confluence_tags: Optional[List[str]] = None,
    killzones: Optional[List[str]] = None,
    context: Optional[str] = None,
):
    """
    AI-powered pre-trade setup grading.
    Returns structured assessment with score and feedback.
    """
    ai = AIService()

    try:
        result = await ai.grade_setup(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            narrative=narrative,
            confluence_tags=confluence_tags or [],
            killzones=killzones or [],
            context=context,
        )
        return result
    except Exception as e:
        logger.error(f"Setup grading error: {e}")
        return {"error": str(e)}
    finally:
        await ai.close()


# ────────────────────────────────────────────────
# Journal Review
# ────────────────────────────────────────────────

@router.post("/journal-review")
async def journal_review(
    trade_summary: str,
    pre_trade_notes: Optional[str] = None,
    post_trade_notes: Optional[str] = None,
    setup_grade: Optional[int] = None,
    execution_grade: Optional[int] = None,
    management_grade: Optional[int] = None,
    pnl: Optional[float] = None,
    tags: Optional[List[str]] = None,
):
    """
    AI-powered journal review and narrative generation.
    """
    ai = AIService()

    try:
        result = await ai.review_journal(
            trade_summary=trade_summary,
            pre_trade_notes=pre_trade_notes,
            post_trade_notes=post_trade_notes,
            setup_grade=setup_grade,
            execution_grade=execution_grade,
            management_grade=management_grade,
            pnl=pnl,
            tags=tags,
        )
        return result
    except Exception as e:
        logger.error(f"Journal review error: {e}")
        return {"error": str(e)}
    finally:
        await ai.close()
