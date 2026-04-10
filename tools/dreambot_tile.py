"""
Converts Explv OSRS map URLs, raw tile coordinates, or location names
into DreamBot code snippets.

Enhanced with RAG spatial lookup: when a 'location' string is provided,
queries the spatial collection to resolve name to coordinates.
"""
from urllib.parse import urlparse, parse_qs
from mcp.types import TextContent


async def handle_dreambot_tile_tool(arguments: dict, retriever=None) -> list[TextContent]:
    url = arguments.get("url", "").strip()
    location = arguments.get("location", "").strip()
    x_raw = arguments.get("x")
    y_raw = arguments.get("y")
    z_raw = arguments.get("z", 0)

    # Priority: URL > raw coordinates > location name
    if url:
        try:
            params = parse_qs(urlparse(url).query)
            x = int(params["centreX"][0])
            y = int(params["centreY"][0])
            z = int(params.get("centreZ", ["0"])[0])
        except (KeyError, ValueError, IndexError):
            return [TextContent(type="text", text=(
                "Error: could not parse Explv URL.\n"
                "Expected format: https://explv.github.io/?centreX=2916&centreY=3311&centreZ=0&zoom=7"
            ))]
        return [TextContent(type="text", text=_generate_snippets(x, y, z))]

    elif x_raw is not None and y_raw is not None:
        try:
            x, y, z = int(x_raw), int(y_raw), int(z_raw or 0)
        except (ValueError, TypeError):
            return [TextContent(type="text", text="Error: x, y, z must be integers.")]
        return [TextContent(type="text", text=_generate_snippets(x, y, z))]

    elif location and retriever:
        return await _resolve_location(location, retriever)

    elif location and not retriever:
        return [TextContent(type="text", text=(
            "Error: location name lookup requires RAG to be initialized.\n"
            "Run 'python -m ingest.run_ingest' first, or use URL/coordinates instead."
        ))]

    else:
        return [TextContent(type="text", text=(
            "Error: provide 'url' (Explv map URL), 'x'/'y' coordinates, or 'location' name.\n"
            "Example: url='https://explv.github.io/?centreX=2916&centreY=3311&centreZ=0&zoom=7'\n"
            "Example: location='Lumbridge'"
        ))]


async def _resolve_location(location: str, retriever) -> list[TextContent]:
    """Resolve a location name to coordinates via spatial RAG lookup."""
    result = await retriever.retrieve(
        query=location,
        force_collections=["spatial"],
        extra_filters={"spatial": {"chunk_type": "named_location"}},
        top_k=3,
    )

    if not result.chunks:
        return [TextContent(
            type="text",
            text=f"No locations found matching '{location}'. Try a different name or use coordinates.",
        )]

    # Single high-confidence result — generate code directly
    if len(result.chunks) == 1:
        chunk = result.chunks[0]
        meta = chunk.metadata
        x = meta.get("world_x", 0)
        y = meta.get("world_y", 0)
        z = meta.get("plane", 0)
        name = meta.get("name", location)
        header = f"Location: {name}\n"
        return [TextContent(type="text", text=header + _generate_snippets(x, y, z))]

    # Multiple candidates — present options
    lines = [f'Location candidates for "{location}":', ""]
    for i, chunk in enumerate(result.chunks, 1):
        meta = chunk.metadata
        x = meta.get("world_x", 0)
        y = meta.get("world_y", 0)
        z = meta.get("plane", 0)
        name = meta.get("name", "?")
        region = meta.get("region", "")
        region_str = f" ({region})" if region else ""
        lines.append(f"  [{i}] {name}{region_str} — Tile({x}, {y}, {z})")

    lines.append("")
    lines.append("Specify which location to generate full code snippets,")
    lines.append("or use dreambot_tile with x/y coordinates directly.")

    return [TextContent(type="text", text="\n".join(lines))]


def _generate_snippets(x: int, y: int, z: int) -> str:
    """Generate DreamBot code snippets for a tile coordinate."""
    r = 15
    explv_url = f"https://explv.github.io/?centreX={x}&centreY={y}&centreZ={z}&zoom=7"

    return "\n".join([
        f"Tile ({x}, {y}, z={z})  —  {explv_url}",
        "",
        "// Single tile",
        f"new Tile({x}, {y}, {z})",
        "",
        "// Area (±15 tiles around center)",
        f"new Area({x - r}, {y - r}, {x + r}, {y + r})",
        "",
        "// Area with explicit plane",
        f"new Area(new Tile({x - r}, {y - r}, {z}), new Tile({x + r}, {y + r}, {z}))",
        "",
        "// Walk to tile",
        f"Walking.walk(new Tile({x}, {y}, {z}));",
        "",
        "// Walk and wait until within 5 tiles",
        f"Walking.walk(new Tile({x}, {y}, {z}));",
        f"Sleep.sleepUntil(() -> Players.localPlayer().distance(new Tile({x}, {y}, {z})) < 5, 10_000);",
        "",
        "// Area membership check",
        f"Area area = new Area({x - r}, {y - r}, {x + r}, {y + r});",
        f"boolean inArea = area.contains(Players.localPlayer());",
    ])
