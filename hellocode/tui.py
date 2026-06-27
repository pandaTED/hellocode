"""Terminal UI with prompt_toolkit input, rich markdown rendering, and split-panel layout."""

from __future__ import annotations

import io
import shutil
import sys
import asyncio
from datetime import datetime
from collections import deque

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table


def _make_console() -> Console:
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "buffer") and sys.stdout.encoding != "utf-8":
                stdout_utf8 = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
                return Console(file=stdout_utf8, force_terminal=True)
        except Exception:
            pass
    return Console(force_terminal=True)


class TUI:
    def __init__(self):
        self.console = _make_console()
        self._stream_buf = ""
        self._prompt_session = None
        self._tool_history: deque[dict] = deque(maxlen=50)
        self._right_width = 0
        self._left_width = 0
        self._terminal_height = 0

    def _setup_layout(self):
        try:
            size = shutil.get_terminal_size()
            self._terminal_height = size.lines
            self._right_width = max(20, size.columns // 5)
            self._left_width = size.columns - self._right_width - 3
        except Exception:
            self._left_width = 80
            self._right_width = 20

    def _setup_prompt(self):
        try:
            from prompt_toolkit import PromptSession
            self._prompt_session = PromptSession(history=None)
        except Exception:
            pass

    def _render_markdown(self, content: str) -> Panel:
        md = Markdown(content)
        return Panel(md, border_style="green", padding=(0, 1))

    def _render_right_panel(self) -> Panel:
        if not self._tool_history:
            return Panel("[dim]No tool calls yet[/dim]", title="Tool History", border_style="cyan", width=self._right_width)

        lines = []
        for i, entry in enumerate(self._tool_history):
            name = entry.get("name", "?")
            status = entry.get("status", "pending")
            result_preview = entry.get("result", "")[:80]
            icon = {"ok": "[green]✓[/green]", "error": "[red]✗[/red]", "pending": "[yellow]⏳[/yellow]"}.get(status, "?")
            lines.append(f"{icon} [bold]{name}[/bold]")
            if result_preview:
                lines.append(f"  [dim]{result_preview}[/dim]")
            lines.append("")

        content = "\n".join(lines[-30:])
        return Panel(content, title="Tool History", border_style="cyan", width=self._right_width)

    def print_banner(self):
        from . import __version__
        self._setup_layout()
        self.console.print(f"[bold green]HelloCode v{__version__}[/bold green]")
        self.console.print("[dim]Type /help for commands, /exit to quit[/dim]")
        self.console.print()

    def print_welcome(self, session_title: str = "New Session"):
        pass

    def print_info(self, message: str):
        self.console.print(self._render_markdown(message))

    def print_system(self, message: str):
        self.console.print(f"[dim]{message}[/dim]")

    def print_assistant(self, content: str):
        self.console.print(self._render_markdown(content))
        self._print_tool_panel()

    def print_tool_call(self, tool_name: str, args: dict):
        def truncate(v, n=60):
            s = repr(v)
            return s[:n] + "..." if len(s) > n else s
        args_str = ", ".join(f"{k}={truncate(v)}" for k, v in args.items())
        self._tool_history.append({
            "name": tool_name,
            "args": args_str,
            "status": "pending",
            "result": "",
            "time": datetime.now().strftime("%H:%M:%S"),
        })
        self.console.print(f"  [dim cyan]▸ {tool_name}[/dim cyan] [dim]({args_str})[/dim]")

    def print_tool_result(self, tool_name: str, result: str, success: bool = True):
        for entry in reversed(self._tool_history):
            if entry["name"] == tool_name and entry["status"] == "pending":
                entry["status"] = "ok" if success else "error"
                entry["result"] = result[:200]
                break
        prefix = "[green]✓[/green]" if success else "[red]✗[/red]"
        truncated = result[:150] + "..." if len(result) > 150 else result
        self.console.print(f"  {prefix} [dim]{truncated}[/dim]")

    def _print_tool_panel(self):
        if not self._tool_history:
            return
        table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 1))
        table.add_column("Tool", style="bold", width=16)
        table.add_column("Status", width=8)
        table.add_column("Result", width=self._left_width - 30 if self._left_width > 30 else 40, overflow="ellipsis")
        for entry in list(self._tool_history)[-8:]:
            icon = {"ok": "[green]✓[/green]", "error": "[red]✗[/red]", "pending": "[yellow]⏳[/yellow]"}.get(entry["status"], "?")
            result_short = entry["result"][:60] + "..." if len(entry["result"]) > 60 else entry["result"]
            table.add_row(entry["name"], icon, f"[dim]{result_short}[/dim]")
        self.console.print(Panel(table, title="[bold]Tool Execution Audit[/bold]", border_style="dim cyan", padding=(0, 1)))

    def print_error(self, message: str):
        self.console.print(f"[bold red]Error:[/bold red] {message}")

    def print_warning(self, message: str):
        self.console.print(f"[bold yellow]Warning:[/bold yellow] {message}")

    def print_task_update(self, task_id: str, status: str, summary: str):
        icons = {"open": "○", "in_progress": "●", "blocked": "⊘", "done": "✓", "abandoned": "✗"}
        self.console.print(f"  {icons.get(status, '?')} {task_id}: {summary}")

    def print_tasks(self, tasks: list[dict]):
        if not tasks:
            self.console.print("  No tasks")
            return
        lines = ["  Tasks:"]
        for t in tasks:
            lines.append(f"    {t['id']}: {t.get('summary', '')} [{t.get('status', '?')}]")
        self.console.print("\n".join(lines))

    def print_sessions(self, sessions: list[dict]):
        if not sessions:
            self.console.print("  No sessions")
            return
        lines = ["  Sessions:"]
        for s in sessions:
            ts = s.get("time_updated", 0)
            dt = datetime.fromtimestamp(ts / 1000).strftime("%m-%d %H:%M") if ts else "?"
            lines.append(f"    {s['id']}: {s.get('title', '')} [{dt}]")
        self.console.print("\n".join(lines))

    def print_help(self):
        help_text = (
            "**Commands:**\n\n"
            "| Command | Description |\n"
            "|---------|-------------|\n"
            "| `/help` | Show this help |\n"
            "| `/exit` | Exit |\n"
            "| `/tasks` | List tasks |\n"
            "| `/sessions` | List sessions |\n"
            "| `/clear` | Clear screen |\n"
            "| `/memory <query>` | Search memory |\n"
            "| `/new` | New session |"
        )
        self.console.print(self._render_markdown(help_text))

    def print_streaming(self, token: str):
        self._stream_buf += token

    def finish_streaming(self):
        if self._stream_buf.strip():
            self.console.print(self._render_markdown(self._stream_buf.strip()))
        self._stream_buf = ""

    def print_streaming_end(self):
        self.finish_streaming()

    def finish_output(self):
        self.finish_streaming()

    def clear_tool_history(self):
        self._tool_history.clear()

    async def get_input(self, session_id: str = "") -> str:
        try:
            loop = asyncio.get_running_loop()
            if self._prompt_session:
                return await loop.run_in_executor(
                    None, lambda: self._prompt_session.prompt("❯ ")
                )
            return await loop.run_in_executor(
                None, lambda: input("❯ ")
            )
        except (KeyboardInterrupt, EOFError):
            return "/exit"

    def setup_completer(self, tool_names: list[str]):
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.completion import WordCompleter
            completer = WordCompleter(tool_names, ignore_case=True)
            if self._prompt_session:
                self._prompt_session = PromptSession(completer=completer)
        except Exception:
            pass
