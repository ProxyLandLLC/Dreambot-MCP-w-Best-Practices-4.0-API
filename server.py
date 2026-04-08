"""
DreamBot Scripting MCP Server — API 4.0
Provides JavaDocs lookup tools for DreamBot scripting.
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
from tools.index_builder import load_index
from tools.search_engine import SearchEngine

server = Server("dreambot-scripting-mcp", version="0.4.0")

_engine: SearchEngine | None = None


def _get_engine() -> SearchEngine:
    global _engine
    if _engine is None:
        methods = load_index()
        _engine = SearchEngine(methods)
    return _engine


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="dreambot_search",
            description=(
                "Search the DreamBot API 4.0 by natural language or keyword. "
                "Returns ranked per-method results with class name, signature, and description. "
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
                "Converts an Explv OSRS map URL or raw tile coordinates into ready-to-use "
                "DreamBot code snippets (Tile, Area, Walking.walk, Sleep.sleepUntil). "
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
                    "x": {
                        "type": "integer",
                        "description": "OSRS tile X coordinate (alternative to url).",
                    },
                    "y": {
                        "type": "integer",
                        "description": "OSRS tile Y coordinate (alternative to url).",
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


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "dreambot_search":
        try:
            return await handle_dreambot_search_tool(arguments, _get_engine())
        except FileNotFoundError as e:
            return [types.TextContent(type="text", text=f"Setup error: {e}")]
    elif name == "dreambot_tile":
        return await handle_dreambot_tile_tool(arguments)
    elif name == "dreambot_overview":
        return await handle_dreambot_overview_tool()
    elif name == "dreambot_package":
        return await handle_dreambot_package_tool(arguments)
    elif name == "dreambot_member":
        return await handle_dreambot_member_tool(arguments)
    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
