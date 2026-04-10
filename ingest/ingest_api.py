"""
API documentation ingestion pipeline.
Source: API v4/json files/index.json + API v4/markdown files/*.md
Target: api_methods ChromaDB collection
"""

import os
import sys

from tqdm import tqdm

from rag.store import ChromaStore
from ingest.chunkers.api_chunker import chunk_api_docs

BATCH_SIZE = 500


def _find_api_v4_dir() -> str:
    """Locate the API v4 folder relative to the MCP server root."""
    # Walk up from this file to find the server root
    here = os.path.dirname(os.path.abspath(__file__))
    server_root = os.path.dirname(here)
    api_dir = os.path.join(server_root, "API v4")
    if not os.path.isdir(api_dir):
        raise FileNotFoundError(
            f"API v4 folder not found at {api_dir}. "
            "Place the 'API v4' folder in the MCP server root."
        )
    return api_dir


def ingest_api(store: ChromaStore, reset: bool = False) -> dict:
    """
    Ingest API v4 docs into the api_methods collection.
    Returns stats dict with chunk counts.
    """
    api_dir = _find_api_v4_dir()

    if reset:
        try:
            store.reset_collection("api_methods")
        except Exception:
            pass  # Collection may not exist yet

    print("Chunking API v4 documentation...")
    method_chunks, class_chunks = chunk_api_docs(api_dir)
    all_chunks = method_chunks + class_chunks

    print(f"  Methods: {len(method_chunks)} chunks")
    print(f"  Classes: {len(class_chunks)} chunks")
    print(f"  Total:   {len(all_chunks)} chunks")

    print("Embedding and upserting to ChromaDB...")
    for i in tqdm(range(0, len(all_chunks), BATCH_SIZE), desc="api_methods"):
        batch = all_chunks[i:i + BATCH_SIZE]
        store.upsert_batch(
            collection="api_methods",
            ids=[c["id"] for c in batch],
            documents=[c["document"] for c in batch],
            metadatas=[c["metadata"] for c in batch],
        )

    final_count = store.collection_count("api_methods")
    print(f"  api_methods collection: {final_count} documents")

    return {
        "method_chunks": len(method_chunks),
        "class_chunks": len(class_chunks),
        "total": final_count,
    }


if __name__ == "__main__":
    store = ChromaStore()
    stats = ingest_api(store, reset="--reset" in sys.argv)
    print(f"\nDone. {stats['total']} chunks in api_methods.")
