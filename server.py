"""
DreamBot Scripting MCP Server — API 4.0
Provides JavaDocs lookup tools for DreamBot scripting.

Phase 1: RAG alongside legacy. If ChromaDB sentinel exists, uses RAG retriever.
Otherwise falls back to legacy SearchEngine.
"""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from tools.dreambot_overview import handle_dreambot_overview_tool
from tools.dreambot_package import handle_dreambot_package_tool
from tools.dreambot_member import handle_dreambot_member_tool
from tools.dreambot_search import handle_dreambot_search_tool
from tools.dreambot_tile import handle_dreambot_tile_tool

server = Server("dreambot-scripting-mcp", version="0.5.0")

# RAG retriever (initialized if sentinel exists)
_retriever = None
# Legacy engine (fallback)
_engine = None
# Whether RAG is available
_rag_available = False


def _check_rag_available() -> bool:
    """Check if RAG has been initialized (sentinel file exists)."""
    try:
        from rag.store import sentinel_exists
        return sentinel_exists()
    except ImportError:
        return False


def _get_retriever():
    """Lazy-init the RAG retriever."""
    global _retriever
    if _retriever is None:
        from rag.retriever import Retriever
        _retriever = Retriever()
    return _retriever


def _get_engine():
    """Lazy-init the legacy SearchEngine."""
    global _engine
    if _engine is None:
        from tools.index_builder import load_index
        from tools.search_engine import SearchEngine
        methods = load_index()
        _engine = SearchEngine(methods)
    return _engine


def _get_search_backend():
    """Return RAG retriever if available, otherwise legacy engine."""
    if _rag_available:
        return _get_retriever()
    return _get_engine()


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    tools = [
        types.Tool(
            name="dreambot_search",
            description=(
                "Search the DreamBot API 4.0 by natural language or keyword. "
                "Returns ranked results with class name, signature, and description. "
                "May also return relevant locations and game data when contextually appropriate. "
                "This is the primary tool — use it first before dreambot_member."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural language or keyword query. Examples: "
                            "'check if bank is open', 'Bank.isOpen', "
                            "'walk to a tile', 'get all inventory items', "
                            "'interact with npc'"
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Max results to return. Default: 8.",
                        "default": 8,
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="dreambot_overview",
            description=(
                "Lists all packages in the DreamBot API 4.0 JavaDocs. "
                "Use this to browse available packages before drilling into a specific one."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="dreambot_package",
            description=(
                "Fetches all classes, interfaces, and enums in a specific DreamBot API package. "
                "Returns class names and their href values for use with dreambot_member."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "package": {
                        "type": "string",
                        "description": (
                            "Dot-separated package name. "
                            "Examples: 'org.dreambot.api.methods.container.impl.bank', "
                            "'org.dreambot.api.methods.interactive', "
                            "'org.dreambot.api.methods.walking.impl'"
                        ),
                    }
                },
                "required": ["package"],
            },
        ),
        types.Tool(
            name="dreambot_member",
            description=(
                "Fetches the full method summary for a specific class in the DreamBot API. "
                "Returns modifier, signature, and description for each method. "
                "Use dreambot_search first to identify the class, "
                "then call this with the package and href for complete details."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "package": {
                        "type": "string",
                        "description": "Dot-separated package name containing the class.",
                    },
                    "href": {
                        "type": "string",
                        "description": (
                            "The HTML filename for the class, e.g. 'Bank.html'. "
                            "Obtained from dreambot_search or dreambot_package results."
                        ),
                    },
                },
                "required": ["package", "href"],
            },
        ),
        types.Tool(
            name="dreambot_tile",
            description=(
                "Converts an Explv OSRS map URL, raw tile coordinates, or location name "
                "into ready-to-use DreamBot code snippets (Tile, Area, Walking.walk, Sleep.sleepUntil). "
                "Use this any time you need to reference a map location in a script. "
                "Explv map: https://explv.github.io/"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "Explv map URL. Example: "
                            "'https://explv.github.io/?centreX=2916&centreY=3311&centreZ=0&zoom=7'"
                        ),
                    },
                    "location": {
                        "type": "string",
                        "description": (
                            "Location name to resolve to coordinates via spatial lookup. "
                            "Examples: 'Lumbridge', 'Varrock West Bank', 'Catherby fishing spots'. "
                            "Requires RAG to be initialized."
                        ),
                    },
                    "x": {
                        "type": "integer",
                        "description": "OSRS tile X coordinate (alternative to url/location).",
                    },
                    "y": {
                        "type": "integer",
                        "description": "OSRS tile Y coordinate (alternative to url/location).",
                    },
                    "z": {
                        "type": "integer",
                        "description": "Plane / floor level. 0 = ground floor. Default: 0.",
                        "default": 0,
                    },
                },
            },
        ),
    ]

    # Add RAG-only tools when available
    if _rag_available:
        tools.extend([
            types.Tool(
                name="dreambot_location",
                description=(
                    "Find coordinates, nearby features, and DreamBot code for any OSRS location. "
                    "Returns named locations, NPC positions, and object positions with Tile code. "
                    "Use this when you need to find where something is on the map."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Location query. Examples: 'Catherby fishing spots', "
                                "'nearest bank to Falador', 'yew trees', 'Lumbridge'"
                            ),
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Max results to return. Default: 5.",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="dreambot_item",
                description=(
                    "Look up OSRS item data — IDs, stats, equipment bonuses, requirements. "
                    "Use this when you need item IDs for script logic, equipment stats, "
                    "or trade information."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Item query. Examples: 'dragon scimitar', 'lobster', "
                                "'rune axe stats', 'best f2p weapon'"
                            ),
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Max results to return. Default: 5.",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="dreambot_npc",
                description=(
                    "Look up NPC data — combat stats, drops, and location if known. "
                    "Use this when you need NPC IDs, combat info, or drop tables for scripts."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "NPC query. Examples: 'guard', 'hans', 'giant spider', "
                                "'goblin drops'"
                            ),
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Max results to return. Default: 5.",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
        ])

    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    retriever = _get_retriever() if _rag_available else None

    if name == "dreambot_search":
        try:
            return await handle_dreambot_search_tool(arguments, _get_search_backend())
        except FileNotFoundError as e:
            return [types.TextContent(type="text", text=f"Setup error: {e}")]

    elif name == "dreambot_tile":
        return await handle_dreambot_tile_tool(arguments, retriever=retriever)

    elif name == "dreambot_overview":
        return await handle_dreambot_overview_tool()

    elif name == "dreambot_package":
        return await handle_dreambot_package_tool(arguments, retriever=retriever)

    elif name == "dreambot_member":
        return await handle_dreambot_member_tool(arguments, retriever=retriever)

    elif name == "dreambot_location":
        if not retriever:
            return [types.TextContent(type="text", text="Error: RAG not initialized. Run 'python -m ingest.run_ingest' first.")]
        from tools.dreambot_location import handle_dreambot_location_tool
        return await handle_dreambot_location_tool(arguments, retriever)

    elif name == "dreambot_item":
        if not retriever:
            return [types.TextContent(type="text", text="Error: RAG not initialized. Run 'python -m ingest.run_ingest' first.")]
        from tools.dreambot_item import handle_dreambot_item_tool
        return await handle_dreambot_item_tool(arguments, retriever)

    elif name == "dreambot_npc":
        if not retriever:
            return [types.TextContent(type="text", text="Error: RAG not initialized. Run 'python -m ingest.run_ingest' first.")]
        from tools.dreambot_npc import handle_dreambot_npc_tool
        return await handle_dreambot_npc_tool(arguments, retriever)

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    global _rag_available

    # Check for RAG availability at startup
    _rag_available = _check_rag_available()

    if _rag_available:
        # Eager warm-up: load embedding model into memory before first query
        try:
            retriever = _get_retriever()
            retriever.warm_up()
        except Exception as e:
            import sys
            print(f"RAG warm-up failed, falling back to legacy: {e}", file=sys.stderr)
            _rag_available = False

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
