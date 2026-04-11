import pytest

from tests.protocol.conftest import extract_text, mcp_session


@pytest.mark.asyncio
async def test_dreambot_member_anchors():
    async with mcp_session() as client:
        # Bank class — Bank.html in the bank package
        r = await client.call_tool(
            "dreambot_member",
            {
                "package": "org.dreambot.api.methods.container.impl.bank",
                "href": "Bank.html",
            },
        )
        text = extract_text(r)
        assert "open" in text
        assert "close" in text
