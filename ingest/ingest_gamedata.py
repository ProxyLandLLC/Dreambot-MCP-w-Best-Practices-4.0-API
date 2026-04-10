"""
Game data ingestion pipeline.
Sources: osrs-db items.g.json, osrs-db npcs.g.json
Target: game_data ChromaDB collection
"""

import json
import os
import sys

import requests
from tqdm import tqdm

from rag.store import ChromaStore, get_cache_path
from ingest.chunkers.gamedata_chunker import chunk_items, chunk_npcs

BATCH_SIZE = 500

OSRSDB_ITEMS_URL = "https://raw.githubusercontent.com/osrs-data/osrs-db/main/items.g.json"
OSRSDB_NPCS_URL = "https://raw.githubusercontent.com/osrs-data/osrs-db/main/npcs.g.json"


def _download_if_missing(url: str, cache_path: str, force: bool = False) -> str:
    """Download a file if not cached. Returns the local path."""
    if os.path.exists(cache_path) and not force:
        print(f"  Using cached: {cache_path}")
        return cache_path

    print(f"  Downloading: {url}")
    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        with open(cache_path, "wb") as f:
            f.write(resp.content)
        print(f"  Saved to: {cache_path}")
    except requests.RequestException as e:
        print(f"  WARNING: Failed to download {url}: {e}")
        if os.path.exists(cache_path):
            print(f"  Using stale cache: {cache_path}")
        else:
            raise
    return cache_path


def ingest_gamedata(store: ChromaStore, reset: bool = False) -> dict:
    """
    Ingest game data (items + NPCs) into the game_data collection.
    Downloads from osrs-db on first run.
    Returns stats dict.
    """
    osrsdb_cache = os.path.join(get_cache_path(), "osrs-db")
    os.makedirs(osrsdb_cache, exist_ok=True)

    if reset:
        try:
            store.reset_collection("game_data")
        except Exception:
            pass

    # Download data
    print("Fetching game data sources...")
    items_path = _download_if_missing(
        OSRSDB_ITEMS_URL,
        os.path.join(osrsdb_cache, "items.g.json"),
        force=reset,
    )
    npcs_path = _download_if_missing(
        OSRSDB_NPCS_URL,
        os.path.join(osrsdb_cache, "npcs.g.json"),
        force=reset,
    )

    # Chunk items
    print("Chunking items...")
    with open(items_path, encoding="utf-8") as f:
        items_data = json.load(f)
    item_chunks = chunk_items(items_data)
    print(f"  Items: {len(item_chunks)} chunks")

    # Chunk NPCs
    print("Chunking NPCs...")
    with open(npcs_path, encoding="utf-8") as f:
        npcs_data = json.load(f)
    npc_chunks = chunk_npcs(npcs_data)
    print(f"  NPCs: {len(npc_chunks)} chunks")

    all_chunks = item_chunks + npc_chunks
    print(f"  Total game_data: {len(all_chunks)} chunks")

    # Upsert — this is the big one (~20K chunks)
    print("\nEmbedding and upserting to ChromaDB (this may take several minutes)...")
    for i in tqdm(range(0, len(all_chunks), BATCH_SIZE), desc="game_data"):
        batch = all_chunks[i:i + BATCH_SIZE]
        store.upsert_batch(
            collection="game_data",
            ids=[c["id"] for c in batch],
            documents=[c["document"] for c in batch],
            metadatas=[c["metadata"] for c in batch],
        )

    final_count = store.collection_count("game_data")
    print(f"  game_data collection: {final_count} documents")

    return {
        "item_chunks": len(item_chunks),
        "npc_chunks": len(npc_chunks),
        "total": final_count,
    }


if __name__ == "__main__":
    store = ChromaStore()
    stats = ingest_gamedata(store, reset="--reset" in sys.argv)
    print(f"\nDone. {stats['total']} chunks in game_data.")
