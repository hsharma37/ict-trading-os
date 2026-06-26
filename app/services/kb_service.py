from typing import Dict, List, Optional
from datetime import datetime
from app.core.database import db

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

    def add_source(self, title: str, url: str, transcript: str = "", tags: str = "", source_type: str = "generic") -> Dict:
        doc = {
            "title": title,
            "url": url,
            "source_type": source_type,
            "transcript": transcript,
            "tags": self.normalize_tags(tags),
            "concepts": self._extract_concepts(title + " " + transcript + " " + tags),
            "created_at": datetime.utcnow().isoformat()
        }
        return db.insert("kb_sources", doc)

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
            return collection.pop(index)
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

kb_service = KBService()
