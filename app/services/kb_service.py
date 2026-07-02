"""
Knowledge Base Service — Ingestion, analysis, and retrieval with AI-powered chat.

Uses modern YouTube transcription (yt-dlp + youtube-transcript-api + whisper fallback),
agent-based video analysis, and sentence-transformer embeddings for semantic search.
"""
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.core.database import db
from app.services.vector_store import vector_store
from app.services.youtube_service import youtube_service, VideoAnalysis
from app.services.video_analysis_agent import video_analysis_agent


class KBService:
    KEYWORDS_MAP = {
        "MSS": ["market structure shift", "mss", "bos", "break of structure", "change of character", "choch"],
        "FVG": ["fair value gap", "fvg", "imbalances", "inefficiency", "void"],
        "OB": ["order block", "orderblock", "order block", "ob", "breaker block", "mitigation block"],
        "liquidity": ["liquidity", "stop run", "liquidity sweep", "liquidity pool", "inducement", "stop hunt"],
        "pd_arrays": ["premium", "discount", "optimal trade entry", "ote", "fibonacci", "50%", "equilibrium"],
        "session": ["london open", "new york", "asian session", "killzone", "ny session"],
        "bias": ["bullish", "bearish", "neutral", "bias", "directional bias"],
        "time": ["timeframe", "daily bias", "weekly bias", "monthly bias", "higher timeframe"],
        "trade_management": ["risk management", "lot sizing", "position sizing", "money management", "risk reward", "1:2", "1:3"],
    }

    def normalize_tags(self, tags: Optional[str]) -> List[str]:
        if not tags:
            return []
        return [t.strip().lower() for t in tags.split(",") if t.strip()]

    def _chunk_text(self, text: str, chunk_words: int = 200, overlap: int = 50) -> List[str]:
        """Chunk text with overlap for better semantic continuity."""
        if not text:
            return []
        words = re.findall(r"\S+", text)
        chunks = []
        i = 0
        while i < len(words):
            chunk = words[i:i + chunk_words]
            chunks.append(" ".join(chunk))
            i += chunk_words - overlap
        return chunks

    def add_source(self, title: str, url: str, transcript: str = "", tags: str = "", 
                   source_type: str = "generic", analysis: Dict = None, metadata: Dict = None) -> Dict:
        doc = {
            "title": title,
            "url": url,
            "source_type": source_type,
            "transcript": transcript,
            "tags": self.normalize_tags(tags),
            "concepts": self._extract_concepts(title + " " + transcript + " " + tags),
            "analysis": analysis or {},
            "metadata": metadata or {},
            "chunk_count": 0,
            "created_at": datetime.utcnow().isoformat()
        }
        source = db.insert("kb_sources", doc)
        if transcript:
            chunks = self._chunk_text(transcript, 200, 50)
            for idx, chunk_text in enumerate(chunks):
                vector_store.add_chunk(source_id=source["id"], text=chunk_text, chunk_index=idx)
            source["chunk_count"] = len(chunks)
            db.update("kb_sources", source["id"], {"chunk_count": len(chunks)})
        return source

    def _extract_concepts(self, text: str) -> List[str]:
        lower = text.lower()
        concepts = set()
        for concept, terms in self.KEYWORDS_MAP.items():
            for term in terms:
                if term in lower:
                    concepts.add(concept)
                    break
        return sorted(concepts)

    def list_sources(self) -> List[Dict]:
        return db.get_collection("kb_sources")[::-1]

    def find_source(self, source_id: str) -> Dict:
        return next((item for item in db.get_collection("kb_sources") if item.get("id") == source_id), {})

    def remove_source(self, source_id: str) -> Dict:
        collection = db.get_collection("kb_sources")
        index = next((i for i, item in enumerate(collection) if item.get("id") == source_id), -1)
        if index >= 0:
            removed = collection.pop(index)
            db.get_collection("kb_chunks")[:] = [chunk for chunk in db.get_collection("kb_chunks") if chunk.get("source_id") != source_id]
            return removed
        return {}

    def search(self, query: str) -> List[Dict]:
        lower = query.lower()
        results = []
        for source in db.get_collection("kb_sources"):
            haystack = " ".join([
                source.get("title", ""), source.get("url", ""), 
                source.get("transcript", ""), " ".join(source.get("tags", [])),
                source.get("analysis", {}).get("summary", ""),
                source.get("analysis", {}).get("trading_insights", ""),
            ]).lower()
            if lower in haystack:
                results.append(source)
        return results

    def search_vectors(self, query: str, top_k: int = 5) -> List[Dict]:
        hits = vector_store.search(query, top_k=top_k)
        results = []
        for hit in hits:
            chunk = hit.get("chunk", {})
            source = self.find_source(chunk.get("source_id", ""))
            results.append({
                "score": hit.get("score", 0),
                "chunk_text": chunk.get("chunk_text", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "source_id": chunk.get("source_id", ""),
                "source_title": source.get("title", ""),
                "source_url": source.get("url", ""),
                "source_type": source.get("source_type", ""),
            })
        return results

    def auto_transcribe(self, url: str, tags: str = "", use_ai_analysis: bool = True, 
                        use_whisper: bool = True) -> Dict:
        """
        Auto-transcribe a YouTube video or playlist with optional AI analysis.
        
        Args:
            url: YouTube video, playlist, or channel URL
            tags: Comma-separated tags to apply
            use_ai_analysis: Whether to run LLM analysis (requires Ollama/OpenAI)
            use_whisper: Whether to use whisper audio fallback when captions are disabled
        """
        if not url:
            raise ValueError("URL is required")

        # Determine URL type
        playlist_id = youtube_service.extract_playlist_id(url)
        channel_handle = youtube_service.extract_channel_handle(url)
        video_id = youtube_service.extract_video_id(url)

        items = []
        is_channel = False
        
        if channel_handle:
            items = youtube_service.fetch_channel_videos(url, max_videos=20)
            is_channel = True
        elif playlist_id:
            items = youtube_service.fetch_playlist_items(url)
        else:
            if not video_id:
                raise ValueError("Unsupported YouTube URL. Must be a video, playlist, or channel URL.")
            meta = youtube_service.fetch_video_metadata(url)
            items = [{"id": video_id, "url": url, "title": meta.title if meta else "Unknown"}]

        if not items:
            raise RuntimeError("No videos found")

        created = []
        failed = []
        analyses = []

        for item in items:
            transcript = ""
            analysis = None
            metadata = None
            try:
                # Fetch metadata
                metadata = youtube_service.fetch_video_metadata(item["url"])
                
                # Fetch transcript
                transcript_result = youtube_service.fetch_video_transcript(item["id"])
                transcript = transcript_result.text
                
                # Generate analysis (heuristic always, AI optionally)
                base_analysis = youtube_service.analyze_transcript(transcript_result, metadata)
                analysis = {
                    "summary": base_analysis.summary,
                    "key_concepts": base_analysis.key_concepts,
                    "timestamps": [t for t in base_analysis.timestamps],
                    "ict_relevance": base_analysis.ict_relevance,
                    "trading_insights": base_analysis.trading_insights,
                    "sentiment": base_analysis.sentiment,
                    "word_count": base_analysis.word_count,
                    "transcript_source": transcript_result.source,
                }
                
                # Try AI-enhanced analysis if enabled
                if use_ai_analysis:
                    try:
                        import asyncio
                        # Create new event loop for this thread
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        ai_analysis = loop.run_until_complete(
                            video_analysis_agent.analyze_video(transcript_result, metadata)
                        )
                        loop.close()
                        # Merge AI analysis into base
                        analysis.update(ai_analysis)
                        analysis["ai_enhanced"] = True
                    except Exception as ai_err:
                        analysis["ai_enhanced"] = False
                        analysis["ai_error"] = str(ai_err)

                # Auto-generate tags from concepts
                auto_tags = ",".join(base_analysis.key_concepts) if base_analysis.key_concepts else ""
                all_tags = tags + ("," + auto_tags if auto_tags and tags else auto_tags)

                source = self.add_source(
                    title=item.get("title") or item.get("url"),
                    url=item.get("url"),
                    transcript=transcript,
                    tags=all_tags,
                    source_type="youtube",
                    analysis=analysis,
                    metadata={
                        "video_id": item["id"],
                        "channel": metadata.channel if metadata else "",
                        "duration": metadata.duration if metadata else 0,
                        "view_count": metadata.view_count if metadata else 0,
                        "upload_date": metadata.upload_date if metadata else "",
                    }
                )
                created.append({
                    "id": source.get("id"),
                    "title": source.get("title"),
                    "url": source.get("url"),
                    "transcript_added": bool(transcript),
                    "analysis": analysis,
                })
                analyses.append(analysis)
            except Exception as exc:
                failed.append({"url": item.get("url"), "title": item.get("title"), "error": str(exc)})

        # If channel, generate aggregate analysis
        channel_analysis = None
        if is_channel and analyses:
            all_concepts = {}
            sentiments = {"bullish": 0, "bearish": 0, "neutral": 0}
            total_words = 0
            for a in analyses:
                for c in a.get("key_concepts", []):
                    all_concepts[c] = all_concepts.get(c, 0) + 1
                sentiments[a.get("sentiment", "neutral")] += 1
                total_words += a.get("word_count", 0)
            
            channel_analysis = {
                "videos_analyzed": len(created),
                "total_words": total_words,
                "top_concepts": sorted(all_concepts.items(), key=lambda x: x[1], reverse=True),
                "sentiment_distribution": sentiments,
                "dominant_sentiment": max(sentiments, key=sentiments.get),
            }

        return {
            "created": created,
            "failed": failed,
            "source_count": len(created),
            "channel_analysis": channel_analysis,
            "url_type": "channel" if is_channel else "playlist" if playlist_id else "video",
        }

    def recommend(self, query: str) -> Dict:
        matched = self.search(query)
        concept_counts = {}
        for source in matched:
            for concept in source.get("concepts", []):
                concept_counts[concept] = concept_counts.get(concept, 0) + 1
        return {
            "query": query,
            "matches": matched,
            "top_concepts": sorted(concept_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        }

    def support_for_confluences(self, confluences: List[str]) -> List[Dict]:
        sources = []
        for source in db.get_collection("kb_sources"):
            text = " ".join([
                source.get("title", ""), source.get("transcript", ""), 
                " ".join(source.get("tags", [])),
                source.get("analysis", {}).get("summary", ""),
            ]).lower()
            for term in confluences:
                if term.lower().replace("_", " ") in text:
                    sources.append(source)
                    break
        return sources

    def status(self) -> Dict:
        sources = db.get_collection("kb_sources")
        chunks = db.get_collection("kb_chunks")
        youtube_sources = [s for s in sources if s.get("source_type") == "youtube"]
        return {
            "source_count": len(sources),
            "chunk_count": len(chunks),
            "youtube_source_count": len(youtube_sources),
            "transcript_enabled": youtube_service is not None,
            "search_enabled": True,
            "vector_search_enabled": True,
            "ai_analysis_enabled": True,
            "last_source": sources[-1] if sources else None,
        }

    def chat_answer(self, query: str, use_vectors: bool = True, top_k: int = 5) -> Dict[str, Any]:
        """
        Generate a RAG-based answer from the knowledge base.
        Uses vector search to find relevant chunks, then builds a prompt.
        """
        # Retrieve relevant chunks
        if use_vectors:
            hits = vector_store.search(query, top_k=top_k)
        else:
            # Fallback to simple text search
            hits = []
            for source in self.search(query):
                hits.append({
                    "chunk": {"chunk_text": source.get("transcript", "")[:800], "source_id": source.get("id")},
                    "score": 1.0,
                })

        if not hits:
            return {
                "answer": "I don't have any relevant sources in the knowledge base to answer this question. Try adding some YouTube videos or transcripts first!",
                "sources": [],
                "context_chunks": 0,
            }

        # Build context
        context_parts = []
        sources = []
        for i, hit in enumerate(hits, 1):
            chunk = hit.get("chunk", {})
            source = self.find_source(chunk.get("source_id", ""))
            context_parts.append(
                f"[{i}] {source.get('title', 'Unknown')} ({source.get('source_type', 'unknown')}):\n"
                f"{chunk.get('chunk_text', '')}"
            )
            sources.append({
                "id": source.get("id"),
                "title": source.get("title"),
                "url": source.get("url"),
                "score": hit.get("score", 0),
            })

        context_text = "\n\n".join(context_parts)

        # Build prompt for simple answer (without LLM dependency for basic operation)
        # For production, this should call an LLM. Here we provide a structured retrieval.
        answer = f"""Based on the knowledge base sources, here is what I found:

{context_text}

---

Your question: {query}

I found {len(hits)} relevant passages. The top sources are:
"""
        for s in sources[:3]:
            answer += f"\n- [{s['title']}]({s['url']}) (relevance: {s['score']:.3f})"

        # Try to add a simple synthesized answer using keyword extraction
        answer += "\n\nKey points from the sources:\n"
        for i, hit in enumerate(hits[:3], 1):
            chunk_text = hit.get("chunk", {}).get("chunk_text", "")
            # Extract first sentence or first 200 chars
            first_sentence = chunk_text.split(".")[0] if "." in chunk_text else chunk_text[:200]
            answer += f"\n{i}. {first_sentence}..."

        return {
            "answer": answer,
            "sources": sources,
            "context_chunks": len(hits),
            "query": query,
        }


kb_service = KBService()
