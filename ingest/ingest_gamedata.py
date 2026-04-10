"""
Game data ingestion pipeline.
Sources: osrs-db items.g.json, osrs-db npcs.g.json (via npm package)
Target: game_data ChromaDB collection
"""

import json
import os
import sys

from tqdm import tqdm

from rag.store import ChromaStore
from ingest.chunkers.gamedata_chunker import chunk_items, chunk_npcs
from ingest._osrsdb import ensure_osrsdb_cached

BATCH_SIZE = 500


def ingest_gamedata(store: ChromaStore, reset: bool = False) -> dict:
    """
    Ingest game data (items + NPCs) into the game_data collection.
    Downloads from osrs-db npm package on first run.
    Returns stats dict.
    """
    if reset:
        try:
            store.reset_collection("game_data")
        except Exception:
            pass

    # Get osrs-db data (shared npm download)
    print("Fetching game data sources...")
    osrsdb_cache = ensure_osrsdb_cached(force=reset)
    items_path = os.path.join(osrsdb_cache, "items.g.json")
    npcs_path = os.path.join(osrsdb_cache, "npcs.g.json")

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

    # Upsert — this is the big one
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
