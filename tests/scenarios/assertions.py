"""Structural assertion engine for scenario transcripts."""
from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from pathlib import Path

from tests.scenarios.schema import Assertions
from tests.scenarios.transcript import Transcript


@dataclass
class AssertionResult:
    name: str
    passed: bool
    message: str = ""


def run_assertions(
    assertions: Assertions,
    transcript: Transcript,
    hooks_root: Path | None = None,
) -> list[AssertionResult]:
    results: list[AssertionResult] = []

    for tool in assertions.tool_called:
        if tool in transcript.tool_names():
            results.append(AssertionResult(f"tool_called:{tool}", True))
        else:
            results.append(
                AssertionResult(
                    f"tool_called:{tool}",
                    False,
                    f"expected call to {tool}, got {transcript.tool_names()}",
                )
            )

    for tool in assertions.tool_not_called:
        if tool not in transcript.tool_names():
            results.append(AssertionResult(f"tool_not_called:{tool}", True))
        else:
            results.append(
                AssertionResult(
                    f"tool_not_called:{tool}",
                    False,
                    f"unexpected call to {tool}",
                )
            )

    for tool, expected in assertions.tool_call_count.items():
        actual = len(transcript.calls_for(tool))
        passed = actual == expected
        msg = "" if passed else f"expected {expected} calls to {tool}, got {actual}"
        results.append(AssertionResult(f"tool_call_count:{tool}", passed, msg))

    for spec in assertions.tool_called_with:
        calls = transcript.calls_for(spec.name)
        matched = any(
            all(call.args.get(k) == v for k, v in spec.args_contain.items())
            for call in calls
        )
        msg = "" if matched else f"no call to {spec.name} matched args {spec.args_contain}"
        results.append(AssertionResult(f"tool_called_with:{spec.name}", matched, msg))

    for needle in assertions.response_contains:
        passed = needle in transcript.final_text
        msg = "" if passed else f"missing substring {needle!r}"
        results.append(AssertionResult(f"response_contains:{needle}", passed, msg))

    for needle in assertions.response_not_contains:
        passed = needle not in transcript.final_text
        msg = "" if passed else f"forbidden substring {needle!r} present"
        results.append(AssertionResult(f"response_not_contains:{needle}", passed, msg))

    for pattern in assertions.response_matches:
        passed = re.search(pattern, transcript.final_text) is not None
        msg = "" if passed else f"regex {pattern!r} did not match"
        results.append(AssertionResult(f"response_matches:{pattern}", passed, msg))

    if assertions.python_hook:
        try:
            module = importlib.import_module(
                f"tests.scenarios.hooks.{assertions.python_hook}"
            )
            hook_results = module.check(transcript)
            results.extend(hook_results)
        except Exception as e:
            results.append(
                AssertionResult(
                    f"python_hook:{assertions.python_hook}",
                    False,
                    f"hook error: {type(e).__name__}: {e}",
                )
            )

    return results
