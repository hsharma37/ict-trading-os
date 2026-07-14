"""
Knowledge Base Service — Ingestion, analysis, and retrieval with AI-powered chat.

Uses modern YouTube transcription (yt-dlp + youtube-transcript-api + whisper fallback),
agent-based video analysis, and sentence-transformer embeddings for semantic search.
"""
import hashlib
import re
import threading
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from app.core.database import db
from app.services.vector_store import vector_store
from app.services.youtube_service import youtube_service, VideoAnalysis
from app.services.video_analysis_agent import video_analysis_agent


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
    EXECUTION_TERMS = {
        "buy", "sell", "long", "short", "entry", "enter", "execute", "trade now",
        "stop loss", "take profit", "target", "lot", "position size", "risk",
    }

    def normalize_tags(self, tags: Optional[str]) -> List[str]:
        if not tags:
            return []
        return [t.strip().lower() for t in tags.split(",") if t.strip()]

    def _content_hash(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text or "").strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _query_terms(self, text: str) -> set[str]:
        terms = set(re.findall(r"\b[a-z][a-z0-9_]{2,}\b", (text or "").lower()))
        return {term for term in terms if term not in {"what", "when", "where", "which", "should", "would", "could", "about"}}

    def _is_execution_sensitive(self, query: str) -> bool:
        lower = (query or "").lower()
        return any(term in lower for term in self.EXECUTION_TERMS)

    # Terms that mean the user is asking about their OWN live account/trades,
    # which the knowledge base can't answer but the MT5 terminal can.
    ACCOUNT_TERMS = (
        "my position", "my positions", "my trade", "my trades", "open position",
        "open positions", "open trade", "open trades", "my account", "my balance",
        "my equity", "my pnl", "my p&l", "my profit", "my loss", "my drawdown",
        "my win rate", "current position", "current trade", "am i in", "how am i doing",
        "how are my", "what am i holding", "what do i hold", "my performance",
        "floating", "unrealized", "my exposure", "portfolio",
    )

    def _is_account_query(self, query: str) -> bool:
        lower = (query or "").lower()
        return any(term in lower for term in self.ACCOUNT_TERMS)

    def _canonical_url(self, url: str, video_id: Optional[str] = None) -> str:
        if not url:
            return ""
        video_id = video_id or youtube_service.extract_video_id(url)
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"

        parsed = urlparse(url.strip())
        keep_params = {}
        for key, value in parse_qs(parsed.query).items():
            if key not in {"si", "feature", "t", "utm_source", "utm_medium", "utm_campaign"}:
                keep_params[key] = value[-1]
        return urlunparse((
            parsed.scheme or "https",
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            urlencode(keep_params),
            "",
        ))

    def _format_timestamp(self, seconds: Optional[float]) -> Optional[str]:
        if seconds is None:
            return None
        total = max(0, int(seconds))
        return f"{total // 60}:{total % 60:02d}"

    def _normalize_segments(self, text: str, segments: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        normalized = []
        for index, segment in enumerate(segments or []):
            segment_text = re.sub(r"\s+", " ", str(segment.get("text", ""))).strip()
            if not segment_text:
                continue
            start = segment.get("start")
            duration = segment.get("duration") or 0
            try:
                start_seconds = float(start) if start is not None else None
                end_seconds = start_seconds + float(duration or 0) if start_seconds is not None else None
            except (TypeError, ValueError):
                start_seconds = None
                end_seconds = None
            normalized.append({
                "index": index,
                "text": segment_text,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "timestamp": self._format_timestamp(start_seconds),
            })

        if normalized:
            return normalized

        words = re.findall(r"\S+", text or "")
        fallback = []
        for index in range(0, len(words), 120):
            fallback.append({
                "index": len(fallback),
                "text": " ".join(words[index:index + 120]),
                "start_seconds": None,
                "end_seconds": None,
                "timestamp": None,
            })
        return fallback

    def _chunk_segments(
        self,
        segments: List[Dict[str, Any]],
        target_tokens: int = 450,
        overlap_tokens: int = 64,
    ) -> List[Dict[str, Any]]:
        """Chunk normalized transcript segments into cited 350-512-ish token windows."""
        word_records = []
        for segment in segments:
            for word in re.findall(r"\S+", segment.get("text", "")):
                word_records.append({
                    "word": word,
                    "start_seconds": segment.get("start_seconds"),
                    "end_seconds": segment.get("end_seconds"),
                })
        if not word_records:
            return []

        chunks = []
        start = 0
        step = max(1, target_tokens - overlap_tokens)
        while start < len(word_records):
            window = word_records[start:start + target_tokens]
            text = " ".join(item["word"] for item in window)
            starts = [item["start_seconds"] for item in window if item.get("start_seconds") is not None]
            ends = [item["end_seconds"] for item in window if item.get("end_seconds") is not None]
            start_seconds = starts[0] if starts else None
            end_seconds = ends[-1] if ends else None
            timestamp = self._format_timestamp(start_seconds)
            end_timestamp = self._format_timestamp(end_seconds)
            chunks.append({
                "text": text,
                "token_count": len(window),
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "timestamp": timestamp,
                "end_timestamp": end_timestamp,
                "span": f"{timestamp or 'transcript'}-{end_timestamp}" if timestamp and end_timestamp else timestamp,
            })
            if start + target_tokens >= len(word_records):
                break
            start += step
        return chunks

    def _find_existing_source(self, canonical_url: str, video_id: Optional[str]) -> Dict:
        if canonical_url:
            matches = db.find("kb_sources", url=canonical_url)
            if matches:
                return matches[0]
            matches = db.find("kb_sources", canonical_url=canonical_url)
            if matches:
                return matches[0]
        if video_id:
            for source in db.get_collection("kb_sources"):
                metadata = source.get("metadata", {})
                if metadata.get("video_id") == video_id:
                    return source
        return {}

    def _build_analysis_artifacts(
        self,
        transcript: str,
        analysis: Optional[Dict[str, Any]],
        segments: List[Dict[str, Any]],
        transcript_source: str = "",
    ) -> Dict[str, Any]:
        analysis = analysis or {}
        concepts = sorted(set(self._extract_concepts(transcript) + [
            str(concept).strip() for concept in analysis.get("key_concepts", []) if str(concept).strip()
        ]))
        lower_concepts = {concept.lower() for concept in concepts}
        playbook_rules = []
        if {"fvg", "liquidity"} & lower_concepts:
            playbook_rules.append({
                "type": "setup",
                "rule": "Look for liquidity being taken before displacement into a fair value gap.",
                "evidence": ["liquidity", "FVG"],
            })
        if "ob" in lower_concepts:
            playbook_rules.append({
                "type": "trigger",
                "rule": "Use order block or mitigation reaction as confirmation, not as a standalone signal.",
                "evidence": ["OB"],
            })
        if {"risk management", "trade_management"} & lower_concepts or "risk" in (transcript or "").lower():
            playbook_rules.append({
                "type": "management",
                "rule": "Define invalidation before entry and manage exits from the cited setup context.",
                "evidence": ["risk"],
            })

        evidence_spans = []
        for item in analysis.get("timestamps", [])[:8]:
            evidence_spans.append({
                "timestamp": item.get("time") or item.get("timestamp"),
                "concept": item.get("concept"),
                "text": item.get("text", ""),
            })
        for segment in segments[:5]:
            evidence_spans.append({
                "timestamp": segment.get("timestamp"),
                "start_seconds": segment.get("start_seconds"),
                "end_seconds": segment.get("end_seconds"),
                "text": segment.get("text", "")[:220],
            })

        uncertainty = []
        if transcript_source in {"fallback", "whisper"}:
            uncertainty.append(f"Transcript source is {transcript_source}; verify exact wording before trading decisions.")
        if not evidence_spans:
            uncertainty.append("No timestamped evidence spans were available.")

        return {
            "concepts": concepts,
            "playbook_rules": playbook_rules,
            "uncertainty": uncertainty,
            "evidence_spans": evidence_spans,
        }

    def _delete_chunks_for_source(self, source_id: str) -> int:
        chunks = db.find("kb_chunks", source_id=source_id)
        deleted = 0
        for chunk in chunks:
            if db.delete("kb_chunks", chunk["id"]):
                deleted += 1
        return deleted

    def add_source(
        self,
        title: str,
        url: str,
        transcript: str = "",
        tags: str = "",
        source_type: str = "generic",
        analysis: Dict = None,
        metadata: Dict = None,
        transcript_segments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict:
        metadata = metadata or {}
        video_id = metadata.get("video_id") or youtube_service.extract_video_id(url)
        canonical_url = self._canonical_url(url, video_id)
        existing = self._find_existing_source(canonical_url, video_id)
        if existing:
            self._delete_chunks_for_source(existing["id"])

        normalized_segments = self._normalize_segments(transcript, transcript_segments)
        content_hash = self._content_hash(transcript)
        analysis_artifacts = self._build_analysis_artifacts(
            transcript,
            analysis,
            normalized_segments,
            (analysis or {}).get("transcript_source", ""),
        )
        now = utc_now_iso()
        doc = {
            "id": existing.get("id") if existing else None,
            "title": title,
            "url": canonical_url or url,
            "canonical_url": canonical_url or url,
            "original_url": url,
            "source_type": source_type,
            "transcript": transcript,
            "tags": self.normalize_tags(tags),
            "concepts": analysis_artifacts["concepts"] or self._extract_concepts(title + " " + transcript + " " + tags),
            "analysis": analysis or {},
            "analysis_artifacts": analysis_artifacts,
            "metadata": metadata or {},
            "transcript_segments": normalized_segments,
            "content_hash": content_hash,
            "chunk_count": 0,
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
        }

        if existing:
            source = db.update("kb_sources", existing["id"], {k: v for k, v in doc.items() if k != "id"})
        else:
            doc = {k: v for k, v in doc.items() if v is not None}
            source = db.insert("kb_sources", doc)

        if transcript:
            chunks = self._chunk_segments(normalized_segments)
            for idx, chunk in enumerate(chunks):
                chunk_concepts = self._extract_concepts(chunk["text"] + " " + " ".join(source.get("tags", [])))
                vector_store.add_chunk(
                    source_id=source["id"],
                    text=chunk["text"],
                    chunk_index=idx,
                    metadata={
                        "source_url": source.get("url"),
                        "source_title": source.get("title"),
                        "concept_tags": sorted(set(chunk_concepts + source.get("concepts", []))),
                        "content_hash": self._content_hash(chunk["text"]),
                        "source_content_hash": content_hash,
                        "token_count": chunk.get("token_count"),
                        "start_seconds": chunk.get("start_seconds"),
                        "end_seconds": chunk.get("end_seconds"),
                        "timestamp": chunk.get("timestamp"),
                        "span": chunk.get("span"),
                        "citation": {
                            "source_id": source["id"],
                            "url": source.get("url"),
                            "title": source.get("title"),
                            "timestamp": chunk.get("timestamp"),
                            "span": chunk.get("span"),
                        },
                    },
                )
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
        removed = db.find_one("kb_sources", source_id)
        if removed:
            self._delete_chunks_for_source(source_id)
            db.delete("kb_sources", source_id)
            removed["removed"] = True
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
                "timestamp": chunk.get("timestamp"),
                "span": chunk.get("span"),
                "citation": chunk.get("citation") or {
                    "source_id": source.get("id"),
                    "url": source.get("url", ""),
                    "title": source.get("title", ""),
                    "timestamp": chunk.get("timestamp"),
                    "span": chunk.get("span"),
                },
                "concept_tags": chunk.get("concept_tags") or source.get("concepts", []),
                "chunk_score": hit.get("score", 0),
                "match_reason": self._match_reason(query, chunk, source),
            })
        return results

    def _match_reason(self, query: str, chunk: Dict[str, Any], source: Dict[str, Any]) -> str:
        query_terms = self._query_terms(query)
        haystack_terms = self._query_terms(" ".join([
            chunk.get("chunk_text", ""),
            " ".join(chunk.get("concept_tags", [])),
            source.get("title", ""),
        ]))
        overlap = sorted(query_terms & haystack_terms)
        if overlap:
            return "matched terms: " + ", ".join(overlap[:6])
        if chunk.get("concept_tags"):
            return "matched nearby concept tags"
        return "matched embedding similarity"

    def _citation_from_hit(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        chunk = hit.get("chunk", {})
        source = self.find_source(chunk.get("source_id", ""))
        citation = chunk.get("citation") or {}
        return {
            "source_id": source.get("id") or chunk.get("source_id"),
            "title": citation.get("title") or source.get("title", ""),
            "url": citation.get("url") or source.get("url", ""),
            "timestamp": citation.get("timestamp") or chunk.get("timestamp"),
            "span": citation.get("span") or chunk.get("span"),
            "chunk_index": chunk.get("chunk_index", 0),
            "score": hit.get("score", 0),
            "concept_tags": chunk.get("concept_tags") or source.get("concepts", []),
        }

    def _hit_has_query_support(self, query: str, hit: Dict[str, Any]) -> bool:
        chunk = hit.get("chunk", {})
        source = self.find_source(chunk.get("source_id", ""))
        query_terms = self._query_terms(query)
        if not query_terms:
            return False
        supported_terms = self._query_terms(" ".join([
            chunk.get("chunk_text", ""),
            " ".join(chunk.get("concept_tags", [])),
            source.get("title", ""),
            source.get("analysis", {}).get("summary", ""),
        ]))
        return bool(query_terms & supported_terms)

    def _confidence_from_hits(self, hits: List[Dict[str, Any]], supported: bool) -> str:
        if not hits or not supported:
            return "low"
        top_score = max(float(hit.get("score", 0) or 0) for hit in hits)
        citation_count = sum(1 for hit in hits if self._citation_from_hit(hit).get("url"))
        if top_score >= 0.45 and citation_count >= 2:
            return "high"
        if top_score >= 0.12 and citation_count >= 1:
            return "medium"
        return "low"

    def enqueue_auto_transcribe(
        self,
        url: str,
        tags: str = "",
        use_ai_analysis: bool = True,
        use_whisper: bool = True,
    ) -> Dict:
        if not url:
            raise ValueError("URL is required")
        video_id = youtube_service.extract_video_id(url)
        canonical_url = self._canonical_url(url, video_id)
        now = utc_now_iso()
        job = db.insert("kb_ingestion_jobs", {
            "id": f"KBJ-{uuid.uuid4().hex[:12]}",
            "status": "QUEUED",
            "url": url,
            "canonical_url": canonical_url,
            "tags": tags,
            "use_ai_analysis": use_ai_analysis,
            "use_whisper": use_whisper,
            "progress": {"stage": "queued", "completed": 0, "total": 0},
            "result": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        })

        thread = threading.Thread(target=self._run_ingestion_job, args=(job["id"],), daemon=True)
        thread.start()
        return job

    def _run_ingestion_job(self, job_id: str) -> None:
        job = db.find_one("kb_ingestion_jobs", job_id)
        if not job:
            return
        db.update("kb_ingestion_jobs", job_id, {
            "status": "RUNNING",
            "progress": {"stage": "transcribing", "completed": 0, "total": 1},
            "started_at": utc_now_iso(),
        })
        try:
            result = self.auto_transcribe(
                url=job.get("url", ""),
                tags=job.get("tags", ""),
                use_ai_analysis=bool(job.get("use_ai_analysis", True)),
                use_whisper=bool(job.get("use_whisper", True)),
            )
            db.update("kb_ingestion_jobs", job_id, {
                "status": "SUCCEEDED",
                "progress": {
                    "stage": "complete",
                    "completed": result.get("source_count", 0),
                    "total": result.get("source_count", 0) + len(result.get("failed", [])),
                },
                "result": result,
                "error": None,
                "finished_at": utc_now_iso(),
            })
        except Exception as exc:
            db.update("kb_ingestion_jobs", job_id, {
                "status": "FAILED",
                "progress": {"stage": "failed", "completed": 0, "total": 1},
                "error": str(exc),
                "finished_at": utc_now_iso(),
            })

    def get_ingestion_job(self, job_id: str) -> Dict:
        return db.find_one("kb_ingestion_jobs", job_id)

    def list_ingestion_jobs(self, limit: int = 20) -> List[Dict]:
        return db.get_collection("kb_ingestion_jobs")[:limit]

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
                transcript_result = youtube_service.fetch_video_transcript(
                    item["id"],
                    allow_whisper=use_whisper,
                )
                transcript = transcript_result.text
                if not transcript.strip():
                    raise RuntimeError(
                        "No transcript text was available from captions"
                        + (" or whisper" if use_whisper else "")
                    )
                
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
                    },
                    transcript_segments=transcript_result.segments,
                )
                created.append({
                    "id": source.get("id"),
                    "title": source.get("title"),
                    "url": source.get("url"),
                    "transcript_added": bool(transcript),
                    "chunk_count": source.get("chunk_count", 0),
                    "source_type": source.get("source_type"),
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
            "chunk_count": sum(item.get("chunk_count", 0) for item in created),
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
        jobs = db.get_collection("kb_ingestion_jobs")
        youtube_sources = [s for s in sources if s.get("source_type") == "youtube"]
        concept_count = len({concept for source in sources for concept in source.get("concepts", [])})
        return {
            "source_count": len(sources),
            "chunk_count": len(chunks),
            "youtube_source_count": len(youtube_sources),
            "concept_count": concept_count,
            "ingestion_job_count": len(jobs),
            "latest_ingestion_job": jobs[0] if jobs else None,
            "transcript_enabled": youtube_service is not None,
            "search_enabled": True,
            "vector_search_enabled": True,
            "embedding": vector_store.embedding_info(),
            "ai_analysis_enabled": True,
            "last_source": sources[0] if sources else None,
        }

    def _answer_from_account(self, query: str, account_ctx: str, use_vectors: bool, top_k: int) -> Dict[str, Any]:
        """Answer an account/trades question from the live MT5 snapshot, with any
        relevant KB passages appended as (educational) coaching context."""
        kb_notes = ""
        sources: List[Dict[str, Any]] = []
        try:
            hits = vector_store.search(query, top_k=top_k) if use_vectors else []
        except Exception:
            hits = []
        supported = [h for h in hits if self._hit_has_query_support(query, h)]
        if supported:
            note_lines = []
            for i, hit in enumerate(supported[:3], 1):
                chunk = hit.get("chunk", {})
                source = self.find_source(chunk.get("source_id", ""))
                citation = self._citation_from_hit(hit)
                text = (chunk.get("chunk_text", "") or "").strip()
                snippet = text.split(".")[0][:200] if text else ""
                note_lines.append(f"[{i}] {source.get('title', 'Unknown')}: {snippet}...")
                sources.append({
                    "id": source.get("id"),
                    "title": source.get("title"),
                    "url": source.get("url"),
                    "score": hit.get("score", 0),
                    "timestamp": citation.get("timestamp"),
                    "span": citation.get("span"),
                })
            kb_notes = "\n".join(note_lines)

        answer = (
            f"{account_ctx}\n\n---\n\nYour question: {query}\n\n"
            "Answered from your live MT5 terminal (the figures above are your real "
            "broker account, not the knowledge base)."
        )
        if kb_notes:
            answer += f"\n\nRelevant notes from your knowledge base (educational context):\n{kb_notes}"

        return {
            "answer": answer,
            "sources": sources,
            "citations": [],
            "confidence": "high",
            "missing_context": [],
            "refused": False,
            "safety_disclaimer": (
                "Educational only. This reports your live account state; it is not "
                "advice to open, hold, or close any position."
            ),
            "context_chunks": len(sources),
            "query": query,
            "source": "mt5_account",
        }

    def chat_answer(self, query: str, use_vectors: bool = True, top_k: int = 5) -> Dict[str, Any]:
        """
        Generate a RAG-based answer from the knowledge base.
        Uses vector search to find relevant chunks, then builds a prompt.

        If the question is about the user's own live account/trades, answer it
        directly from the MT5 terminal (the knowledge base has no such data),
        and blend in any relevant KB context as coaching notes.
        """
        from app.services.mt5_trades_service import mt5_trades_service
        account_ctx = None
        if self._is_account_query(query) and mt5_trades_service.is_active():
            account_ctx = mt5_trades_service.get_context_block()
        if account_ctx:
            return self._answer_from_account(query, account_ctx, use_vectors, top_k)

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

        supported_hits = [hit for hit in hits if self._hit_has_query_support(query, hit)]
        supported = bool(supported_hits)
        execution_sensitive = self._is_execution_sensitive(query)
        citations = [self._citation_from_hit(hit) for hit in hits[:top_k]]
        confidence = self._confidence_from_hits(hits, supported)
        safety_disclaimer = (
            "Educational only. Do not treat retrieved notes as live trade instructions; validate bias, risk, invalidation, and execution context yourself."
            if execution_sensitive else ""
        )

        if not hits or not supported:
            missing_context = [
                "No retrieved chunk directly supports the question.",
                "Ingest or cite source material that covers this setup before using it for planning.",
            ]
            return {
                "answer": "I do not have enough cited knowledge-base context to answer that reliably.",
                "sources": [],
                "citations": citations,
                "confidence": "low",
                "missing_context": missing_context,
                "refused": True,
                "safety_disclaimer": safety_disclaimer,
                "context_chunks": len(hits),
                "query": query,
            }

        # Build context
        context_parts = []
        sources = []
        for i, hit in enumerate(hits, 1):
            chunk = hit.get("chunk", {})
            source = self.find_source(chunk.get("source_id", ""))
            citation = self._citation_from_hit(hit)
            context_parts.append(
                f"[{i}] {source.get('title', 'Unknown')} {citation.get('span') or citation.get('timestamp') or ''}:\n"
                f"{chunk.get('chunk_text', '')}"
            )
            sources.append({
                "id": source.get("id"),
                "title": source.get("title"),
                "url": source.get("url"),
                "score": hit.get("score", 0),
                "timestamp": citation.get("timestamp"),
                "span": citation.get("span"),
            })

        context_text = "\n\n".join(context_parts)

        # Build prompt for simple answer (without LLM dependency for basic operation)
        # For production, this should call an LLM. Here we provide a structured retrieval.
        answer = f"""Based on the cited knowledge-base passages, here is what I found:

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
        if safety_disclaimer:
            answer += f"\n\nSafety note: {safety_disclaimer}"

        missing_context = []
        if confidence != "high":
            missing_context.append("Retrieved evidence is useful but not exhaustive; add more source-backed examples for higher confidence.")
        if execution_sensitive:
            missing_context.append("Live market state, account risk, and current invalidation are outside the KB retrieval context.")

        return {
            "answer": answer,
            "sources": sources,
            "citations": citations,
            "confidence": confidence,
            "missing_context": missing_context,
            "refused": False,
            "safety_disclaimer": safety_disclaimer,
            "context_chunks": len(hits),
            "query": query,
        }


kb_service = KBService()
