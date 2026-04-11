"""Helpers for protocol-layer MCP tests.

Uses an async context manager (not a pytest fixture) so the entire MCP session
lives inside a single asyncio task — required because anyio's task groups
inside the official `mcp` stdio client cannot be entered and exited from
different tasks, which is what pytest-asyncio's async-generator fixtures do.
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_SCRIPT = REPO_ROOT / "server.py"


@asynccontextmanager
async def mcp_session():
    """Yield a connected, initialized MCP ClientSession against server.py."""
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        cwd=str(REPO_ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def extract_text(result) -> str:
    """Concatenate all text content blocks from an MCP CallToolResult."""
    parts = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)
