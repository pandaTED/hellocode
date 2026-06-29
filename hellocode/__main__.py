"""CLI entry point for HelloCode."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import threading
from pathlib import Path

from . import __version__
from .config import Config
from .storage import Storage
from .provider import LLMProvider
from .memory import MemorySystem
from .agent import AgentLoop, ActorManager
from .tools import create_registry
from .mcp import MCPClient


def _has_display() -> bool:
    """Check if a graphical display is available."""
    if sys.platform == "win32":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _resolve_mode(args) -> str:
    """Determine launch mode: 'gui', 'cli', or 'plain'."""
    if args.gui:
        return "gui"
    if args.cli or args.no_tui:
        return "plain"
    if args.prompt:
        return "plain"

    # Auto-detect: use GUI if display available, else CLI
    if _has_display():
        try:
            import PySide6  # noqa: F401
            return "gui"
        except ImportError:
            return "cli"
    return "cli"


def _connect_mcp_for_gui(config: Config, tools) -> tuple[MCPClient, tuple[asyncio.AbstractEventLoop, threading.Thread] | None]:
    mcp_client = MCPClient(config)
    if not config.mcp.servers:
        return mcp_client, None

    loop = asyncio.new_event_loop()

    def run_loop() -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    thread = threading.Thread(target=run_loop, name="hellocode-mcp", daemon=True)
    thread.start()
    return mcp_client, (loop, thread)


def _do_mcp_connect(mcp_client, runtime, tools):
    try:
        future = asyncio.run_coroutine_threadsafe(mcp_client.connect_all(), runtime[0])
        for tool in future.result(timeout=15):
            tools.register(tool)
    except Exception:
        pass


def _disconnect_mcp_for_gui(
    mcp_client: MCPClient,
    runtime: tuple[asyncio.AbstractEventLoop, threading.Thread] | None,
) -> None:
    if not runtime:
        return
    loop, thread = runtime
    future = asyncio.run_coroutine_threadsafe(mcp_client.disconnect_all(), loop)
    try:
        future.result(timeout=10)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        loop.close()


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
    parser.add_argument("--gui", action="store_true", help="Force GUI mode (requires PySide6)")
    parser.add_argument("--cli", action="store_true", help="Force CLI/TUI mode")
    parser.add_argument("--no-tui", action="store_true", help="Plain text output (no TUI)")
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
            while "<system-reminder>" in content:
                idx = content.index("<system-reminder>")
                before = content[:idx]
                rest = content[idx + len("<system-reminder>"):]
                end_idx = rest.find("</system-reminder>")
                if end_idx >= 0:
                    content = before + rest[end_idx + len("</system-reminder>"):]
                else:
                    content = before
                    _in_system_reminder = True
            if _in_system_reminder:
                if "</system-reminder>" in content:
                    _in_system_reminder = False
                    content = content.split("</system-reminder>", 1)[-1]
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
            tui.console.clear()
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


def launch_gui(args: argparse.Namespace):
    """Launch the PySide6 GUI."""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
    except ImportError:
        print("Error: PySide6 is required for GUI mode.")
        print("Install it with: pip install PySide6")
        return

    workdir = (args.workdir or Path.cwd()).resolve()
    data_dir = args.data_dir or (Path.home() / ".local" / "share" / "hellocode")
    data_dir.mkdir(parents=True, exist_ok=True)

    config = Config.load(workdir)
    if args.model:
        pname = config.provider.default
        if pname not in config.provider.providers:
            config.provider.providers[pname] = {}
        config.provider.providers[pname]["model"] = args.model

    storage = Storage(data_dir / "hellocode.db")
    provider = LLMProvider(config)
    memory = MemorySystem(storage, data_dir)
    tools = create_registry()
    mcp_client, mcp_runtime = _connect_mcp_for_gui(config, tools)
    agent_loop = AgentLoop(config, storage, provider, tools, memory)
    actor_manager = ActorManager(storage, provider, tools, memory, config)
    actor_manager.set_loop(agent_loop)
    agent_loop.actor_manager = actor_manager

    from .scheduler import Scheduler
    scheduler = Scheduler(storage)

    async def _run_shell(schedule):
        import asyncio as _aio
        cmd = schedule.get("payload", "")
        if not cmd:
            return "No command"
        proc = await _aio.create_subprocess_shell(
            cmd, stdout=_aio.subprocess.PIPE, stderr=_aio.subprocess.PIPE,
            cwd=schedule.get("workdir") or str(workdir),
        )
        stdout, stderr = await _aio.wait_for(proc.communicate(), timeout=300)
        return stdout.decode(errors="replace")[:1000]

    async def _run_agent_prompt(schedule):
        prompt = schedule.get("payload", "")
        session_id = schedule.get("session_id") or ""
        if not session_id:
            proj = storage.find_project_by_worktree(str(workdir))
            if not proj:
                proj = storage.create_project(str(workdir), workdir.name)
            s = storage.create_session(proj["id"], str(workdir), "Scheduled Task")
            session_id = s["id"]
        result = await agent_loop.run(
            session_id=session_id, user_input=prompt,
            agent_name=schedule.get("agent_name", "build"), workdir=workdir,
        )
        return result[:1000] if result else "No response"

    async def _run_workflow(schedule):
        from .workflow import WorkflowRunner
        runner = WorkflowRunner(storage)
        result = await runner.run_workflow(
            session_id=schedule.get("session_id", ""),
            script=schedule.get("payload", ""),
            args={},
        )
        return result.get("status", "unknown") if isinstance(result, dict) else str(result)[:1000]

    scheduler.register_executor("shell_command", _run_shell)
    scheduler.register_executor("agent_prompt", _run_agent_prompt)
    scheduler.register_executor("workflow", _run_workflow)

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

    app = QApplication([])
    app.setApplicationName("HelloCode")
    app.setApplicationVersion(__version__)

    from .gui import HelloCodeGUI
    window = HelloCodeGUI(
        config=config,
        storage=storage,
        provider=provider,
        memory=memory,
        agent_loop=agent_loop,
        actor_manager=actor_manager,
        workdir=workdir,
        project=project,
        session_id=session_id,
        scheduler=scheduler,
    )

    _scheduler_timer = QTimer()
    _scheduler_timer.setInterval(30000)

    def _scheduler_tick():
        import threading as _threading
        def _run_in_thread():
            try:
                import asyncio as _aio
                loop = _aio.new_event_loop()
                try:
                    loop.run_until_complete(scheduler._check_and_run())
                finally:
                    pending = _aio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    if pending:
                        loop.run_until_complete(_aio.gather(*pending, return_exceptions=True))
                    loop.close()
            except Exception:
                pass
        _threading.Thread(target=_run_in_thread, daemon=True).start()

    _scheduler_timer.timeout.connect(_scheduler_tick)

    def _on_quit():
        scheduler._running = False
        _scheduler_timer.stop()

    app.aboutToQuit.connect(_on_quit)

    window.show()

    if mcp_runtime:
        QTimer.singleShot(500, lambda: _do_mcp_connect(mcp_client, mcp_runtime, tools))

    _scheduler_timer.start()
    try:
        app.exec()
    finally:
        _scheduler_timer.stop()
        _disconnect_mcp_for_gui(mcp_client, mcp_runtime)
        storage.close()


async def async_main(args: argparse.Namespace):
    workdir = (args.workdir or Path.cwd()).resolve()
    data_dir = args.data_dir or (Path.home() / ".local" / "share" / "hellocode")
    data_dir.mkdir(parents=True, exist_ok=True)

    config = Config.load(workdir)
    if args.model:
        pname = config.provider.default
        if pname not in config.provider.providers:
            config.provider.providers[pname] = {}
        config.provider.providers[pname]["model"] = args.model

    storage = Storage(data_dir / "hellocode.db")
    provider = LLMProvider(config)
    memory = MemorySystem(storage, data_dir)
    tools = create_registry()
    mcp_client = MCPClient(config)
    for tool in await mcp_client.connect_all():
        tools.register(tool)
    loop = AgentLoop(config, storage, provider, tools, memory)
    actor_manager = ActorManager(storage, provider, tools, memory, config)
    actor_manager.set_loop(loop)
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

    try:
        if args.prompt:
            prompt = " ".join(args.prompt)
            await run_one_shot(loop, session_id, prompt, args.agent, workdir)
        else:
            await run_interactive(loop, session_id, args.agent, workdir, use_tui=not args.no_tui)
    finally:
        await mcp_client.disconnect_all()
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

    mode = _resolve_mode(args)

    if mode == "gui":
        launch_gui(args)
        return

    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
