"""
dreambot_search — Primary search tool. Enhanced to use RAG retriever
with intent routing across collections, falling back to legacy SearchEngine.
"""

from mcp.types import TextContent


async def handle_dreambot_search_tool(
    arguments: dict, engine_or_retriever
) -> list[TextContent]:
    """
    Handles dreambot_search. Accepts either a legacy SearchEngine
    or a RAG Retriever instance.
    """
    query = arguments.get("query", "").strip()
    if not query:
        return [TextContent(type="text", text="Error: 'query' parameter is required.")]

    try:
        top_k = int(arguments.get("top_k", 8))
        if top_k < 1:
            top_k = 8
    except (ValueError, TypeError):
        top_k = 8

    # Check if we have a RAG Retriever or legacy SearchEngine
    from rag.retriever import Retriever
    if isinstance(engine_or_retriever, Retriever):
        return await _search_rag(query, top_k, engine_or_retriever)
    else:
        return _search_legacy(query, top_k, engine_or_retriever)


async def _search_rag(query: str, top_k: int, retriever) -> list[TextContent]:
    """RAG-powered search with intent routing."""
    result = await retriever.retrieve(query=query, top_k=top_k)

    if not result.chunks:
        return [TextContent(
            type="text",
            text=(
                f"No results found matching '{query}'. "
                "Try a more specific keyword (e.g., class name like 'Bank', "
                "or method name like 'isOpen')."
            ),
        )]

    lines = [f"Search results for: '{query}'", "=" * 60, ""]

    # Use the formatted context from the retriever
    lines.append(result.text)

    # Add drill-down hint for API method results
    api_chunks = result.sections.get("api_methods", [])
    if api_chunks:
        classes = set()
        for chunk in api_chunks:
            cls = chunk.metadata.get("class_name", "")
            pkg = chunk.metadata.get("package", "")
            href = chunk.metadata.get("href", "")
            if cls and pkg and href:
                classes.add((cls, pkg, href))

        if classes:
            lines.append("")
            lines.append("Drill down with dreambot_member:")
            for cls, pkg, href in list(classes)[:3]:
                lines.append(f"  dreambot_member(package='{pkg}', href='{href}')")

    return [TextContent(type="text", text="\n".join(lines))]


def _search_legacy(query: str, top_k: int, engine) -> list[TextContent]:
    """Legacy SearchEngine fallback (pre-RAG)."""
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
