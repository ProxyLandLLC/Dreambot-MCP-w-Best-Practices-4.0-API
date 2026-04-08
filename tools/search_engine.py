"""
Hybrid search over the DreamBot method index.
Exact keyword token match first; semantic cosine fallback when no tokens match.
"""
import os
import re

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_MCP_ROOT = os.path.dirname(_HERE)
EMBEDDINGS_FILE = os.path.join(_MCP_ROOT, "index", "embeddings.npy")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

try:
    from sentence_transformers import SentenceTransformer
    _EMBEDDINGS_AVAILABLE = True
except ImportError:
    _EMBEDDINGS_AVAILABLE = False


class SearchEngine:
    def __init__(self, methods: list[dict]):
        self.methods = methods
        self._model = None
        self._embeddings: np.ndarray | None = None
        self._keyword_index: dict[str, list[int]] = {}
        self._build_keyword_index()

    def _build_keyword_index(self):
        for i, method in enumerate(self.methods):
            tokens = _tokenize(method["class_name"] + " " + method["method_signature"])
            for token in tokens:
                self._keyword_index.setdefault(token, []).append(i)

    def search(self, query: str, top_k: int = 8) -> list[dict]:
        """Hybrid search: exact keyword match first, semantic fallback."""
        scores: dict[int, int] = {}
        for token in _tokenize(query):
            for idx in self._keyword_index.get(token, []):
                scores[idx] = scores.get(idx, 0) + 1

        if scores:
            ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
            return [self.methods[idx] for idx, _ in ranked]

        return self._semantic_search(query, top_k=top_k)

    def _semantic_search(self, query: str, top_k: int = 8) -> list[dict]:
        """Cosine similarity search using sentence-transformer embeddings."""
        self._ensure_embeddings()
        if self._embeddings is None:
            return []

        model = self._get_model()
        query_vec = model.encode([query], convert_to_numpy=True)[0]

        norms = np.linalg.norm(self._embeddings, axis=1, keepdims=True) + 1e-8
        normalized = self._embeddings / norms
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)
        sims = normalized @ query_norm

        top_indices = np.argsort(sims)[::-1][:top_k]
        return [self.methods[int(i)] for i in top_indices]

    def _ensure_embeddings(self):
        if self._embeddings is not None:
            return
        if os.path.exists(EMBEDDINGS_FILE):
            self._embeddings = np.load(EMBEDDINGS_FILE)
            return
        if not _EMBEDDINGS_AVAILABLE:
            return
        model = self._get_model()
        texts = [m["full_text"] for m in self.methods]
        self._embeddings = model.encode(
            texts, convert_to_numpy=True, show_progress_bar=False
        )
        os.makedirs(os.path.dirname(EMBEDDINGS_FILE), exist_ok=True)
        np.save(EMBEDDINGS_FILE, self._embeddings)

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(EMBEDDING_MODEL)
        return self._model


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z0-9]*", text)]
