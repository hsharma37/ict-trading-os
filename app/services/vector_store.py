"""
Vector Store — Semantic search with sentence-transformer embeddings.

Upgrades from simple TF-IDF to real dense embeddings using sentence-transformers.
Falls back to TF-IDF if sentence-transformers is not installed.
"""
import math
import re
from typing import Dict, List, Any
from app.core.database import db

STOPWORDS = {
    'the', 'and', 'for', 'with', 'that', 'this', 'from', 'your', 'into', 'over', 'each', 'more', 'have',
    'not', 'will', 'their', 'they', 'them', 'into', 'then', 'than', 'also', 'about', 'what', 'when',
    'where', 'which', 'while', 'there', 'here', 'you', 'are', 'can', 'all', 'any', 'but', 'its', "it's",
    'is', 'was', 'were', 'been', 'be', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'done',
    'a', 'an', 'to', 'of', 'in', 'on', 'at', 'by', 'as', 'or', 'if', 'so', 'no', 'yes', 'up', 'out',
    'down', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when',
    'where', 'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'only',
    'own', 'same', 'so', 'than', 'too', 'very', 'just', 'now', 'also', 'back', 'after', 'use', 'two',
    'way', 'even', 'new', 'want', 'because', 'any', 'these', 'give', 'day', 'most', 'us', 'get', 'go',
    'know', 'take', 'person', 'see', 'make', 'come', 'could', 'say', 'would', 'may', 'should', 'must',
    'might', 'shall', 'will', 'need', 'let', 'put', 'try', 'keep', 'help', 'show', 'play', 'run', 'move',
    'live', 'believe', 'hold', 'bring', 'happen', 'write', 'provide', 'sit', 'stand', 'lose', 'pay',
    'meet', 'include', 'continue', 'set', 'learn', 'change', 'lead', 'understand', 'watch', 'follow',
    'stop', 'create', 'speak', 'read', 'spend', 'grow', 'open', 'walk', 'offer', 'remember', 'love',
    'consider', 'appear', 'buy', 'wait', 'serve', 'die', 'send', 'expect', 'build', 'stay', 'fall',
    'cut', 'reach', 'kill', 'remain', 'suggest', 'raise', 'pass', 'sell', 'require', 'report', 'decide',
    'pull', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
    'did', 'will', 'would', 'shall', 'should', 'may', 'might', 'must', 'can', 'could', 'need', 'dare',
    'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
    'during', 'before', 'after', 'above', 'below', 'between', 'under', 'again', 'further', 'then', 'once',
    'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other',
    'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
    'and', 'but', 'if', 'or', 'because', 'until', 'while', 'although', 'though', 'unless', 'whether',
    'however', 'therefore', 'thus', 'hence', 'consequently', 'meanwhile', 'otherwise', 'nevertheless',
    'nonetheless', 'furthermore', 'moreover', 'besides', 'additionally', 'alternatively', 'accordingly',
}

# Try to import sentence-transformers for real embeddings
_EMBEDDING_MODEL = None
try:
    from sentence_transformers import SentenceTransformer
    _EMBEDDING_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    print("[VectorStore] Loaded sentence-transformers embedding model")
except ImportError:
    print("[VectorStore] sentence-transformers not installed, using TF-IDF fallback")
    _EMBEDDING_MODEL = None


class SimpleVectorStore:
    """
    Hybrid vector store using sentence-transformer embeddings when available,
    falling back to TF-IDF cosine similarity.
    """

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

    def _embedding_similarity(self, emb_a: List[float], emb_b: List[float]) -> float:
        """Cosine similarity between two dense embeddings."""
        if not emb_a or not emb_b or len(emb_a) != len(emb_b):
            return 0.0
        dot = sum(a * b for a, b in zip(emb_a, emb_b))
        norm_a = math.sqrt(sum(v * v for v in emb_a))
        norm_b = math.sqrt(sum(v * v for v in emb_b))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    def _embed_text(self, text: str) -> List[float]:
        """Generate dense embedding using sentence-transformers."""
        if _EMBEDDING_MODEL is None:
            return []
        try:
            return _EMBEDDING_MODEL.encode(text, convert_to_numpy=True).tolist()
        except Exception as e:
            print(f"[VectorStore] Embedding failed: {e}")
            return []

    def add_chunk(self, source_id: str, text: str, chunk_index: int = 0) -> Dict:
        tokens = self._normalize(text)
        vector = self._vectorize(tokens)
        embedding = self._embed_text(text) if _EMBEDDING_MODEL else []

        chunk_doc = {
            "source_id": source_id,
            "chunk_index": chunk_index,
            "chunk_text": text,
            "vector": vector,
            "embedding": embedding,
            "tokens": tokens,
        }
        doc = db.insert("kb_chunks", chunk_doc)
        return doc

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search chunks using embeddings if available, else TF-IDF."""
        if _EMBEDDING_MODEL:
            return self._search_embeddings(query, top_k)
        return self._search_tfidf(query, top_k)

    def _search_embeddings(self, query: str, top_k: int) -> List[Dict]:
        query_emb = self._embed_text(query)
        if not query_emb:
            return self._search_tfidf(query, top_k)

        scores = []
        for chunk in db.get_collection("kb_chunks"):
            chunk_emb = chunk.get("embedding", [])
            if chunk_emb and len(chunk_emb) == len(query_emb):
                score = self._embedding_similarity(query_emb, chunk_emb)
                if score > 0.3:  # Embedding threshold
                    scores.append({"chunk": chunk, "score": score})

        scores.sort(key=lambda hit: hit["score"], reverse=True)
        return scores[:top_k]

    def _search_tfidf(self, query: str, top_k: int) -> List[Dict]:
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
