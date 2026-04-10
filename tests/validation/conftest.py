"""
Shared fixtures and query sets for Phase 2 RAG validation tests.
"""

import pytest
import pytest_asyncio

from tools.search_engine import SearchEngine
from tools.index_builder import load_index
from rag.retriever import Retriever
from rag.store import sentinel_exists


# ---------------------------------------------------------------------------
# Query sets
# ---------------------------------------------------------------------------

# 15 Class.method exact API patterns
API_EXACT_QUERIES = [
    "Bank.isOpen",
    "Bank.open",
    "Bank.close",
    "Bank.depositAll",
    "Bank.withdraw",
    "Inventory.isFull",
    "Inventory.contains",
    "Inventory.getCount",
    "Walking.walk",
    "Walking.shouldWalk",
    "NPCs.closest",
    "GameObjects.closest",
    "Players.getLocal",
    "Sleep.sleep",
    "Skills.getRealLevel",
]

# 10 natural language queries
NATURAL_LANGUAGE_QUERIES = [
    "check if bank is open",
    "open the bank",
    "deposit all items",
    "withdraw items from bank",
    "check if inventory is full",
    "count items in inventory",
    "walk to a location",
    "find nearest NPC",
    "get player level",
    "wait for action to complete",
]

# 4 scripting-intent queries
SCRIPTING_QUERIES = [
    "how do I fish lobsters",
    "how to mine iron ore",
    "write a script to cut wood",
    "how do I train combat",
]

# 5 location queries
SPATIAL_QUERIES = [
    "Lumbridge",
    "Grand Exchange",
    "Varrock",
    "Falador",
    "Al Kharid",
]

# 5 item queries
ITEM_QUERIES = [
    "dragon scimitar",
    "lobster",
    "rune full helm",
    "shark",
    "abyssal whip",
]

# 5 NPC queries
NPC_QUERIES = [
    "guard",
    "goblin",
    "cow",
    "chicken",
    "giant spider",
]

# 8 high-traffic classes: (package, href, class_name)
LIVE_VERIFY_CLASSES = [
    ("org.dreambot.api.methods.container.impl", "Bank.html", "Bank"),
    ("org.dreambot.api.methods.container.impl", "Inventory.html", "Inventory"),
    ("org.dreambot.api.methods.walking.impl", "Walking.html", "Walking"),
    ("org.dreambot.api.methods.interactive", "NPCs.html", "NPCs"),
    ("org.dreambot.api.methods.interactive", "GameObjects.html", "GameObjects"),
    ("org.dreambot.api.methods.interactive", "Players.html", "Players"),
    ("org.dreambot.api.utilities", "Sleep.html", "Sleep"),
    ("org.dreambot.api.methods.skills", "Skills.html", "Skills"),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def legacy_engine() -> SearchEngine:
    """Session-scoped legacy SearchEngine loaded from the method index."""
    methods = load_index()
    return SearchEngine(methods)


@pytest.fixture(scope="session")
def retriever() -> Retriever:
    """Session-scoped RAG Retriever. Skips if RAG has not been initialized."""
    if not sentinel_exists():
        pytest.skip("RAG not initialized — run ingest first")
    return Retriever()
