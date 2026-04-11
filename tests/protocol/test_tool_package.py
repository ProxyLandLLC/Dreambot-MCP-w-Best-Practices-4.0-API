import pytest

from tests.protocol.conftest import extract_text, mcp_session


@pytest.mark.asyncio
async def test_dreambot_package_anchors():
    async with mcp_session() as client:
        # Known package — bank classes
        r = await client.call_tool(
            "dreambot_package",
            {"package": "org.dreambot.api.methods.container.impl.bank"},
        )
        text = extract_text(r)
        for cls in ("Bank", "BankLocation", "BankMode"):
            assert cls in text, f"missing class {cls} in: {text[:400]}"

        # Unknown package — must not crash
        r = await client.call_tool(
            "dreambot_package",
            {"package": "org.dreambot.api.nonsense.fake"},
        )
        assert r is not None
