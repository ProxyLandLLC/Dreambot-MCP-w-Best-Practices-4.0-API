"""
Ingestion orchestrator — runs all or selected pipelines.

Usage:
  python -m ingest.run_ingest                    # full ingest, all collections
  python -m ingest.run_ingest --collection api   # just api_methods
  python -m ingest.run_ingest --collection spatial
  python -m ingest.run_ingest --collection gamedata
  python -m ingest.run_ingest --reset            # wipe + rebuild all collections
"""

import argparse
import sys
import time

from rag.store import ChromaStore, write_sentinel


def main():
    parser = argparse.ArgumentParser(description="Ingest data into DreamBot MCP ChromaDB")
    parser.add_argument(
        "--collection",
        choices=["api", "spatial", "gamedata"],
        help="Ingest only a specific collection (default: all)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe and rebuild collections before ingesting",
    )
    args = parser.parse_args()

    store = ChromaStore()
    all_stats = {}
    start_time = time.time()

    collections_to_run = (
        [args.collection] if args.collection
        else ["api", "spatial", "gamedata"]
    )

    for collection in collections_to_run:
        print(f"\n{'=' * 60}")
        print(f"  Ingesting: {collection}")
        print(f"{'=' * 60}\n")

        if collection == "api":
            from ingest.ingest_api import ingest_api
            all_stats["api_methods"] = ingest_api(store, reset=args.reset)

        elif collection == "spatial":
            from ingest.ingest_spatial import ingest_spatial
            all_stats["spatial"] = ingest_spatial(store, reset=args.reset)

        elif collection == "gamedata":
            from ingest.ingest_gamedata import ingest_gamedata
            all_stats["game_data"] = ingest_gamedata(store, reset=args.reset)

    elapsed = time.time() - start_time

    # Write sentinel on success
    write_sentinel()

    # Print summary
    print(f"\n{'=' * 60}")
    print("  INGESTION COMPLETE")
    print(f"{'=' * 60}\n")

    total_chunks = 0
    for coll_name, stats in all_stats.items():
        count = stats.get("total", 0)
        total_chunks += count
        print(f"  {coll_name}: {count} chunks")

        # Collection-specific details
        if coll_name == "api_methods":
            print(f"    Methods: {stats.get('method_chunks', 0)}")
            print(f"    Classes: {stats.get('class_chunks', 0)}")
        elif coll_name == "spatial":
            print(f"    Locations: {stats.get('location_chunks', 0)}")
            print(f"    NPC locations: {stats.get('npc_location_chunks', 0)}")
            print(f"    Object locations: {stats.get('object_location_chunks', 0)}")
            coverage = stats.get("npc_coverage_pct", 0)
            if coverage < 30:
                print(f"    WARNING: NPC spatial coverage is {coverage}% (most NPCs lack coordinates)")
        elif coll_name == "game_data":
            print(f"    Items: {stats.get('item_chunks', 0)}")
            print(f"    NPCs: {stats.get('npc_chunks', 0)}")

    print(f"\n  Total chunks: {total_chunks}")
    print(f"  Time elapsed: {elapsed:.1f}s")
    print(f"\n  Sentinel written. RAG is now active.")


if __name__ == "__main__":
    main()
