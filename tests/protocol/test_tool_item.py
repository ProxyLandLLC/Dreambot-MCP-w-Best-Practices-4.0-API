import pytest

from tests.protocol.conftest import extract_text, mcp_session


@pytest.mark.asyncio
async def test_dreambot_item_anchors():
    async with mcp_session() as client:
        # Lobster — id 379
        r = await client.call_tool("dreambot_item", {"query": "lobster"})
        text = extract_text(r)
        assert "Lobster" in text
        assert "379" in text

        # Shark — id 385
        r = await client.call_tool("dreambot_item", {"query": "shark"})
        text = extract_text(r)
        assert "Shark" in text or "shark" in text

        # Unknown item — must not crash
        r = await client.call_tool(
            "dreambot_item",
            {"query": "asdfqwerxyz_not_an_item"},
        )
        assert r is not None
