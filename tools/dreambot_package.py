import requests
from bs4 import BeautifulSoup
from mcp.types import TextContent


async def handle_dreambot_package_tool(arguments: dict):
    """
    Fetches the class/interface/enum listing for a specific DreamBot package.
    Updated for API 4.0 JavaDocs format (table.typeSummary, th.colFirst > a).

    Args:
        arguments: dict with key 'package' — e.g. 'org.dreambot.api.methods.container.impl.bank'
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

        results = [f"Package: {package}", "=" * 60]

        # API 4.0: type summary tables use class 'typeSummary'
        # Each section (Class Summary, Enum Summary, Interface Summary) is a separate table
        tables = soup.find_all("table", {"class": "typeSummary"})

        if not tables:
            # Fallback: try older format
            tables = soup.find_all("table", {"class": "typeSummary"})

        for table in tables:
            caption = table.find("caption")
            if caption:
                # Caption text is like "Class Summary\xa0" — clean it up
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

                # Description from the adjacent colLast td
                row = th.parent
                desc_td = row.find("td", {"class": "colLast"})
                desc = ""
                if desc_td:
                    block = desc_td.find("div", {"class": "block"})
                    desc = block.get_text(strip=True) if block else desc_td.get_text(strip=True)

                entry = f"  {name} (href: {href})"
                if desc:
                    entry += f"\n    {desc}"
                entries.append(entry)

            if entries:
                results.append(f"\n{section_name}:")
                results.extend(entries)

        if len(results) > 2:  # more than just the header lines
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
