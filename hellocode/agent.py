"""Agent autonomous loop - the core execution engine."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("hellocode.agent")

from .agents import AgentDef, DEFAULT_AGENTS
from .config import Config
from .memory import MemorySystem
from .provider import LLMProvider
from .storage import Storage
from .tools.base import ToolContext, ToolRegistry


class AgentLoop:
    def __init__(
        self,
        config: Config,
        storage: Storage,
        provider: LLMProvider,
        tools: ToolRegistry,
        memory: MemorySystem,
    ):
        self.config = config
        self.storage = storage
        self.provider = provider
        self.tools = tools
        self.memory = memory
        self.actor_manager: ActorManager | None = None
        self._abort_events: dict[str, set[asyncio.Event]] = {}

    def abort(self, session_id: str | None = None) -> None:
        if session_id:
            for evt in list(self._abort_events.get(session_id, ())):
                evt.set()
        else:
            for events in list(self._abort_events.values()):
                for evt in list(events):
                    evt.set()

    async def run(
        self,
        session_id: str,
        user_input: str,
        agent_name: str = "build",
        workdir: Path | None = None,
        on_tool_call: Any = None,
        on_tool_result: Any = None,
        on_message: Any = None,
    ) -> str:
        abort = asyncio.Event()
        self._abort_events.setdefault(session_id, set()).add(abort)
        try:
            return await self._run_inner(
                session_id, user_input, agent_name, workdir,
                on_tool_call, on_tool_result, on_message, abort,
            )
        finally:
            events = self._abort_events.get(session_id)
            if events:
                events.discard(abort)
                if not events:
                    self._abort_events.pop(session_id, None)

    async def _run_inner(
        self,
        session_id: str,
        user_input: str,
        agent_name: str,
        workdir: Path | None,
        on_tool_call: Any,
        on_tool_result: Any,
        on_message: Any,
        abort: asyncio.Event,
    ) -> str:
        agent_def = DEFAULT_AGENTS.get(agent_name) or AgentDef(name=agent_name, description="", mode="primary")
        agent_model = self.config.get_provider_model(agent_name)
        temperature = agent_def.temperature
        agent_config = self.config.agent.get(agent_name)
        max_tokens = (agent_config.max_tokens if agent_config and agent_config.max_tokens else None) \
            or self.config.get_provider_max_tokens() or 32768

        cwd = workdir or Path.cwd()
        ctx = ToolContext(
            session_id=session_id,
            message_id="",
            agent_id=agent_name,
            workdir=cwd,
            storage=self.storage,
            memory=self.memory,
            actor_manager=self.actor_manager,
        )

        system_prompt = self._build_system_prompt(agent_def, session_id, workdir or Path.cwd(), user_input)
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        # Load previous conversation history from storage
        prev_messages = self.storage.list_messages(session_id, limit=200)
        # Truncate to last ~50k chars of content to stay within context limits
        total_chars = 0
        MAX_HISTORY_CHARS = 50000
        trimmed_messages: list[dict] = []
        for pm in reversed(prev_messages):
            data = pm.get("data", {})
            content_len = len(str(data.get("content", "")))
            if total_chars + content_len > MAX_HISTORY_CHARS and trimmed_messages:
                break
            total_chars += content_len
            trimmed_messages.append(pm)
        trimmed_messages.reverse()
        for pm in trimmed_messages:
            data = pm.get("data", {})
            role = data.get("role", "")
            if not role:
                continue
            if role == "assistant":
                content = data.get("content") or ""
                tool_calls = data.get("tool_calls")
                if tool_calls:
                    # Ensure each tool_call has type: "function"
                    for tc in tool_calls:
                        if "type" not in tc:
                            tc["type"] = "function"
                    messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
                elif content:
                    messages.append({"role": "assistant", "content": content})
            elif role == "tool":
                tc_id = data.get("tool_call_id", "")
                content = data.get("content", "")
                if tc_id:
                    messages.append({"role": "tool", "tool_call_id": tc_id, "content": content})
            elif role == "user":
                content = data.get("content", "")
                if content:
                    messages.append({"role": "user", "content": content})

        messages.append({"role": "user", "content": user_input})
        self.storage.create_message(session_id, agent_name, {
            "role": "user", "content": user_input,
        })
        logger.debug("Agent %s starting, %d history messages loaded", agent_name, len(messages) - 1)

        tool_schemas = self.provider.build_tool_schema(
            self.tools.filter_by_allowlist(agent_def.tool_allowlist)
        )

        max_iterations = 50
        iteration = 0

        if self.storage.has_open_tasks(session_id):
            messages.append({"role": "system", "content": "[TASK NUDGE] You have open tasks. Continue working on them."})

        while not abort.is_set():
            iteration += 1
            if iteration > max_iterations:
                break

            stream = None
            try:
                # Use streaming to display tokens in real-time
                stream = await self.provider.chat(
                    messages=messages,
                    model=agent_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tool_schemas if tool_schemas else None,
                    tool_choice="auto" if tool_schemas else None,
                    stream=True,
                )
                assistant_content = ""
                tool_calls = []
                async for chunk in stream:
                    if chunk["type"] == "content":
                        assistant_content += chunk["content"]
                        if on_message:
                            await on_message("stream", chunk["content"])
                    elif chunk["type"] == "tool_call":
                        tool_calls.append(chunk["tool_call"])
            except Exception as e:
                error_msg = f"LLM error: {e}"
                logger.error("LLM call failed: %s", e)
                if on_message:
                    await on_message("error", error_msg)
                break
            finally:
                if stream is not None:
                    try:
                        await stream.aclose()
                    except Exception:
                        pass

            # Build single assistant message (content + tool_calls must be together)
            assistant_msg = {"role": "assistant"}
            if assistant_content:
                assistant_msg["content"] = assistant_content
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            if assistant_content or tool_calls:
                messages.append(assistant_msg)
                self.storage.create_message(session_id, agent_name, {
                    "role": "assistant",
                    "content": assistant_content or "",
                    "tool_calls": tool_calls if tool_calls else None,
                })

            if not tool_calls:
                break

            needs_user_input = False
            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                logger.info("Tool call: %s", fn_name)
                try:
                    fn_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    fn_args = {}

                tool = self.tools.get(fn_name)
                tool_result = ""
                if not tool:
                    tool_result = json.dumps({"error": f"Unknown tool: {fn_name}"})
                    if on_tool_result:
                        await on_tool_result(fn_name, tool_result, False)
                else:
                    if on_tool_call:
                        await on_tool_call(fn_name, fn_args)
                    try:
                        result = await tool.execute(fn_args, ctx)
                        tool_result = result.output
                        if result.metadata.get("needs_user_input"):
                            needs_user_input = True
                        tool_success = bool(result.metadata.get("success", True))
                        if on_tool_result:
                            await on_tool_result(fn_name, tool_result, tool_success)
                    except Exception as e:
                        tool_result = f"Tool error: {e}"
                        if on_tool_result:
                            await on_tool_result(fn_name, tool_result, False)

                # Store tool result
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })
                self.storage.create_message(session_id, agent_name, {
                    "role": "tool", "tool_call_id": tc["id"], "content": tool_result,
                })

            if needs_user_input:
                break

        # Notify agent finished
        if on_message:
            await on_message("finish", "")

        last_assistant = ""
        for m in reversed(messages):
            if m.get("role") == "assistant" and m.get("content"):
                last_assistant = m["content"]
                break

        return last_assistant

    def _build_system_prompt(self, agent: AgentDef, session_id: str, workdir: Path, user_query: str = "") -> str:
        parts = [agent.prompt]

        # Search memory based on user query
        if user_query:
            mem_results = self.memory.search(user_query, limit=5)
            if mem_results:
                mem_text = "\n".join(
                    f"- [{r.get('scope','')}] {r.get('path','')}: {r.get('body','')[:300]}"
                    for r in mem_results
                )
                parts.append(f"\n## Relevant Memory\n{mem_text}")

        checkpoint = self.memory.read_checkpoint(session_id)
        if checkpoint:
            parts.append(f"\n## Session Checkpoint\n{checkpoint[:4000]}")

        project_mem = self.memory.read_project_memory("global")
        if project_mem:
            parts.append(f"\n## Project Memory\n{project_mem[:2000]}")

        # Load session notes
        notes = self.memory.read_notes(session_id)
        if notes:
            parts.append(f"\n## Session Notes\n{notes[:2000]}")

        parts.append(f"\n## Working Directory\n{workdir}")
        parts.append(f"\n## Platform\n{self._get_platform_info()}")
        parts.append(f"\n## Date\n{time.strftime('%Y-%m-%d %H:%M')}")

        return "\n".join(parts)

    def _get_platform_info(self) -> str:
        import platform
        return f"{platform.system()} {platform.release()} ({platform.machine()})"


class ActorManager:
    def __init__(self, storage: Storage, provider: LLMProvider, tools: ToolRegistry, memory: MemorySystem, config: Config):
        self.storage = storage
        self.provider = provider
        self.tools = tools
        self.memory = memory
        self.config = config
        self._actors: dict[str, asyncio.Task] = {}
        self._loop: AgentLoop | None = None

    def set_loop(self, loop: AgentLoop) -> None:
        self._loop = loop

    async def spawn(
        self,
        session_id: str,
        prompt: str,
        agent_type: str = "explore",
        description: str = "",
        background: bool = False,
        context_mode: str = "none",
    ) -> str:
        import uuid
        actor_id = f"actor-{uuid.uuid4().hex[:8]}"

        self.storage.register_actor(
            session_id=session_id,
            actor_id=actor_id,
            mode="subagent",
            agent=agent_type,
            description=description,
            context_mode=context_mode,
            background=background,
        )

        agent_def = DEFAULT_AGENTS.get(agent_type) or AgentDef(
            name=agent_type, description=description, mode="subagent"
        )

        if not self._loop:
            raise RuntimeError("ActorManager.set_loop() must be called before spawn()")
        agent_loop = self._loop

        async def _run_actor():
            self.storage.update_actor(session_id, actor_id, status="running")
            try:
                result = await agent_loop.run(
                    session_id=session_id,
                    user_input=prompt,
                    agent_name=agent_type,
                )
                self.storage.update_actor(session_id, actor_id, status="idle", last_outcome="success")
                self.storage.send_inbox(
                    session_id, "main", session_id, actor_id,
                    {"type": "result", "content": result},
                )
            except Exception as e:
                self.storage.update_actor(
                    session_id, actor_id, status="idle", last_outcome="failure",
                    last_error=str(e),
                )
            finally:
                self._actors.pop(actor_id, None)

        task = asyncio.create_task(_run_actor())
        self._actors[actor_id] = task
        return actor_id

    async def wait(self, session_id: str, actor_id: str, timeout: float = 600) -> dict | None:
        task = self._actors.get(actor_id)
        if not task:
            return None
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        actor = self.storage.get_actor(session_id, actor_id)
        return actor

    def cancel(self, session_id: str, actor_id: str) -> None:
        task = self._actors.get(actor_id)
        if task and not task.done():
            task.cancel()
        self.storage.update_actor(session_id, actor_id, status="idle", last_outcome="cancelled")

    async def send_message(self, session_id: str, to_actor_id: str, content: str) -> None:
        self.storage.send_inbox(session_id, to_actor_id, session_id, "main", content)

    def list_actors(self, session_id: str, status: str | None = None) -> list[dict]:
        return self.storage.list_actors(session_id, status)
