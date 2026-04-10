"""
ChromaDB wrapper — connection management and clean query interface.

Persistent client at {DREAMBOT_MCP_DATA_DIR}/chromadb/.
No business logic, just collection access and query abstraction.
"""

import os
from pathlib import Path

import chromadb

from rag.embeddings import get_embedding_function, NomicEmbeddingFunction

COLLECTION_NAMES = ("api_methods", "spatial", "game_data")

_DEFAULT_DATA_DIR = os.path.join(Path.home(), ".dreambot-mcp")


def get_data_dir() -> str:
    return os.environ.get("DREAMBOT_MCP_DATA_DIR", _DEFAULT_DATA_DIR)


def get_chromadb_path() -> str:
    return os.path.join(get_data_dir(), "chromadb")


def get_cache_path() -> str:
    return os.path.join(get_data_dir(), "cache")


def sentinel_exists() -> bool:
    """Check if ingestion has been run (sentinel file exists)."""
    return os.path.exists(os.path.join(get_chromadb_path(), ".ingested"))


def write_sentinel():
    """Write the sentinel file after successful ingestion."""
    sentinel_path = os.path.join(get_chromadb_path(), ".ingested")
    os.makedirs(os.path.dirname(sentinel_path), exist_ok=True)
    Path(sentinel_path).touch()


class ChromaStore:
    """Thin wrapper over ChromaDB persistent client."""

    def __init__(self):
        self._client = chromadb.PersistentClient(path=get_chromadb_path())
        self._embed_fn = get_embedding_function()
        self._collections: dict[str, chromadb.Collection] = {}

    @property
    def embed_fn(self) -> NomicEmbeddingFunction:
        return self._embed_fn

    def get_collection(self, name: str) -> chromadb.Collection:
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                embedding_function=self._embed_fn,
            )
        return self._collections[name]

    def query(
        self,
        collection: str,
        query_text: str,
        where: dict | None = None,
        n_results: int = 8,
    ) -> list[tuple[str, dict, float]]:
        """
        Query a collection by text similarity with optional metadata filters.

        Returns list of (document, metadata, distance) tuples.
        Lower distance = more similar.
        """
        coll = self.get_collection(collection)

        # Use query prefix for the query embedding
        query_embedding = self._embed_fn.embed_query(query_text)

        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, coll.count()) if coll.count() > 0 else 1,
        }
        if where:
            kwargs["where"] = where

        if coll.count() == 0:
            return []

        results = coll.query(**kwargs)

        output = []
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metadatas, distances):
            output.append((doc, meta, dist))

        return output

    def get_by_ids(self, collection: str, ids: list[str]) -> list[tuple[str, dict]]:
        """Fetch specific documents by ID."""
        coll = self.get_collection(collection)
        results = coll.get(ids=ids)
        output = []
        for doc, meta in zip(results["documents"], results["metadatas"]):
            output.append((doc, meta))
        return output

    def upsert_batch(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
    ):
        """Upsert a batch of documents into a collection."""
        coll = self.get_collection(collection)
        coll.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def collection_count(self, collection: str) -> int:
        return self.get_collection(collection).count()

    def reset_collection(self, name: str):
        """Delete and recreate a collection."""
        self._client.delete_collection(name)
        self._collections.pop(name, None)

    def embed_dummy(self):
        """Warm up the embedding model."""
        self._embed_fn.embed_dummy()
