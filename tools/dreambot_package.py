"""
dreambot_package — Fetches class/interface/enum listing for a DreamBot package.
Enhanced with RAG to show method count and description per class.
"""

import requests
from bs4 import BeautifulSoup
from mcp.types import TextContent


async def handle_dreambot_package_tool(arguments: dict, retriever=None):
    """
    Fetches the class/interface/enum listing for a specific DreamBot package.
    When retriever is available, enriches each class with method count and
    one-line description from the api_methods collection.

    Args:
        arguments: dict with key 'package'
        retriever: optional Retriever instance for RAG enrichment
    """
    package = arguments.get("package")
    if not package:
        return [TextContent(
            type="text",
            text=(
                "Error: 'package' parameter is required.\n"
                "Example: org.dreambot.api.methods.container.impl.bank\n\n"
                "Use dreambot_overview first to browse available packages."
            )
        )]

    package_path = package.replace(".", "/")
    url = f"https://dreambot.org/javadocs/{package_path}/package-summary.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 404:
            return [TextContent(
                type="text",
                text=f"Package '{package}' not found (404). Check the package name is correct."
            )]
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Build RAG enrichment map if available
        rag_info: dict[str, dict] = {}
        if retriever:
            try:
                result = await retriever.retrieve(
                    query=package,
                    force_collections=["api_methods"],
                    extra_filters={"api_methods": {
                        "$and": [
                            {"chunk_type": "class_overview"},
                            {"package": package},
                        ]
                    }},
                    top_k=50,
                )
                for chunk in result.chunks:
                    cls_name = chunk.metadata.get("class_name", "")
                    if cls_name:
                        rag_info[cls_name] = {
                            "method_count": chunk.metadata.get("method_count", 0),
                            "description": chunk.document[:150],
                        }
            except Exception:
                pass  # Fall through to scrape-only output

        results = [f"Package: {package}", "=" * 60]

        tables = soup.find_all("table", {"class": "typeSummary"})

        for table in tables:
            caption = table.find("caption")
            if caption:
                section_name = caption.get_text(strip=True).replace("\xa0", "").strip()
            else:
                section_name = "Types"

            entries = []
            for th in table.find_all("th", {"class": "colFirst"}):
                a = th.find("a")
                if not a:
                    continue
                href = a.get("href", "")
                name = a.get_text(strip=True)

                row = th.parent
                desc_td = row.find("td", {"class": "colLast"})
                desc = ""
                if desc_td:
                    block = desc_td.find("div", {"class": "block"})
                    desc = block.get_text(strip=True) if block else desc_td.get_text(strip=True)

                entry = f"  {name} (href: {href})"

                # RAG enrichment: method count
                enrichment = rag_info.get(name, {})
                method_count = enrichment.get("method_count", 0)
                if method_count:
                    entry += f"  [{method_count} methods]"

                if desc:
                    entry += f"\n    {desc}"
                elif enrichment.get("description"):
                    entry += f"\n    {enrichment['description']}"
                entries.append(entry)

            if entries:
                results.append(f"\n{section_name}:")
                results.extend(entries)

        if len(results) > 2:
            results.append(
                f"\nUse dreambot_member with package='{package}' and href='ClassName.html' "
                "to see method signatures."
            )
            return [TextContent(type="text", text="\n".join(results))]

        return [TextContent(
            type="text",
            text=f"No types found in package '{package}'. The package may be empty or the name may be incorrect."
        )]

    except requests.RequestException as e:
        return [TextContent(type="text", text=f"Network error fetching package '{package}': {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error parsing package '{package}': {e}")]
