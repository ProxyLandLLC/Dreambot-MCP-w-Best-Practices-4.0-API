"""
Spatial data ingestion pipeline.
Sources: Explv map_labels.json, osrs-db NPC locations, osrs-db object locations
Target: spatial ChromaDB collection
"""

import json
import os
import sys

import requests
from tqdm import tqdm

from rag.store import ChromaStore, get_cache_path
from ingest.chunkers.spatial_chunker import (
    chunk_map_labels,
    chunk_npc_locations,
    chunk_object_locations,
)

BATCH_SIZE = 500

# Data source URLs
MAP_LABELS_URL = "https://raw.githubusercontent.com/Explv/osrs_map_full_2/master/map_labels.json"
# osrs-db URLs — these contain NPC and object location data
OSRSDB_NPCS_URL = "https://raw.githubusercontent.com/osrs-data/osrs-db/main/npcs.g.json"
OSRSDB_OBJECTS_URL = "https://raw.githubusercontent.com/osrs-data/osrs-db/main/objects.g.json"


def _ensure_cache_dir() -> str:
    cache_dir = os.path.join(get_cache_path(), "spatial")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _download_if_missing(url: str, cache_path: str, force: bool = False) -> str:
    """Download a file if not cached. Returns the local path."""
    if os.path.exists(cache_path) and not force:
        print(f"  Using cached: {cache_path}")
        return cache_path

    print(f"  Downloading: {url}")
    try:
        resp = requests.get(url, timeout=60)
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


def _load_json(path: str) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ingest_spatial(store: ChromaStore, reset: bool = False) -> dict:
    """
    Ingest spatial data into the spatial collection.
    Downloads source data on first run, caches locally.
    Returns stats dict.
    """
    cache_dir = _ensure_cache_dir()

    if reset:
        try:
            store.reset_collection("spatial")
        except Exception:
            pass

    # Download data sources
    print("Fetching spatial data sources...")
    labels_path = _download_if_missing(
        MAP_LABELS_URL,
        os.path.join(cache_dir, "map_labels.json"),
        force=reset,
    )

    # NPC data is shared with gamedata — use shared cache
    osrsdb_cache = os.path.join(get_cache_path(), "osrs-db")
    os.makedirs(osrsdb_cache, exist_ok=True)

    npcs_path = _download_if_missing(
        OSRSDB_NPCS_URL,
        os.path.join(osrsdb_cache, "npcs.g.json"),
        force=reset,
    )
    objects_path = _download_if_missing(
        OSRSDB_OBJECTS_URL,
        os.path.join(osrsdb_cache, "objects.g.json"),
        force=reset,
    )

    # Chunk data
    print("Chunking spatial data...")

    labels_data = _load_json(labels_path)
    location_chunks = chunk_map_labels(labels_data)
    print(f"  Named locations: {len(location_chunks)} chunks")

    npcs_data = _load_json(npcs_path)
    npc_chunks = chunk_npc_locations(npcs_data)
    print(f"  NPC locations: {len(npc_chunks)} chunks")

    objects_data = _load_json(objects_path)
    object_chunks = chunk_object_locations(objects_data)
    print(f"  Object locations: {len(object_chunks)} chunks")

    all_chunks = location_chunks + npc_chunks + object_chunks
    print(f"  Total spatial: {len(all_chunks)} chunks")

    # NPC spatial coverage report
    total_npcs = len(npcs_data)
    located_npcs = len(npc_chunks)
    coverage_pct = (located_npcs / total_npcs * 100) if total_npcs > 0 else 0
    print(f"\n  NPC spatial coverage: {located_npcs}/{total_npcs} ({coverage_pct:.1f}%)")
    if coverage_pct < 30:
        print("  NOTE: Most osrs-db NPCs lack coordinates. This is a known gap.")

    # Upsert
    print("\nEmbedding and upserting to ChromaDB...")
    for i in tqdm(range(0, len(all_chunks), BATCH_SIZE), desc="spatial"):
        batch = all_chunks[i:i + BATCH_SIZE]
        store.upsert_batch(
            collection="spatial",
            ids=[c["id"] for c in batch],
            documents=[c["document"] for c in batch],
            metadatas=[c["metadata"] for c in batch],
        )

    final_count = store.collection_count("spatial")
    print(f"  spatial collection: {final_count} documents")

    return {
        "location_chunks": len(location_chunks),
        "npc_location_chunks": len(npc_chunks),
        "object_location_chunks": len(object_chunks),
        "npc_coverage_pct": round(coverage_pct, 1),
        "total": final_count,
    }


if __name__ == "__main__":
    store = ChromaStore()
    stats = ingest_spatial(store, reset="--reset" in sys.argv)
    print(f"\nDone. {stats['total']} chunks in spatial.")
