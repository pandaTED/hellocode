"""Tool package - exports all built-in tools."""

from .base import Tool, ToolRegistry, ToolContext, ExecuteResult
from .builtin import (
    ReadTool, WriteTool, EditTool, GlobTool, GrepTool,
    BashTool, ChangeDirectoryTool, WebfetchTool, QuestionTool,
    TaskTool, ActorTool, MemoryTool, WorkflowTool, SkillTool,
    NotebookEditTool, ApplyPatchTool,
)

ALL_TOOLS = [
    ReadTool(), WriteTool(), EditTool(), GlobTool(), GrepTool(),
    BashTool(), ChangeDirectoryTool(), WebfetchTool(), QuestionTool(),
    TaskTool(), ActorTool(), MemoryTool(), WorkflowTool(), SkillTool(),
    NotebookEditTool(), ApplyPatchTool(),
]


def create_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for t in ALL_TOOLS:
        reg.register(t)
    return reg


__all__ = [
    "Tool", "ToolRegistry", "ToolContext", "ExecuteResult",
    "ALL_TOOLS", "create_registry",
]
