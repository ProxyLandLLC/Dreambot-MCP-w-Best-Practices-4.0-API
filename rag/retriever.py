"""
Intent-routed retriever — classifies queries, fans out to collections, merges results.

Three stages:
  1. Intent classification (keyword signals + pattern matching)
  2. Query execution (concurrent multi-collection queries)
  3. Context formatting (structured sections per collection)
"""

import asyncio
import re
from dataclasses import dataclass, field

from rag.store import ChromaStore


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QueryIntent:
    collections: list[str]
    filters: dict[str, dict] = field(default_factory=dict)
    top_k: dict[str, int] = field(default_factory=dict)
    query_text: str = ""
    intent_type: str = "general"


@dataclass
class ChunkResult:
    document: str
    metadata: dict
    distance: float
    collection: str = ""


@dataclass
class FormattedContext:
    text: str
    chunks: list[ChunkResult]
    sections: dict[str, list[ChunkResult]]


# ---------------------------------------------------------------------------
# Intent classification patterns
# ---------------------------------------------------------------------------

# camelCase or Class.method patterns
_API_PATTERN = re.compile(
    r"(?:[A-Z][a-zA-Z0-9]*\.(?:[a-z][a-zA-Z0-9]*)|"  # Class.method
    r"[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*)"             # camelCase
)

_SPATIAL_KEYWORDS = {
    "where", "location", "coordinates", "near", "nearest", "closest",
    "position", "tile", "area", "walk to", "go to", "path to",
}

_GAMEDATA_KEYWORDS = {
    "item", "equip", "equipment", "stats", "drops", "drop", "id",
    "alch", "price", "buy", "sell", "slot", "weapon", "armour", "armor",
    "requirement", "requirements", "combat level",
}

_SCRIPTING_KEYWORDS = {
    "how do i", "how to", "write a script", "make a bot", "script for",
    "bot for", "automate", "scripting",
}

# NPC-related keywords that push toward game_data npc chunks
_NPC_KEYWORDS = {
    "npc", "monster", "enemy", "mob", "boss", "hitpoints", "hp",
    "max hit", "attack style",
}


def _query_lower(query: str) -> str:
    return query.lower().strip()


def _has_any_keyword(text: str, keywords: set[str]) -> bool:
    for kw in keywords:
        if kw in text:
            return True
    return False


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

class Retriever:
    """
    Entry point for all RAG queries. Tools call retrieve() with optional
    force_collections and extra_filters to override intent routing.
    """

    # Distance threshold for speculative fallback results
    SPECULATIVE_THRESHOLD = 1.2

    def __init__(self, store: ChromaStore | None = None):
        self.store = store or ChromaStore()

    def warm_up(self):
        """Eager model load — call at server startup."""
        self.store.embed_dummy()

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    async def retrieve(
        self,
        query: str,
        force_collections: list[str] | None = None,
        extra_filters: dict[str, dict] | None = None,
        top_k: int = 8,
    ) -> FormattedContext:
        intent = self._classify_intent(query, top_k)

        if force_collections:
            intent.collections = force_collections
            # Set uniform top_k for forced collections
            intent.top_k = {c: top_k for c in force_collections}

        if extra_filters:
            for coll, filt in extra_filters.items():
                intent.filters[coll] = filt

        chunks = await self._execute_queries(intent)
        return self._format_context(chunks)

    # -------------------------------------------------------------------
    # Stage 1: Intent Classification
    # -------------------------------------------------------------------

    def _classify_intent(self, query: str, default_top_k: int = 8) -> QueryIntent:
        lower = _query_lower(query)
        intent = QueryIntent(
            collections=[],
            query_text=query,
        )

        has_scripting = _has_any_keyword(lower, _SCRIPTING_KEYWORDS)
        has_api_ref = bool(_API_PATTERN.search(query))
        has_spatial = _has_any_keyword(lower, _SPATIAL_KEYWORDS)
        has_gamedata = _has_any_keyword(lower, _GAMEDATA_KEYWORDS)
        has_npc = _has_any_keyword(lower, _NPC_KEYWORDS)

        # Priority 1: Scripting intent — always include api_methods
        if has_scripting:
            intent.intent_type = "scripting"
            intent.collections.append("api_methods")
            intent.top_k["api_methods"] = default_top_k

            if has_spatial:
                intent.collections.append("spatial")
                intent.top_k["spatial"] = 3
            if has_gamedata or has_npc:
                intent.collections.append("game_data")
                intent.top_k["game_data"] = 3

            if len(intent.collections) > 1:
                intent.intent_type = "scripting_located"
            return intent

        # Priority 2: Explicit API reference (no scripting intent)
        if has_api_ref:
            intent.intent_type = "api_lookup"
            intent.collections = ["api_methods"]
            intent.top_k["api_methods"] = default_top_k
            return intent

        # Priority 3: Spatial keywords
        if has_spatial:
            intent.intent_type = "spatial"
            intent.collections = ["spatial"]
            intent.top_k["spatial"] = default_top_k
            return intent

        # Priority 4: Game data keywords
        if has_gamedata or has_npc:
            intent.intent_type = "game_data"
            intent.collections = ["game_data"]
            intent.top_k["game_data"] = default_top_k
            if has_npc:
                intent.filters["game_data"] = {"chunk_type": "npc"}
            return intent

        # Fallback: general — query api_methods primary + speculative others
        intent.intent_type = "general"
        intent.collections = ["api_methods", "spatial", "game_data"]
        intent.top_k = {
            "api_methods": default_top_k,
            "spatial": 2,
            "game_data": 2,
        }
        return intent

    # -------------------------------------------------------------------
    # Stage 2: Query Execution
    # -------------------------------------------------------------------

    async def _execute_queries(self, intent: QueryIntent) -> list[ChunkResult]:
        async def _query_one(collection: str) -> list[ChunkResult]:
            top_k = intent.top_k.get(collection, 8)
            where = intent.filters.get(collection)

            results = self.store.query(
                collection=collection,
                query_text=intent.query_text,
                where=where,
                n_results=top_k,
            )

            chunks = []
            for doc, metadata, distance in results:
                # For general intent, gate speculative results by threshold
                if intent.intent_type == "general" and collection != "api_methods":
                    if distance > self.SPECULATIVE_THRESHOLD:
                        continue
                chunks.append(ChunkResult(
                    document=doc,
                    metadata=metadata,
                    distance=distance,
                    collection=collection,
                ))
            return chunks

        # Run queries concurrently
        tasks = [_query_one(c) for c in intent.collections]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_chunks = []
        for result in results:
            if isinstance(result, Exception):
                continue
            all_chunks.extend(result)

        return all_chunks

    # -------------------------------------------------------------------
    # Stage 3: Context Formatting
    # -------------------------------------------------------------------

    def _format_context(self, chunks: list[ChunkResult]) -> FormattedContext:
        sections: dict[str, list[ChunkResult]] = {}
        for chunk in chunks:
            sections.setdefault(chunk.collection, []).append(chunk)

        lines = []

        # API Methods section
        if "api_methods" in sections:
            lines.append("=== API Methods ===")
            for chunk in sections["api_methods"]:
                meta = chunk.metadata
                ct = meta.get("chunk_type", "method")

                if ct == "class_overview":
                    lines.append(f"[{meta.get('class_name', '?')}] Class Overview")
                    lines.append(f"  {chunk.document[:300]}")
                    pkg = meta.get("package", "")
                    if pkg:
                        lines.append(f"  Package: {pkg}")
                else:
                    cls = meta.get("class_name", "?")
                    mods = meta.get("modifiers", "")
                    ret = meta.get("return_type", "")
                    name = meta.get("method_name", "")
                    params = meta.get("params", "")
                    sig = f"{mods} {ret} {name}({params})".strip()
                    lines.append(f"[{cls}] {sig}")

                    # Extract description from document text (after " — ")
                    doc = chunk.document
                    dash_idx = doc.find(" — ")
                    desc = doc[dash_idx + 3:].strip() if dash_idx != -1 else ""
                    if desc:
                        lines.append(f"  {desc[:200]}")

                    pkg = meta.get("package", "")
                    if pkg:
                        lines.append(f"  Package: {pkg}")
                lines.append("")

        # Spatial section
        if "spatial" in sections:
            lines.append("=== Locations ===")
            for chunk in sections["spatial"]:
                meta = chunk.metadata
                name = meta.get("name", "Unknown")
                ct = meta.get("chunk_type", "")
                x = meta.get("world_x", "?")
                y = meta.get("world_y", "?")
                plane = meta.get("plane", 0)
                lines.append(f"{name} — Coordinates: ({x}, {y}, {plane}) [{ct}]")
                lines.append(f"  DreamBot: new Tile({x}, {y}, {plane})")
                lines.append("")

        # Game Data section
        if "game_data" in sections:
            lines.append("=== Game Data ===")
            for chunk in sections["game_data"]:
                meta = chunk.metadata
                ct = meta.get("chunk_type", "")
                name = meta.get("name", "Unknown")
                if ct == "item":
                    item_id = meta.get("item_id", "?")
                    lines.append(f"{name} — Item ID: {item_id}")
                elif ct == "npc":
                    npc_id = meta.get("npc_id", "?")
                    combat = meta.get("combat_level", "?")
                    lines.append(f"{name} — NPC ID: {npc_id}, Combat: {combat}")
                else:
                    lines.append(f"{name}")
                # Truncated document for detail
                lines.append(f"  {chunk.document[:200]}")
                lines.append("")

        text = "\n".join(lines).strip()
        return FormattedContext(text=text, chunks=chunks, sections=sections)
