"""Tool base class and registry."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolContext:
    session_id: str
    message_id: str
    agent_id: str
    workdir: Path
    abort_event: asyncio.Event | None = None
    storage: Any = None
    memory: Any = None
    actor_manager: Any = None


@dataclass
class ExecuteResult:
    title: str
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    id: str = "base"
    description: str = ""

    @abstractmethod
    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ExecuteResult:
        ...

    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.id] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_all(self) -> list[Tool]:
        return list(self._tools.values())

    def filter_by_allowlist(self, allowlist: list[str] | None) -> list[Tool]:
        if allowlist is None:
            return self.list_all()
        return [t for t in self._tools.values() if t.id in allowlist]


def _truncate(s: str, max_len: int = 20000) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len] + f"\n... (truncated, {len(s)} total chars)"
