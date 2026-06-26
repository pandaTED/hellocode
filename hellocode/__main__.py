"""CLI entry point for HelloCode."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from . import __version__
from .config import Config
from .storage import Storage
from .provider import LLMProvider
from .memory import MemorySystem
from .agent import AgentLoop, ActorManager
from .tools import create_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hellocode",
        description="HelloCode - Terminal-native AI coding assistant",
    )
    parser.add_argument("prompt", nargs="*", help="Initial prompt (non-interactive mode)")
    parser.add_argument("--model", "-m", help="Override model name")
    parser.add_argument("--agent", "-a", default="build", help="Agent to use (default: build)")
    parser.add_argument("--workdir", "-d", type=Path, help="Working directory")
    parser.add_argument("--data-dir", type=Path, help="Data directory for storage/memory")
    parser.add_argument("--session-id", help="Resume a previous session")
    parser.add_argument("--no-tui", action="store_true", help="Disable TUI, plain text output")
    parser.add_argument("--version", "-v", action="version", version=f"HelloCode {__version__}")
    return parser.parse_args()


async def run_interactive(loop: AgentLoop, session_id: str, agent_name: str, workdir: Path, use_tui: bool = True):
    from .tui import TUI

    tui = TUI()
    if use_tui:
        tui._setup_prompt()
        tui.print_banner()

    _in_system_reminder = False
    _session = {"id": session_id}

    async def on_tool_call(name: str, args: dict):
        nonlocal _in_system_reminder
        _in_system_reminder = False
        tui.finish_streaming()
        tui.print_tool_call(name, args)

    async def on_tool_result(name: str, result: str, success: bool = True):
        tui.print_tool_result(name, result, success)

    async def on_message(kind: str, content: str):
        nonlocal _in_system_reminder
        if kind == "stream":
            if "<system-reminder>" in content:
                _in_system_reminder = True
                parts = content.split("<system-reminder>")
                content = parts[0] if parts else ""
            if _in_system_reminder:
                if "</system-reminder>" in content:
                    _in_system_reminder = False
                    content = content.split("</system-reminder>")[-1]
                else:
                    return
            if content:
                tui.print_streaming(content)
        elif kind == "finish":
            tui.finish_streaming()
        elif kind == "error":
            _in_system_reminder = False
            tui.finish_streaming()
            tui.print_error(content)

    async def on_submit(user_input: str):
        if not user_input.strip():
            return

        if user_input.strip() in ("/exit", "/quit", "/q"):
            return "exit"

        if user_input.strip() == "/help":
            tui.print_help()
            return

        if user_input.strip() == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            return

        if user_input.strip() == "/tasks":
            tasks = loop.storage.list_tasks(_session["id"])
            tui.print_tasks(tasks)
            return

        if user_input.strip() == "/sessions":
            sess = loop.storage.get_session(_session["id"])
            pid = sess["project_id"] if sess and "project_id" in sess else ""
            sessions = loop.storage.list_sessions(pid)
            tui.print_sessions(sessions)
            return

        if user_input.strip() == "/new":
            sess = loop.storage.get_session(_session["id"])
            pid = sess["project_id"] if sess and "project_id" in sess else ""
            session = loop.storage.create_session(pid, str(workdir), "New Session")
            _session["id"] = session["id"]
            tui.print_info(f"New session: {_session['id']}")
            return

        if user_input.strip().startswith("/memory "):
            query = user_input.strip()[8:].strip()
            results = loop.memory.search(query)
            if results:
                for r in results:
                    tui.print_info(f"[{r['scope']}] {r['path']}: {r['body'][:200]}")
            else:
                tui.print_info("No results found")
            return

        if user_input.strip().startswith("/"):
            tui.print_error(f"Unknown command: {user_input}")
            return

        try:
            tui.clear_tool_history()
            await loop.run(
                session_id=_session["id"],
                user_input=user_input,
                agent_name=agent_name,
                workdir=workdir,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
                on_message=on_message,
            )
        except Exception as e:
            tui.print_error(f"Error: {e}")

    # Main loop
    while True:
        try:
            user_input = await tui.get_input()
        except (KeyboardInterrupt, EOFError):
            break

        result = await on_submit(user_input)
        if result == "exit":
            break


async def run_one_shot(loop: AgentLoop, session_id: str, prompt: str, agent_name: str, workdir: Path):
    response = await loop.run(
        session_id=session_id,
        user_input=prompt,
        agent_name=agent_name,
        workdir=workdir,
    )
    print(response)


async def async_main(args: argparse.Namespace):
    workdir = (args.workdir or Path.cwd()).resolve()
    data_dir = args.data_dir or (Path.home() / ".local" / "share" / "hellocode")
    data_dir.mkdir(parents=True, exist_ok=True)

    config = Config.load(workdir)
    if args.model:
        if config.provider.default not in config.provider.__dict__:
            config.provider.__dict__[config.provider.default] = {}
        config.provider.__dict__[config.provider.default]["model"] = args.model

    storage = Storage(data_dir / "minicode_python.db")
    provider = LLMProvider(config)
    memory = MemorySystem(storage, data_dir)
    tools = create_registry()
    loop = AgentLoop(config, storage, provider, tools, memory)
    actor_manager = ActorManager(storage, provider, tools, memory, config)
    loop.actor_manager = actor_manager

    project = storage.find_project_by_worktree(str(workdir))
    if not project:
        project = storage.create_project(str(workdir), workdir.name)

    if args.session_id:
        session = storage.get_session(args.session_id)
        if session:
            session_id = args.session_id
        else:
            s = storage.create_session(project["id"], str(workdir))
            session_id = s["id"]
    else:
        s = storage.create_session(project["id"], str(workdir))
        session_id = s["id"]

    if args.prompt:
        prompt = " ".join(args.prompt)
        await run_one_shot(loop, session_id, prompt, args.agent, workdir)
    else:
        await run_interactive(loop, session_id, args.agent, workdir, use_tui=not args.no_tui)

    storage.close()


def main():
    import logging
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("hellocode").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    args = parse_args()
    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
