import re

import pytest

from tests.protocol.conftest import extract_text, mcp_session


@pytest.mark.asyncio
async def test_dreambot_npc_cow_present():
    async with mcp_session() as client:
        r = await client.call_tool("dreambot_npc", {"query": "cow"})
        text = extract_text(r)
        assert "Cow" in text or "cow" in text


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=False,
    reason="Regression: 'goblin' query may only return level-0 non-combat goblins, missing combat-level (2-5) variants",
)
async def test_dreambot_npc_goblin_combat_level_present():
    async with mcp_session() as client:
        r = await client.call_tool("dreambot_npc", {"query": "goblin"})
        text = extract_text(r)
        # Combat-level goblin should mention level 2..5 in proximity to "Goblin"
        assert re.search(r"Goblin.{0,80}[2-5]", text, re.IGNORECASE | re.DOTALL)
