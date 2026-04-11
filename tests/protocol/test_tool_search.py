import pytest

from tests.protocol.conftest import extract_text, mcp_session


@pytest.mark.asyncio
async def test_dreambot_search_anchors():
    async with mcp_session() as client:
        # Bank.open
        r = await client.call_tool("dreambot_search", {"query": "Bank.open"})
        text = extract_text(r)
        assert "Bank" in text and "open" in text, f"missing Bank.open in: {text[:300]}"

        # Inventory.contains
        r = await client.call_tool("dreambot_search", {"query": "Inventory.contains"})
        text = extract_text(r)
        assert "Inventory" in text and "contains" in text

        # Walking.walk
        r = await client.call_tool("dreambot_search", {"query": "Walking.walk"})
        text = extract_text(r)
        assert "Walking" in text and "walk" in text

        # Empty query — must not crash the server
        r = await client.call_tool("dreambot_search", {"query": ""})
        assert r is not None
