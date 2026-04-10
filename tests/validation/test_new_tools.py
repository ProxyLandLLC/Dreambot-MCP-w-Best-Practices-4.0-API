"""
Validation tests for the three new RAG-powered tools:
  - Item lookup (game_data collection, chunk_type=item)
  - NPC lookup (game_data collection, chunk_type=npc)
  - Location lookup (spatial collection)
"""

import pytest

from rag.retriever import Retriever
from rag.store import sentinel_exists
from tests.validation.conftest import ITEM_QUERIES, NPC_QUERIES, SPATIAL_QUERIES


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Known item IDs for spot-checking: {name: item_id}
KNOWN_ITEMS = {"bones": 526, "lobster": 379}

# Known NPC combat levels for spot-checking: {name: combat_level}
KNOWN_NPCS = {"Hans": 0}

# Valid OSRS world coordinate ranges
OSRS_X_RANGE = (1024, 4000)
OSRS_Y_RANGE = (2500, 10000)


# ---------------------------------------------------------------------------
# Module fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def retriever() -> Retriever:
    """Module-scoped RAG Retriever. Skips if RAG has not been initialized."""
    if not sentinel_exists():
        pytest.skip("RAG not initialized — run ingest first")
    return Retriever()


# ---------------------------------------------------------------------------
# Item tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDreambotItem:
    """Validate item lookups via the game_data collection (chunk_type=item)."""

    async def test_all_item_queries_return_results(self, retriever: Retriever):
        """Every query in ITEM_QUERIES must return at least one chunk."""
        empty_queries = []

        for query in ITEM_QUERIES:
            ctx = await retriever.retrieve(
                query,
                force_collections=["game_data"],
                extra_filters={"game_data": {"chunk_type": "item"}},
                top_k=5,
            )
            if len(ctx.chunks) == 0:
                empty_queries.append(query)

        assert not empty_queries, (
            f"Item queries returned 0 results for: {empty_queries}"
        )

    async def test_known_item_ids(self, retriever: Retriever):
        """
        Spot-check KNOWN_ITEMS: searching by name should return the correct
        item_id within the top 5 results.
        """
        failures = []

        for name, expected_id in KNOWN_ITEMS.items():
            ctx = await retriever.retrieve(
                name,
                force_collections=["game_data"],
                extra_filters={"game_data": {"chunk_type": "item"}},
                top_k=5,
            )
            found_ids = [
                chunk.metadata.get("item_id")
                for chunk in ctx.chunks
            ]
            if expected_id not in found_ids:
                failures.append({
                    "name": name,
                    "expected_id": expected_id,
                    "found_ids": found_ids,
                })

        assert not failures, (
            f"Known item ID check failed: {failures}"
        )

    async def test_item_metadata_complete(self, retriever: Retriever):
        """
        Dragon scimitar results must contain all required metadata fields:
        item_id, name, tradeable, members, equipable, slot, chunk_type.
        """
        required_fields = {"item_id", "name", "tradeable", "members", "equipable", "slot", "chunk_type"}

        ctx = await retriever.retrieve(
            "dragon scimitar",
            force_collections=["game_data"],
            extra_filters={"game_data": {"chunk_type": "item"}},
            top_k=5,
        )

        assert ctx.chunks, "No results returned for 'dragon scimitar'"

        missing_per_chunk = []
        for chunk in ctx.chunks:
            missing = required_fields - set(chunk.metadata.keys())
            if missing:
                missing_per_chunk.append({
                    "chunk_name": chunk.metadata.get("name"),
                    "missing_fields": sorted(missing),
                })

        assert not missing_per_chunk, (
            f"Some dragon scimitar chunks are missing metadata fields: {missing_per_chunk}"
        )


# ---------------------------------------------------------------------------
# NPC tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDreambotNpc:
    """Validate NPC lookups via the game_data collection (chunk_type=npc)."""

    async def test_all_npc_queries_return_results(self, retriever: Retriever):
        """Every query in NPC_QUERIES must return at least one chunk."""
        empty_queries = []

        for query in NPC_QUERIES:
            ctx = await retriever.retrieve(
                query,
                force_collections=["game_data"],
                extra_filters={"game_data": {"chunk_type": "npc"}},
                top_k=5,
            )
            if len(ctx.chunks) == 0:
                empty_queries.append(query)

        assert not empty_queries, (
            f"NPC queries returned 0 results for: {empty_queries}"
        )

    async def test_known_npc_combat_levels(self, retriever: Retriever):
        """
        Spot-check KNOWN_NPCS: searching by NPC name should return the correct
        combat_level within the top 5 results.
        """
        failures = []

        for name, expected_combat in KNOWN_NPCS.items():
            ctx = await retriever.retrieve(
                name,
                force_collections=["game_data"],
                extra_filters={"game_data": {"chunk_type": "npc"}},
                top_k=5,
            )
            found_levels = [
                chunk.metadata.get("combat_level")
                for chunk in ctx.chunks
            ]
            if expected_combat not in found_levels:
                failures.append({
                    "name": name,
                    "expected_combat_level": expected_combat,
                    "found_levels": found_levels,
                })

        assert not failures, (
            f"Known NPC combat level check failed: {failures}"
        )


# ---------------------------------------------------------------------------
# Location tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDreambotLocation:
    """Validate location lookups via the spatial collection."""

    async def test_all_spatial_queries_return_results(self, retriever: Retriever):
        """Every query in SPATIAL_QUERIES must return at least one chunk."""
        empty_queries = []

        for query in SPATIAL_QUERIES:
            ctx = await retriever.retrieve(
                query,
                force_collections=["spatial"],
                top_k=5,
            )
            if len(ctx.chunks) == 0:
                empty_queries.append(query)

        assert not empty_queries, (
            f"Spatial queries returned 0 results for: {empty_queries}"
        )

    async def test_coordinates_in_valid_range(self, retriever: Retriever):
        """
        All returned world_x and world_y coordinates must fall within the
        valid OSRS coordinate ranges defined by OSRS_X_RANGE and OSRS_Y_RANGE.
        """
        out_of_range = []

        for query in SPATIAL_QUERIES:
            ctx = await retriever.retrieve(
                query,
                force_collections=["spatial"],
                top_k=5,
            )
            for chunk in ctx.chunks:
                world_x = chunk.metadata.get("world_x")
                world_y = chunk.metadata.get("world_y")

                if world_x is None or world_y is None:
                    continue

                x_ok = OSRS_X_RANGE[0] <= world_x <= OSRS_X_RANGE[1]
                y_ok = OSRS_Y_RANGE[0] <= world_y <= OSRS_Y_RANGE[1]

                if not x_ok or not y_ok:
                    out_of_range.append({
                        "query": query,
                        "name": chunk.metadata.get("name"),
                        "world_x": world_x,
                        "world_y": world_y,
                    })

        assert not out_of_range, (
            f"Coordinates outside valid OSRS ranges "
            f"(x: {OSRS_X_RANGE}, y: {OSRS_Y_RANGE}): {out_of_range}"
        )

    async def test_lumbridge_coordinates_roughly_correct(self, retriever: Retriever):
        """
        Querying 'Lumbridge' should return at least one result whose
        world_x and world_y are within 50 tiles of (3222, 3218).
        """
        LUMBRIDGE_X = 3222
        LUMBRIDGE_Y = 3218
        TOLERANCE = 50

        ctx = await retriever.retrieve(
            "Lumbridge",
            force_collections=["spatial"],
            top_k=10,
        )

        assert ctx.chunks, "No results returned for 'Lumbridge' spatial query"

        close_enough = False
        for chunk in ctx.chunks:
            world_x = chunk.metadata.get("world_x")
            world_y = chunk.metadata.get("world_y")

            if world_x is None or world_y is None:
                continue

            if (
                abs(world_x - LUMBRIDGE_X) <= TOLERANCE
                and abs(world_y - LUMBRIDGE_Y) <= TOLERANCE
            ):
                close_enough = True
                break

        assert close_enough, (
            f"No Lumbridge result within {TOLERANCE} tiles of "
            f"({LUMBRIDGE_X}, {LUMBRIDGE_Y}). Chunks returned: "
            + str([
                {"name": c.metadata.get("name"), "x": c.metadata.get("world_x"), "y": c.metadata.get("world_y")}
                for c in ctx.chunks
            ])
        )
