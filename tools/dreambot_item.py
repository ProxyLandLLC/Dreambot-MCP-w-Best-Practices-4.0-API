"""
dreambot_item — Look up OSRS item data: IDs, stats, equipment bonuses, requirements.
Queries the game_data collection filtered to item chunks.
"""

from mcp.types import TextContent
from rag.retriever import Retriever


async def handle_dreambot_item_tool(
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
        force_collections=["game_data"],
        extra_filters={"game_data": {"chunk_type": "item"}},
        top_k=top_k,
    )

    if not result.chunks:
        return [TextContent(
            type="text",
            text=f"No items found matching '{query}'. Try a different name or description.",
        )]

    lines = [f"Item results for: '{query}'", "=" * 60, ""]

    for chunk in result.chunks:
        meta = chunk.metadata
        name = meta.get("name", "Unknown")
        item_id = meta.get("item_id", "?")
        tradeable = meta.get("tradeable", False)
        equipable = meta.get("equipable", False)
        slot = meta.get("slot", "")
        members = meta.get("members", False)
        quest_req = meta.get("quest_req", "")

        lines.append(f"{name}  (ID: {item_id})")

        # Tags line
        tags = []
        if tradeable:
            tags.append("Tradeable")
        if equipable:
            tags.append(f"Equipable ({slot})" if slot else "Equipable")
        if members:
            tags.append("Members")
        if tags:
            lines.append(f"  [{', '.join(tags)}]")

        if quest_req:
            lines.append(f"  Quest requirements: {quest_req}")

        # Full details from document text
        lines.append(f"  {chunk.document[:300]}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]
