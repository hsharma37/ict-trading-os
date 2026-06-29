"""
Video Analysis Agent — LLM-powered structured analysis of YouTube video transcripts.

Inspired by agentic AI pipelines from modern video analysis projects:
- Uses LangChain-style prompt engineering for structured outputs
- Generates trading-specific insights for ICT methodology
- Supports both Ollama (local) and OpenAI-compatible APIs
"""
import json
import re
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

import httpx

from app.services.youtube_service import VideoTranscript, VideoMetadata, youtube_service


class VideoAnalysisAgent:
    """
    Agent that analyzes video transcripts and generates structured,
    trading-relevant insights using an LLM.
    """

    def __init__(self, ollama_host: str = None, model: str = None, openai_api_key: str = None):
        self.ollama_host = ollama_host or os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.model = model or os.getenv('OLLAMA_MODEL', 'llama3.2')
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        self.openai_base = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
        self._client = httpx.AsyncClient(timeout=120.0)

    # ────────────────────────────────────────────────
    # LLM Core
    # ────────────────────────────────────────────────

    async def _generate(self, prompt: str, system: str = None, temperature: float = 0.3) -> str:
        """Generate text using available LLM (Ollama or OpenAI)."""
        if self.openai_api_key:
            return await self._generate_openai(prompt, system, temperature)
        return await self._generate_ollama(prompt, system, temperature)

    async def _generate_ollama(self, prompt: str, system: str = None, temperature: float = 0.3) -> str:
        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": self.model,
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
        except Exception as e:
            print(f"[Ollama] Error: {e}")
            return ""

    async def _generate_openai(self, prompt: str, system: str = None, temperature: float = 0.3) -> str:
        url = f"{self.openai_base}/chat/completions"
        headers = {"Authorization": f"Bearer {self.openai_api_key}", "Content-Type": "application/json"}
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model or "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature,
        }
        try:
            resp = await self._client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[OpenAI] Error: {e}")
            return ""

    # ────────────────────────────────────────────────
    # Analysis Prompts
    # ────────────────────────────────────────────────

    SYSTEM_PROMPT = """You are an expert ICT (Inner Circle Trader) trading mentor and video analyst.
Your task is to analyze YouTube video transcripts and produce structured, actionable insights.

You must respond in valid JSON format ONLY. No markdown, no extra text outside the JSON.

JSON schema:
{
  "summary": "Brief 2-3 sentence summary of the video's core message",
  "key_concepts": ["List of ICT concepts discussed: e.g., MSS, FVG, OB, Liquidity, etc."],
  "timestamps": [
    {"time": "MM:SS", "concept": "Concept name", "description": "What happens at this timestamp"}
  ],
  "ict_relevance": "high|medium|low — how directly relevant to ICT methodology",
  "trading_insights": "Specific trading insights, setups, or rules mentioned",
  "sentiment": "bullish|bearish|neutral — overall market bias discussed",
  "actionable_takeaways": ["List of 3-5 actionable takeaways a trader can apply"],
  "word_count": 0
}
"""

    def _build_analysis_prompt(self, transcript: VideoTranscript, metadata: VideoMetadata) -> str:
        # Truncate very long transcripts to fit in context window
        max_chars = 12000
        text = transcript.text
        if len(text) > max_chars:
            text = text[:max_chars] + "...\n[TRANSCRIPT TRUNCATED FOR LENGTH]"

        segments_text = ""
        if transcript.segments and len(transcript.segments) <= 50:
            segments_text = "\n".join([
                f"[{int(s['start']//60)}:{int(s['start']%60):02d}] {s['text'][:100]}"
                for s in transcript.segments[:30]
            ])

        prompt = f"""Analyze the following YouTube video transcript for ICT trading concepts.

VIDEO TITLE: {metadata.title}
CHANNEL: {metadata.channel}
DURATION: {metadata.duration} seconds
DESCRIPTION: {metadata.description[:500]}

TRANSCRIPT:
{text}

TIMESTAMPED SEGMENTS:
{segments_text}

Now produce the JSON analysis."""
        return prompt

    # ────────────────────────────────────────────────
    # Main Analysis Methods
    # ────────────────────────────────────────────────

    async def analyze_video(self, transcript: VideoTranscript, metadata: VideoMetadata) -> Dict[str, Any]:
        """Run full LLM analysis on a video transcript."""
        if not transcript.text or len(transcript.text.strip()) < 50:
            # Fallback to heuristic analysis if transcript is too short
            return self._fallback_analysis(transcript, metadata)

        prompt = self._build_analysis_prompt(transcript, metadata)
        raw_response = await self._generate(prompt, system=self.SYSTEM_PROMPT, temperature=0.3)

        if not raw_response:
            return self._fallback_analysis(transcript, metadata)

        # Try to parse JSON from response
        try:
            # Find JSON block
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(raw_response)

            # Ensure required fields
            result.setdefault('summary', '')
            result.setdefault('key_concepts', [])
            result.setdefault('timestamps', [])
            result.setdefault('ict_relevance', 'medium')
            result.setdefault('trading_insights', '')
            result.setdefault('sentiment', 'neutral')
            result.setdefault('actionable_takeaways', [])
            result.setdefault('word_count', len(transcript.text.split()))
            return result
        except json.JSONDecodeError:
            print(f"[Agent] JSON parsing failed, using fallback analysis")
            return self._fallback_analysis(transcript, metadata)

    def _fallback_analysis(self, transcript: VideoTranscript, metadata: VideoMetadata) -> Dict[str, Any]:
        """Fallback heuristic analysis when LLM is unavailable."""
        # Use the youtube_service's built-in analysis
        analysis = youtube_service.analyze_transcript(transcript, metadata)
        return {
            'summary': analysis.summary,
            'key_concepts': analysis.key_concepts,
            'timestamps': [
                {'time': t['time'], 'concept': t['concept'], 'description': t['text']}
                for t in analysis.timestamps
            ],
            'ict_relevance': analysis.ict_relevance,
            'trading_insights': analysis.trading_insights,
            'sentiment': analysis.sentiment,
            'actionable_takeaways': [
                f"Focus on {c} concepts from this video" for c in analysis.key_concepts[:5]
            ] if analysis.key_concepts else ['Review transcript manually'],
            'word_count': analysis.word_count,
            'source': 'heuristic_fallback',
        }

    async def analyze_channel(self, channel_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a high-level channel summary from aggregated video analyses.
        """
        videos = channel_results.get('video_results', [])
        top_concepts = channel_results.get('top_concepts', [])
        sentiment = channel_results.get('dominant_sentiment', 'neutral')
        total_words = channel_results.get('total_words', 0)

        # Build a condensed prompt from the video summaries
        summaries = []
        for v in videos[:10]:
            a = v.get('analysis', {})
            if a.get('summary'):
                summaries.append(f"- {v['title']}: {a['summary'][:200]}")

        prompt = f"""You are analyzing a YouTube trading channel. Here are summaries of recent videos:

{chr(10).join(summaries)}

Top concepts across all videos: {', '.join([c for c, _ in top_concepts[:10]])}
Dominant sentiment: {sentiment}
Total transcript words: {total_words}

Produce a JSON summary with this schema:
{{
  "channel_summary": "2-3 sentence summary of the channel's focus and style",
  "core_teaching": "What is the main methodology or system taught?",
  "recommended_for": "Beginner/Intermediate/Advanced — who is this channel best for?",
  "content_quality": "brief assessment",
  "top_concepts": ["list of top 5-7 concepts"],
  "learning_path": ["3-5 suggested videos or topics to watch in order"],
  "strengths": ["channel strengths"],
  "weaknesses": ["channel weaknesses or gaps"]
}}"""

        raw_response = await self._generate(prompt, system=self.SYSTEM_PROMPT, temperature=0.3)

        try:
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(raw_response)
            return result
        except (json.JSONDecodeError, Exception):
            return {
                'channel_summary': f"Channel analysis based on {len(videos)} videos. Top concepts: {', '.join([c for c, _ in top_concepts[:7]])}.",
                'core_teaching': 'ICT-based trading methodology',
                'recommended_for': 'Intermediate',
                'content_quality': 'Good volume of content available',
                'top_concepts': [c for c, _ in top_concepts[:7]],
                'learning_path': ['Start with market structure basics', 'Study fair value gaps', 'Learn order block strategies'],
                'strengths': ['Consistent content', 'ICT-focused'],
                'weaknesses': ['Requires prior knowledge', 'No structured curriculum'],
                'source': 'heuristic_fallback',
            }

    async def close(self):
        await self._client.aclose()


video_analysis_agent = VideoAnalysisAgent()
