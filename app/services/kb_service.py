import re
from typing import Dict, List, Optional
from datetime import datetime
from app.core.database import db
from app.services.vector_store import vector_store
from app.services.youtube_service import youtube_service

class KBService:
    KEYWORDS_MAP = {
        "MSS": ["market structure shift", "mss", "bos", "break of structure"],
        "FVG": ["fair value gap", "fvg", "imbalances", "inefficiency"],
        "OB": ["order block", "orderblock", "order block", "ob"],
        "liquidity": ["liquidity", "stop run", "liquidity sweep", "liquidity pool"],
        "session": ["london open", "new york", "asian session", "session"],
        "bias": ["bullish", "bearish", "neutral", "bias"],
        "trade_management": ["risk management", "lot sizing", "position sizing", "money management"]
    }

    def normalize_tags(self, tags: Optional[str]) -> List[str]:
        if not tags:
            return []
        return [t.strip().lower() for t in tags.split(",") if t.strip()]

    def _chunk_text(self, text: str, chunk_words: int = 120) -> List[str]:
        if not text:
            return []
        words = re.findall(r"\S+", text)
        return [" ".join(words[i:i+chunk_words]) for i in range(0, len(words), chunk_words)]

    def add_source(self, title: str, url: str, transcript: str = "", tags: str = "", source_type: str = "generic") -> Dict:
        doc = {
            "title": title,
            "url": url,
            "source_type": source_type,
            "transcript": transcript,
            "tags": self.normalize_tags(tags),
            "concepts": self._extract_concepts(title + " " + transcript + " " + tags),
            "chunk_count": 0,
            "created_at": datetime.utcnow().isoformat()
        }
        source = db.insert("kb_sources", doc)
        if transcript:
            chunks = self._chunk_text(transcript, 120)
            for chunk_text in chunks:
                vector_store.add_chunk(source_id=source["id"], text=chunk_text)
            source["chunk_count"] = len(chunks)
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
                source.get("title", ""), source.get("url", ""), source.get("transcript", ""), " ".join(source.get("tags", []))
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
                "source_id": chunk.get("source_id", ""),
                "source_title": source.get("title", ""),
                "source_url": source.get("url", ""),
            })
        return results

    def auto_transcribe(self, url: str, tags: str = "") -> Dict:
        if not url:
            raise ValueError("URL is required")

        playlist_id = youtube_service.extract_playlist_id(url)
        items = []
        if playlist_id:
            items = youtube_service.fetch_playlist_items(url)
            if not items:
                raise RuntimeError("No videos found in playlist")
        else:
            video_id = youtube_service.extract_video_id(url)
            if not video_id:
                raise ValueError("Unsupported YouTube URL")
            title = youtube_service.fetch_video_title(url)
            items = [{"id": video_id, "url": url, "title": title}]

        created = []
        failed = []
        for item in items:
            transcript = ""
            try:
                transcript = youtube_service.fetch_video_transcript(item["id"])
            except Exception as exc:
                failed.append({"url": item.get("url"), "title": item.get("title"), "error": str(exc)})

            source = self.add_source(
                title=item.get("title") or item.get("url"),
                url=item.get("url"),
                transcript=transcript,
                tags=tags,
                source_type="youtube"
            )
            created.append({
                "id": source.get("id"),
                "title": source.get("title"),
                "url": source.get("url"),
                "transcript_added": bool(transcript)
            })

        return {"created": created, "failed": failed, "source_count": len(created)}

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
            text = " ".join([source.get("title", ""), source.get("transcript", ""), " ".join(source.get("tags", []))]).lower()
            for term in confluences:
                if term.lower().replace("_", " ") in text:
                    sources.append(source)
                    break
        return sources

    def status(self) -> Dict:
        sources = db.get_collection("kb_sources")
        chunks = db.get_collection("kb_chunks")
        return {
            "source_count": len(sources),
            "chunk_count": len(chunks),
            "transcript_enabled": youtube_service is not None,
            "search_enabled": True,
            "vector_search_enabled": True,
            "last_source": sources[-1] if sources else None,
        }

kb_service = KBService()
