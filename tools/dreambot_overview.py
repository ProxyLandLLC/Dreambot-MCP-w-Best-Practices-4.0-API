import requests
from bs4 import BeautifulSoup
from mcp.types import TextContent


async def handle_dreambot_overview_tool():
    """
    Fetches the DreamBot API package list.
    Updated for API 4.0 JavaDocs format (allpackages-index.html, table.packagesSummary).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
    }

    # API 4.0 uses allpackages-index.html (overview-summary.html redirects via JS)
    url = "https://dreambot.org/javadocs/allpackages-index.html"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        packages = []

        # API 4.0 format: table.packagesSummary, package names in th.colFirst > a
        table = soup.find("table", {"class": "packagesSummary"})
        if table:
            for th in table.find_all("th", {"class": "colFirst"}):
                a = th.find("a")
                if a:
                    packages.append(a.get_text(strip=True))

        # Fallback: API 3.0 format (table.overviewSummary)
        if not packages:
            table = soup.find("table", {"class": "overviewSummary"})
            if table:
                for row in table.find_all("tr"):
                    a = row.find("a")
                    if a and a.get_text(strip=True):
                        packages.append(a.get_text(strip=True))

        if packages:
            lines = ["DreamBot API 4.0 — Package List", "=" * 40]
            lines.extend(f"  {pkg}" for pkg in packages)
            lines.append(f"\nTotal: {len(packages)} packages")
            return [TextContent(type="text", text="\n".join(lines))]

        return [TextContent(
            type="text",
            text="No packages found. The JavaDocs page structure may have changed."
        )]

    except requests.RequestException as e:
        return [TextContent(type="text", text=f"Network error fetching package overview: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error parsing package overview: {e}")]
