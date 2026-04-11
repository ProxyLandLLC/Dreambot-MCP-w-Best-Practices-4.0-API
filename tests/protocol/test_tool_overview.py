import pytest

from tests.protocol.conftest import extract_text, mcp_session


@pytest.mark.asyncio
async def test_dreambot_overview_anchors():
    async with mcp_session() as client:
        r = await client.call_tool("dreambot_overview", {})
        text = extract_text(r)
        assert "org.dreambot.api" in text
        # Historical QC reported ~115 packages; assert a generous floor.
        assert text.count("org.dreambot.api") >= 30
        assert "container.impl.bank" in text
        assert "walking" in text.lower()
