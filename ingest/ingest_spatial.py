"""
Spatial data ingestion pipeline.
Sources: Explv map_labels.json, osrs-db NPC data, osrs-db object data
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
from ingest._osrsdb import ensure_osrsdb_cached

BATCH_SIZE = 500

MAP_LABELS_URL = "https://raw.githubusercontent.com/Explv/Explv.github.io/master/public/resources/map_labels.json"


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

    # Download map labels
    print("Fetching spatial data sources...")
    labels_path = _download_if_missing(
        MAP_LABELS_URL,
        os.path.join(cache_dir, "map_labels.json"),
        force=reset,
    )

    # Get osrs-db data (shared npm download)
    osrsdb_cache = ensure_osrsdb_cached(force=reset)
    npcs_path = os.path.join(osrsdb_cache, "npcs.g.json")
    objects_path = os.path.join(osrsdb_cache, "objects.g.json")

    # Chunk data
    print("Chunking spatial data...")

    labels_data = _load_json(labels_path)
    location_chunks = chunk_map_labels(labels_data)
    print(f"  Named locations: {len(location_chunks)} chunks")

    npc_chunks = []
    if os.path.exists(npcs_path):
        npcs_data = _load_json(npcs_path)
        npc_chunks = chunk_npc_locations(npcs_data)
    print(f"  NPC locations: {len(npc_chunks)} chunks")

    object_chunks = []
    if os.path.exists(objects_path):
        objects_data = _load_json(objects_path)
        object_chunks = chunk_object_locations(objects_data)
    print(f"  Object locations: {len(object_chunks)} chunks")

    all_chunks = location_chunks + npc_chunks + object_chunks
    print(f"  Total spatial: {len(all_chunks)} chunks")

    # NPC spatial coverage report
    if os.path.exists(npcs_path):
        npcs_data = _load_json(npcs_path)
        total_npcs = len(npcs_data) if isinstance(npcs_data, list) else len(npcs_data.keys())
        located_npcs = len(npc_chunks)
        coverage_pct = (located_npcs / total_npcs * 100) if total_npcs > 0 else 0
        print(f"\n  NPC spatial coverage: {located_npcs}/{total_npcs} ({coverage_pct:.1f}%)")
        if coverage_pct < 30:
            print("  NOTE: osrs-db cache data typically lacks NPC coordinates. This is a known gap.")
    else:
        coverage_pct = 0

    if not all_chunks:
        print("\n  WARNING: No spatial chunks generated. Only map labels available.")
        # Still write what we have (map labels at minimum)
        if not location_chunks:
            return {
                "location_chunks": 0, "npc_location_chunks": 0,
                "object_location_chunks": 0, "npc_coverage_pct": 0, "total": 0,
            }

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
