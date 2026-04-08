import os

import requests
from bs4 import BeautifulSoup
from mcp.types import TextContent

_HERE = os.path.dirname(os.path.abspath(__file__))
_MCP_ROOT = os.path.dirname(_HERE)
_LOCAL_HTML_DIR = os.path.join(_MCP_ROOT, "API v4", "html files")


def _local_html_path(package: str, href: str) -> str:
    """Return path to locally-stored HTML file for this class, or '' if not found."""
    class_name = href.replace(".html", "")
    key = package.replace(".", "_") + "_" + class_name
    path = os.path.join(_LOCAL_HTML_DIR, key + ".html")
    return path if os.path.exists(path) else ""


async def handle_dreambot_member_tool(arguments: dict):
    """
    Fetches method/field documentation for a specific class in the DreamBot API.
    Updated for API 4.0 JavaDocs format (table.memberSummary).

    Args:
        arguments: dict with keys:
            'package' — e.g. 'org.dreambot.api.methods.container.impl.bank'
            'href'    — e.g. 'Bank.html'
    """
    package = arguments.get("package")
    href = arguments.get("href")

    if not package:
        return [TextContent(type="text", text="Error: 'package' parameter is required.")]
    if not href:
        return [TextContent(
            type="text",
            text=(
                "Error: 'href' parameter is required.\n"
                "Use dreambot_package first to get the href for each class (e.g. 'Bank.html')."
            )
        )]

    local_path = _local_html_path(package, href)
    source_label = "local"

    try:
        if local_path:
            with open(local_path, encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
        else:
            package_path = package.replace(".", "/")
            url = f"https://dreambot.org/javadocs/{package_path}/{href}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 404:
                return [TextContent(
                    type="text",
                    text=f"Class '{package}/{href}' not found (404). Check the package and href are correct."
                )]
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            source_label = "web"

        results = []

        # Class title
        title_el = soup.find("h2", {"class": "title"})
        if title_el:
            results.append(title_el.get_text(strip=True))

        # Class hierarchy / extends
        inheritance = soup.find("ul", {"class": "inheritance"})
        if inheritance:
            classes = [li.get_text(strip=True) for li in inheritance.find_all("li") if li.get_text(strip=True)]
            if len(classes) > 1:
                results.append(f"Extends: {' -> '.join(classes)}")

        results.append("")

        # API 4.0: method summary in table.memberSummary
        method_table = soup.find("table", {"class": "memberSummary"})
        if method_table:
            results.append("Method Summary:")
            results.append("-" * 60)

            for row in method_table.find_all("tr"):
                modifier_td = row.find("td", {"class": "colFirst"})
                name_th = row.find("th", {"class": "colSecond"})
                desc_td = row.find("td", {"class": "colLast"})

                if not (modifier_td and name_th):
                    continue

                modifier = modifier_td.get_text(strip=True)
                name_link = name_th.find("span", {"class": "memberNameLink"})
                if not name_link:
                    continue

                # Full method signature including params
                full_sig = name_th.find("code")
                method_text = full_sig.get_text(strip=True) if full_sig else name_link.get_text(strip=True)

                desc = ""
                if desc_td:
                    block = desc_td.find("div", {"class": "block"})
                    desc = block.get_text(strip=True) if block else ""

                line = f"  [{modifier}] {method_text}"
                if desc:
                    line += f"\n    -> {desc}"
                results.append(line)

        # Fallback: old 'details' div format (API 3.0)
        if not method_table:
            details = soup.find("div", {"class": "details"})
            if details:
                results.append("Method Details:")
                results.append("-" * 60)
                for li in details.find_all("li", recursive=False):
                    results.append(f"  {li.get_text(strip=True)[:300]}")

        if results and len(results) > 2:
            results.append(f"\n[Source: {source_label}]")
            return [TextContent(type="text", text="\n".join(results))]

        return [TextContent(
            type="text",
            text=f"No documentation found for '{package}/{href}'. The class may have no public methods."
        )]

    except requests.RequestException as e:
        return [TextContent(type="text", text=f"Network error fetching '{package}/{href}': {e}")]
    except OSError as e:
        return [TextContent(type="text", text=f"Error reading local file for '{package}/{href}': {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error parsing '{package}/{href}': {e}")]
