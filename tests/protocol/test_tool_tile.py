import pytest

from tests.protocol.conftest import extract_text, mcp_session


@pytest.mark.asyncio
async def test_dreambot_tile_anchors():
    async with mcp_session() as client:
        # Raw coordinates — Draynor bank tile
        r = await client.call_tool(
            "dreambot_tile",
            {"x": 3092, "y": 3245, "z": 0},
        )
        text = extract_text(r)
        assert "3092" in text
        assert "3245" in text
        assert "Tile" in text

        # Explv URL parsing
        r = await client.call_tool(
            "dreambot_tile",
            {"url": "https://explv.github.io/?centreX=3208&centreY=3220&centreZ=0&zoom=11"},
        )
        text = extract_text(r)
        assert "3208" in text
        assert "3220" in text
