import math
import re
from typing import Dict, List
from app.core.database import db

STOPWORDS = {
    'the', 'and', 'for', 'with', 'that', 'this', 'from', 'your', 'into', 'over', 'each', 'more', 'have',
    'not', 'will', 'their', 'they', 'them', 'into', 'then', 'than', 'also', 'about', 'what', 'when',
    'where', 'which', 'while', 'there', 'here', 'you', 'are', 'can', 'all', 'any', 'but', 'its', "it's"
}

class SimpleVectorStore:
    def _normalize(self, text: str) -> List[str]:
        tokens = re.findall(r"\b[a-z]{3,}\b", (text or "").lower())
        return [t for t in tokens if t not in STOPWORDS]

    def _vectorize(self, tokens: List[str]) -> Dict[str, int]:
        vec = {}
        for token in tokens:
            vec[token] = vec.get(token, 0) + 1
        return vec

    def _cosine_similarity(self, a: Dict[str, int], b: Dict[str, int]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(a.get(k, 0) * b.get(k, 0) for k in a)
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    def add_chunk(self, source_id: str, text: str) -> Dict:
        tokens = self._normalize(text)
        vector = self._vectorize(tokens)
        chunk_doc = {
            "source_id": source_id,
            "chunk_text": text,
            "vector": vector,
            "tokens": tokens,
        }
        doc = db.insert("kb_chunks", chunk_doc)
        return doc

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        tokens = self._normalize(query)
        if not tokens:
            return []
        q_vec = self._vectorize(tokens)
        scores = []
        for chunk in db.get_collection("kb_chunks"):
            score = self._cosine_similarity(q_vec, chunk.get("vector", {}))
            if score > 0:
                scores.append({"chunk": chunk, "score": score})
        scores.sort(key=lambda hit: hit["score"], reverse=True)
        return scores[:top_k]

    def get_chunks_for_source(self, source_id: str) -> List[Dict]:
        return [chunk for chunk in db.get_collection("kb_chunks") if chunk.get("source_id") == source_id]

vector_store = SimpleVectorStore()
