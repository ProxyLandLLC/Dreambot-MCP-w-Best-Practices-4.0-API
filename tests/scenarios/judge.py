"""LLM judge for scenario quality grading."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    query,
)

from tests.scenarios.schema import Judge


@dataclass
class JudgeVerdict:
    passed: bool
    score: int
    reasoning: str
    error: str | None = None


JUDGE_SYSTEM = (
    "You are an impartial grader evaluating a DreamBot OSRS scripting "
    "assistant's response. Read the user prompt, the assistant's final "
    "response, and the rubric. Reply with a single JSON object: "
    '{"score": <0-10 integer>, "reasoning": "<one paragraph>"}. '
    "No prose outside the JSON."
)


async def run_judge(judge_cfg: Judge, prompt: str, final_response: str) -> JudgeVerdict:
    judge_prompt = (
        f"USER PROMPT:\n{prompt}\n\n"
        f"ASSISTANT RESPONSE:\n{final_response}\n\n"
        f"RUBRIC:\n{judge_cfg.rubric}\n\n"
        "Return JSON only."
    )

    options = ClaudeAgentOptions(
        system_prompt=JUDGE_SYSTEM,
        model=judge_cfg.model,
        permission_mode="bypassPermissions",
    )

    text_out = ""
    try:
        async for message in query(prompt=judge_prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_out += block.text
    except Exception as e:
        return JudgeVerdict(False, 0, "", error=f"{type(e).__name__}: {e}")

    match = re.search(r"\{.*\}", text_out, re.DOTALL)
    if not match:
        return JudgeVerdict(False, 0, text_out, error="no JSON in judge output")
    try:
        data = json.loads(match.group(0))
        score = int(data.get("score", 0))
        reasoning = str(data.get("reasoning", ""))
    except Exception as e:
        return JudgeVerdict(False, 0, text_out, error=f"json parse: {e}")

    return JudgeVerdict(
        passed=score >= judge_cfg.pass_threshold,
        score=score,
        reasoning=reasoning,
    )
