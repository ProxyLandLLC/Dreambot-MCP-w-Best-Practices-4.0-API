"""
Converts Explv OSRS map URLs or raw tile coordinates into DreamBot code snippets.

The Explv map (https://explv.github.io/) stores OSRS tile coordinates directly
as URL query parameters (centreX, centreY, centreZ), which are identical to
DreamBot's Tile(x, y, z) constructor arguments. No conversion is needed.
"""
from urllib.parse import urlparse, parse_qs
from mcp.types import TextContent


async def handle_dreambot_tile_tool(arguments: dict) -> list[TextContent]:
    url = arguments.get("url", "").strip()
    x_raw = arguments.get("x")
    y_raw = arguments.get("y")
    z_raw = arguments.get("z", 0)

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
    elif x_raw is not None and y_raw is not None:
        try:
            x, y, z = int(x_raw), int(y_raw), int(z_raw or 0)
        except (ValueError, TypeError):
            return [TextContent(type="text", text="Error: x, y, z must be integers.")]
    else:
        return [TextContent(type="text", text=(
            "Error: provide 'url' (Explv map URL) or 'x' and 'y' integer coordinates.\n"
            "Example: url='https://explv.github.io/?centreX=2916&centreY=3311&centreZ=0&zoom=7'"
        ))]

    r = 15  # default area radius in tiles
    explv_url = f"https://explv.github.io/?centreX={x}&centreY={y}&centreZ={z}&zoom=7"

    lines = [
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
    ]

    return [TextContent(type="text", text="\n".join(lines))]
