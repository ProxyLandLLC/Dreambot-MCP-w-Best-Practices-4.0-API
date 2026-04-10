"""
ChromaDB-compatible embedding function wrapping nomic-embed-text-v1.5.

Single model instance, lazy-loaded. All collections share this function
so cross-collection similarity scores are comparable.
"""

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

MODEL_NAME = "nomic-embed-text-v1.5"
DIMENSIONS = 768


class NomicEmbeddingFunction(EmbeddingFunction[Documents]):
    """Wraps nomic-embed-text-v1.5 as a ChromaDB embedding function."""

    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                "nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True
            )
        return self._model

    def __call__(self, input: Documents) -> Embeddings:
        model = self._get_model()
        # nomic-embed-text-v1.5 expects "search_document: " or "search_query: " prefix
        # For ChromaDB storage, we use "search_document: " prefix
        prefixed = [f"search_document: {doc}" for doc in input]
        embeddings = model.encode(prefixed, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string with the query prefix."""
        model = self._get_model()
        prefixed = f"search_query: {text}"
        embedding = model.encode([prefixed], convert_to_numpy=True, show_progress_bar=False)
        return embedding[0].tolist()

    def embed_dummy(self):
        """Eager warm-up — loads the model into memory."""
        self.embed_query("warmup")


# Module-level singleton
_embedding_fn: NomicEmbeddingFunction | None = None


def get_embedding_function() -> NomicEmbeddingFunction:
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = NomicEmbeddingFunction()
    return _embedding_fn
