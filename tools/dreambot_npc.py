"""
dreambot_npc — Look up NPC data: combat stats, drops, and location if known.
Queries game_data for NPC stats, then does a batched spatial join for locations.
"""

from mcp.types import TextContent
from rag.retriever import Retriever


async def handle_dreambot_npc_tool(
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

    # Step 1: Get NPC stats from game_data
    stats_result = await retriever.retrieve(
        query=query,
        force_collections=["game_data"],
        extra_filters={"game_data": {"chunk_type": "npc"}},
        top_k=top_k,
    )

    if not stats_result.chunks:
        return [TextContent(
            type="text",
            text=f"No NPCs found matching '{query}'. Try a different name.",
        )]

    # Step 2: Batched spatial join — collect NPC names and query spatial collection
    npc_names = list({c.metadata.get("name", "") for c in stats_result.chunks if c.metadata.get("name")})

    location_map: dict[str, list] = {}
    if npc_names:
        # Query spatial for npc_location chunks matching these names
        # Use the first NPC name as primary query for semantic match
        spatial_result = await retriever.retrieve(
            query=" ".join(npc_names),
            force_collections=["spatial"],
            extra_filters={"spatial": {
                "$and": [
                    {"chunk_type": "npc_location"},
                    {"name": {"$in": npc_names}},
                ]
            }},
            top_k=len(npc_names) * 2,
        )

        for chunk in spatial_result.chunks:
            name = chunk.metadata.get("name", "")
            if name:
                location_map.setdefault(name, []).append(chunk)

    # Step 3: Format output
    lines = [f"NPC results for: '{query}'", "=" * 60, ""]

    for chunk in stats_result.chunks:
        meta = chunk.metadata
        name = meta.get("name", "Unknown")
        npc_id = meta.get("npc_id", "?")
        combat = meta.get("combat_level", 0)
        hp = meta.get("hitpoints", 0)
        members = meta.get("members", False)

        lines.append(f"{name}  (NPC ID: {npc_id})")
        lines.append(f"  Combat level: {combat}  |  HP: {hp}")
        if members:
            lines.append("  Members only")

        # Full details from document text
        lines.append(f"  {chunk.document[:300]}")

        # Append location data if available
        locations = location_map.get(name, [])
        if locations:
            lines.append("  Known locations:")
            for loc in locations[:3]:
                lm = loc.metadata
                x = lm.get("world_x", "?")
                y = lm.get("world_y", "?")
                z = lm.get("plane", 0)
                lines.append(f"    ({x}, {y}, {z})  →  new Tile({x}, {y}, {z})")
        else:
            lines.append("  Location: not available in spatial data")

        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]
