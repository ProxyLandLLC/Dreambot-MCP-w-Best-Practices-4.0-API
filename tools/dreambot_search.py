from mcp.types import TextContent
from tools.search_engine import SearchEngine


async def handle_dreambot_search_tool(
    arguments: dict, engine: SearchEngine
) -> list[TextContent]:
    query = arguments.get("query", "").strip()
    if not query:
        return [TextContent(type="text", text="Error: 'query' parameter is required.")]

    try:
        top_k = int(arguments.get("top_k", 8))
        if top_k < 1:
            top_k = 8
    except (ValueError, TypeError):
        top_k = 8
    results = engine.search(query, top_k=top_k)

    if not results:
        return [TextContent(
            type="text",
            text=(
                f"No methods found matching '{query}'. "
                "Try a more specific keyword (e.g., class name like 'Bank', or method name like 'isOpen'). "
                "Semantic search requires 'sentence-transformers' to be installed."
            ),
        )]

    lines = [f"Search results for: '{query}'", "=" * 60, ""]
    for method in results:
        lines.append(f"[{method['class_name']}]  {method['method_signature']}")
        if method.get("description"):
            lines.append(f"  -> {method['description']}")
        lines.append(f"  Package: {method['package']}")
        lines.append(
            f"  (Full class: dreambot_member(package='{method['package']}', "
            f"href='{method['href']}'))"
        )
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]
