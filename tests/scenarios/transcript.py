"""Captured output of a single scenario run."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    result_text: str = ""


@dataclass
class Transcript:
    prompt: str
    final_text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_messages: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def tool_names(self) -> list[str]:
        return [c.name for c in self.tool_calls]

    def calls_for(self, name: str) -> list[ToolCall]:
        return [c for c in self.tool_calls if c.name == name]
