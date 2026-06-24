"""Terminal UI with visual input/output separation."""

from __future__ import annotations

import asyncio
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


BANNER = "[bold green]HelloCode v0.1.0[/bold green]"
SEP = "[dim]" + "━" * 60 + "[/dim]"


class TUI:
    def __init__(self):
        self.console = Console()
        self._prompt_session: PromptSession | None = None

    def setup_completer(self, tool_names: list[str]):
        completer = WordCompleter(tool_names, ignore_case=True)
        self._prompt_session = PromptSession(
            completer=completer,
            history=InMemoryHistory(),
        )

    def _sep(self):
        self.console.print(SEP)

    def print_banner(self):
        self.console.print(BANNER)
        self.console.print("[dim]Type /help for commands, /exit to quit[/dim]")
        self.console.print()

    def print_welcome(self, session_title: str = "New Session"):
        self.console.print()
        self.console.print(Panel(
            f"[bold]Session:[/bold] {session_title}",
            border_style="cyan", width=60,
        ))

    def print_info(self, message: str):
        self.console.print(f"[cyan]{message}[/cyan]")

    def print_system(self, message: str):
        self.console.print(f"[dim]{message}[/dim]")

    def print_assistant(self, content: str):
        self._sep()
        try:
            md = __import__("rich.markdown", fromlist=["Markdown"]).Markdown(content)
            self.console.print(Panel(md, border_style="green", padding=(0, 1)))
        except Exception:
            self.console.print(Panel(content, border_style="green"))
        self._sep()

    def print_tool_call(self, tool_name: str, args: dict):
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        self.console.print(f"  [bold cyan]>[/bold cyan] {tool_name}({args_str})", highlight=False)

    def print_tool_result(self, tool_name: str, result: str, success: bool = True):
        style = "green" if success else "red"
        truncated = result[:400] + "..." if len(result) > 400 else result
        self.console.print(f"  [{style}]✓[/{style}] {truncated}", highlight=False)

    def print_error(self, message: str):
        self.console.print(f"[bold red]Error:[/bold red] {message}")

    def print_warning(self, message: str):
        self.console.print(f"[bold yellow]Warning:[/bold yellow] {message}")

    def print_task_update(self, task_id: str, status: str, summary: str):
        icons = {
            "open": "[blue]○[/blue]",
            "in_progress": "[yellow]●[/yellow]",
            "blocked": "[red]⊘[/red]",
            "done": "[green]✓[/green]",
            "abandoned": "[dim]✗[/dim]",
        }
        icon = icons.get(status, "?")
        self.console.print(f"  {icon} {task_id}: {summary}")

    def print_tasks(self, tasks: list[dict]):
        self.print_tasks_table(tasks)

    def print_tasks_table(self, tasks: list[dict]):
        if not tasks:
            self.console.print("  [dim]No tasks[/dim]")
            return
        table = Table(show_header=True, header_style="bold", border_style="dim")
        table.add_column("ID", style="cyan", width=10)
        table.add_column("Status", width=12)
        table.add_column("Summary")
        for t in tasks:
            s = t.get("status", "?")
            st = {"done": "green", "in_progress": "yellow", "blocked": "red"}.get(s, "white")
            table.add_row(t["id"], Text(s, style=st), t.get("summary", ""))
        self.console.print(table)

    def print_sessions(self, sessions: list[dict]):
        if not sessions:
            self.console.print("  [dim]No sessions[/dim]")
            return
        table = Table(show_header=True, header_style="bold", border_style="dim")
        table.add_column("ID", style="cyan", width=16)
        table.add_column("Title")
        table.add_column("Updated", width=14)
        for s in sessions:
            ts = s.get("time_updated", 0)
            dt = datetime.fromtimestamp(ts / 1000).strftime("%m-%d %H:%M") if ts else "?"
            table.add_row(s["id"], s.get("title", ""), dt)
        self.console.print(table)

    def print_help(self):
        self.console.print(Panel(
            "[bold]/help[/bold]       Show this help\n"
            "[bold]/quit[/bold]       Exit\n"
            "[bold]/tasks[/bold]      List tasks\n"
            "[bold]/sessions[/bold]   List sessions\n"
            "[bold]/clear[/bold]      Clear screen\n"
            "[bold]/memory[/bold] q   Search memory\n"
            "[bold]/new[/bold]        New session",
            title="Commands", border_style="cyan",
        ))

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

    def print_streaming(self, token: str):
        self.console.print(token, end="", highlight=False)

    def print_streaming_end(self):
        self.console.print()
