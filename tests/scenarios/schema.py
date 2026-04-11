"""Pydantic models for scenario YAML files."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolCallWith(BaseModel):
    name: str
    args_contain: dict[str, Any] = Field(default_factory=dict)


class Assertions(BaseModel):
    tool_called: list[str] = Field(default_factory=list)
    tool_not_called: list[str] = Field(default_factory=list)
    tool_call_count: dict[str, int] = Field(default_factory=dict)
    tool_called_with: list[ToolCallWith] = Field(default_factory=list)
    response_contains: list[str] = Field(default_factory=list)
    response_not_contains: list[str] = Field(default_factory=list)
    response_matches: list[str] = Field(default_factory=list)
    python_hook: str | None = None


class Judge(BaseModel):
    rubric: str
    model: str = "claude-sonnet-4-6"
    pass_threshold: int = 7


class Scenario(BaseModel):
    id: str
    description: str
    prompt: str
    assertions: Assertions = Field(default_factory=Assertions)
    judge: Judge | None = None
    timeout_seconds: int = 120
