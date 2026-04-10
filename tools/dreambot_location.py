"""
dreambot_location — Find coordinates, nearby features, and DreamBot code
for any OSRS location. Queries the spatial collection.
"""

from mcp.types import TextContent
from rag.retriever import Retriever


async def handle_dreambot_location_tool(
    arguments: dict, retriever: Retriever
) -> list[TextContent]:
    query = arguments.get("query", "").strip()
    if not query:
        return [TextContent(type="text", text="Error: 'query' parameter is required.")]

    try:
        top_k = int(arguments.get("top_k", 5))
        if top_k < 1:
            top_k = 5
    except (ValueError, TypeError):
        top_k = 5

    result = await retriever.retrieve(
        query=query,
        force_collections=["spatial"],
        top_k=top_k,
    )

    if not result.chunks:
        return [TextContent(
            type="text",
            text=f"No locations found matching '{query}'. Try a different name or description.",
        )]

    lines = [f"Location results for: '{query}'", "=" * 60, ""]

    for chunk in result.chunks:
        meta = chunk.metadata
        name = meta.get("name", "Unknown")
        ct = meta.get("chunk_type", "")
        x = meta.get("world_x", "?")
        y = meta.get("world_y", "?")
        plane = meta.get("plane", 0)

        lines.append(f"{name}  [{ct}]")
        lines.append(f"  Coordinates: ({x}, {y}, {plane})")
        lines.append(f"  new Tile({x}, {y}, {plane})")

        # Area snippet with default radius
        if isinstance(x, int) and isinstance(y, int):
            r = 15
            lines.append(f"  new Area({x - r}, {y - r}, {x + r}, {y + r})")
            lines.append(f"  Walking.walk(new Tile({x}, {y}, {plane}));")

        # Extra info depending on chunk type
        if ct == "npc_location":
            interactions = meta.get("interactions", "")
            combat = meta.get("combat_level", "")
            if interactions:
                lines.append(f"  Interactions: {interactions}")
            if combat:
                lines.append(f"  Combat level: {combat}")
        elif ct == "object_location":
            actions = meta.get("actions", "")
            coords_json = meta.get("coordinates", "")
            if actions:
                lines.append(f"  Actions: {actions}")
            if coords_json:
                lines.append(f"  All positions: {coords_json}")
        elif ct == "named_location":
            region = meta.get("region", "")
            if region:
                lines.append(f"  Region: {region}")

        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]
