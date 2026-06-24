"""Built-in agent definitions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentDef:
    name: str
    description: str
    mode: str = "primary"  # primary | subagent
    model: str | None = None
    prompt: str = ""
    tool_allowlist: list[str] | None = None
    temperature: float = 0.7
    color: str = "cyan"
    hidden: bool = False


DEFAULT_AGENTS: dict[str, AgentDef] = {
    "build": AgentDef(
        name="build",
        description="Main execution agent with full tool access",
        mode="primary",
        prompt=(
            "You are HelloCode, an AI coding assistant running in a terminal. "
            "You help users with software engineering tasks: writing code, fixing bugs, "
            "refactoring, explaining code, and more. "
            "Be concise and direct. Use tools to complete tasks. "
            "After completing a task, run lint/typecheck if available."
        ),
        color="green",
    ),
    "plan": AgentDef(
        name="plan",
        description="Read-only analysis agent for planning",
        mode="primary",
        prompt="You are a planning agent. Analyze code and create implementation plans. Be read-only.",
        tool_allowlist=["read", "glob", "grep", "bash"],
        color="blue",
    ),
    "explore": AgentDef(
        name="explore",
        description="Fast code exploration subagent",
        mode="subagent",
        prompt="You are a code exploration agent. Find files, search code, answer questions about the codebase. Be concise.",
        tool_allowlist=["read", "glob", "grep", "bash"],
        color="magenta",
        hidden=True,
    ),
    "title": AgentDef(
        name="title",
        description="Generate session titles",
        mode="subagent",
        prompt="Generate a short session title (max 8 words) based on the conversation.",
        tool_allowlist=[],
        color="yellow",
        hidden=True,
    ),
    "summary": AgentDef(
        name="summary",
        description="Generate session summaries",
        mode="subagent",
        prompt="Generate a concise session summary.",
        tool_allowlist=[],
        color="yellow",
        hidden=True,
    ),
    "compaction": AgentDef(
        name="compaction",
        description="Context compaction agent",
        mode="subagent",
        prompt="Compress conversation history into a concise summary preserving key facts.",
        tool_allowlist=[],
        color="yellow",
        hidden=True,
    ),
    "checkpoint-writer": AgentDef(
        name="checkpoint-writer",
        description="Write checkpoint files",
        mode="subagent",
        prompt="Write session checkpoint and memory files.",
        tool_allowlist=["read", "write", "edit"],
        color="yellow",
        hidden=True,
    ),
}
