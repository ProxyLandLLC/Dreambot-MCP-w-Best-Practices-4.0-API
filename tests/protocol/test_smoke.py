import pytest

from tests.protocol.conftest import mcp_session


@pytest.mark.asyncio
async def test_server_lists_tools():
    async with mcp_session() as client:
        result = await client.list_tools()
        names = {t.name for t in result.tools}
        assert "dreambot_search" in names
        assert len(names) >= 8
