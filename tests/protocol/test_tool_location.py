import pytest

from tests.protocol.conftest import extract_text, mcp_session


@pytest.mark.asyncio
async def test_dreambot_location_grand_exchange():
    async with mcp_session() as client:
        r = await client.call_tool(
            "dreambot_location",
            {"query": "Grand Exchange"},
        )
        text = extract_text(r)
        assert "grand exchange" in text.lower()


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=False,
    reason="Regression: 'Lumbridge bank' returns generic Lumbridge tile, not the bank tile (3208, 3220)",
)
async def test_dreambot_location_lumbridge_bank_returns_bank_tile():
    async with mcp_session() as client:
        r = await client.call_tool(
            "dreambot_location",
            {"query": "Lumbridge bank"},
        )
        text = extract_text(r)
        assert "3208" in text
        assert "3220" in text
