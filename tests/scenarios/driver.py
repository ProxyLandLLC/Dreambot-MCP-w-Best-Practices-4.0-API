"""Drive a single scenario through the Claude Agent SDK.

Uses ClaudeSDKClient (not the one-shot `query` helper) so we can wait for the
dreambot MCP server to reach status=`connected` before sending the scenario
prompt. Otherwise Claude races ahead, the tool isn't registered yet, and the
session falls back to built-in tools.
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from tests.scenarios.schema import Scenario
from tests.scenarios.transcript import ToolCall, Transcript

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_FILE = REPO_ROOT / "dreambot-scripting" / "SKILL.md"
SERVER_SCRIPT = REPO_ROOT / "server.py"

DREAMBOT_TOOL_NAMES = (
    "dreambot_search",
    "dreambot_overview",
    "dreambot_package",
    "dreambot_member",
    "dreambot_tile",
    "dreambot_location",
    "dreambot_item",
    "dreambot_npc",
)

MCP_SERVER_NAME = "dreambot"
MCP_CONNECT_TIMEOUT_SECONDS = 60.0
MCP_POLL_INTERVAL_SECONDS = 0.5


def _strip_frontmatter(text: str) -> str:
    match = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    return text[match.end() :] if match else text


def _load_skill_text() -> str:
    raw = SKILL_FILE.read_text(encoding="utf-8")
    return _strip_frontmatter(raw).strip()


def _mcp_tool_name(tool_name: str) -> str:
    return f"mcp__{MCP_SERVER_NAME}__{tool_name}"


def _strip_mcp_prefix(name: str) -> str:
    prefix = f"mcp__{MCP_SERVER_NAME}__"
    return name[len(prefix) :] if name.startswith(prefix) else name


def _build_options() -> ClaudeAgentOptions:
    skill_text = _load_skill_text()
    system_prompt = (
        "You are a DreamBot OSRS scripting assistant using the DreamBot API 4.0.\n"
        "Always prefer the dreambot_* MCP tools to look up real API signatures, "
        "item IDs, NPC data, and map coordinates rather than guessing.\n\n"
        "## Skill: dreambot-scripting\n\n"
        + skill_text
    )
    allowed_tools = [_mcp_tool_name(n) for n in DREAMBOT_TOOL_NAMES]
    return ClaudeAgentOptions(
        system_prompt=system_prompt,
        mcp_servers={
            MCP_SERVER_NAME: {
                "type": "stdio",
                "command": sys.executable,
                "args": [str(SERVER_SCRIPT)],
                "env": {},
            }
        },
        allowed_tools=allowed_tools,
        permission_mode="bypassPermissions",
        setting_sources=[],
        cwd=str(REPO_ROOT),
        extra_args={"strict-mcp-config": None},
    )


async def _wait_for_mcp_connected(client: ClaudeSDKClient) -> bool:
    """Poll get_mcp_status() until the dreambot server is connected.

    McpStatusResponse is a TypedDict: {'mcpServers': [McpServerStatus, ...]}
    Each McpServerStatus has 'name' and 'status' string fields.
    """
    deadline = asyncio.get_event_loop().time() + MCP_CONNECT_TIMEOUT_SECONDS
    while asyncio.get_event_loop().time() < deadline:
        try:
            status = await client.get_mcp_status()
        except Exception:
            await asyncio.sleep(MCP_POLL_INTERVAL_SECONDS)
            continue
        servers = status.get("mcpServers", []) if isinstance(status, dict) else []
        for server in servers:
            if server.get("name") == MCP_SERVER_NAME:
                state = server.get("status")
                if state == "connected":
                    return True
                if state == "failed":
                    return False
        await asyncio.sleep(MCP_POLL_INTERVAL_SECONDS)
    return False


async def run_scenario(scenario: Scenario) -> Transcript:
    transcript = Transcript(prompt=scenario.prompt)
    options = _build_options()

    try:
        async with asyncio.timeout(scenario.timeout_seconds):
            async with ClaudeSDKClient(options=options) as client:
                connected = await _wait_for_mcp_connected(client)
                if not connected:
                    transcript.error = "dreambot MCP server did not connect"
                    return transcript

                await client.query(scenario.prompt)

                async for message in client.receive_response():
                    mtype = type(message).__name__
                    transcript.raw_messages.append({"type": mtype})
                    print(f"  [driver] {mtype}", file=sys.stderr, flush=True)
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            btype = type(block).__name__
                            if isinstance(block, TextBlock):
                                transcript.final_text += block.text
                                print(
                                    f"  [driver]   text: {block.text[:120]!r}",
                                    file=sys.stderr,
                                    flush=True,
                                )
                            elif isinstance(block, ToolUseBlock):
                                name = _strip_mcp_prefix(block.name)
                                transcript.tool_calls.append(
                                    ToolCall(name=name, args=dict(block.input))
                                )
                                print(
                                    f"  [driver]   tool_use: {name} {dict(block.input)}",
                                    file=sys.stderr,
                                    flush=True,
                                )
                            else:
                                print(f"  [driver]   block: {btype}", file=sys.stderr, flush=True)
                    elif isinstance(message, ResultMessage):
                        print("  [driver] ResultMessage -> break", file=sys.stderr, flush=True)
                        break
    except asyncio.TimeoutError:
        transcript.error = f"timeout after {scenario.timeout_seconds}s"
    except Exception as e:
        transcript.error = f"driver error: {type(e).__name__}: {e}"

    return transcript
