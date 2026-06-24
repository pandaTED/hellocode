"""CLI entry point for HelloCode."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

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
    parser.add_argument("--version", "-v", action="version", version="HelloCode 0.1.0")
    return parser.parse_args()


async def run_interactive(loop: AgentLoop, session_id: str, agent_name: str, workdir: Path):
    from .tui import TUI

    tui = TUI()
    tui.print_banner()

    async def on_tool_call(name: str, args: dict):
        tui.print_tool_call(name, args)

    async def on_message(kind: str, content: str):
        if kind == "error":
            tui.print_error(content)

    def on_sigint(sig, frame):
        loop.abort()
        tui.print_warning("\nInterrupted")

    signal.signal(signal.SIGINT, on_sigint)

    while True:
        try:
            user_input = await tui.get_input()
        except (KeyboardInterrupt, EOFError):
            tui.print_info("Goodbye!")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input in ("/exit", "/quit", "/q"):
            tui.print_info("Goodbye!")
            break

        if user_input == "/help":
            tui.print_help()
            continue

        if user_input == "/clear":
            tui.console.clear()
            continue

        if user_input == "/tasks":
            tasks = loop.storage.list_tasks(session_id)
            tui.print_tasks(tasks)
            continue

        if user_input == "/sessions":
            sess = loop.storage.get_session(session_id)
            pid = sess["project_id"] if sess and "project_id" in sess.keys() else ""
            sessions = loop.storage.list_sessions(pid)
            tui.print_sessions(sessions)
            continue

        if user_input == "/new":
            sess = loop.storage.get_session(session_id)
            pid = sess["project_id"] if sess and "project_id" in sess.keys() else ""
            session = loop.storage.create_session(
                pid,
                str(workdir),
                "New Session",
            )
            session_id = session["id"]
            tui.print_info(f"New session: {session_id}")
            continue

        if user_input.startswith("/memory "):
            query = user_input[8:].strip()
            results = loop.memory.search(query)
            if results:
                for r in results:
                    tui.print_info(f"[{r['scope']}] {r['path']}: {r['body'][:200]}")
            else:
                tui.print_info("No results found")
            continue

        if user_input.startswith("/"):
            tui.print_error(f"Unknown command: {user_input}")
            continue

        tui.print_system(f"You: {user_input}")

        try:
            response = await loop.run(
                session_id=session_id,
                user_input=user_input,
                agent_name=agent_name,
                workdir=workdir,
                on_tool_call=on_tool_call,
                on_message=on_message,
            )
            if response:
                tui.print_assistant(response)
        except Exception as e:
            tui.print_error(f"Error: {e}")


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
        await run_interactive(loop, session_id, args.agent, workdir)

    storage.close()


def main():
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args()
    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
