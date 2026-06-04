#!/usr/bin/env python3
"""Rich terminal UI — Claude Code / OpenCode style."""
import sys, os
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.spinner import Spinner
from rich.live import Live
from rich.table import Table
from rich.columns import Columns
from rich import box


BANNER = """[bold cyan]
  _____ ____   ____           _   _ _   _ ______   __
 |  __ \\___ \\ / ___|         | | | | \\ | |  _ \\ \\ / /
 | | | | |_) | |    _ __   __| | | |  \\| | | | \\ V /
 | |_| |  __/| |___| '_ \\ / _` | | | |\\  | |_| || |
 |____/|_|    \\____|_| |_|_\\__,_|_| |_| \\_|____/ |_|

[/bold cyan]"""

COMMANDS_TABLE = Table(title="Commands", box=box.ROUNDED, border_style="cyan")
COMMANDS_TABLE.add_column("Command", style="green")
COMMANDS_TABLE.add_column("Description")
COMMANDS_TABLE.add_row("/help", "Show this help")
COMMANDS_TABLE.add_row("/new", "New conversation")
COMMANDS_TABLE.add_row("/clear", "Clear history")
COMMANDS_TABLE.add_row("/model <name>", "Switch model")
COMMANDS_TABLE.add_row("/tools", "Show available tools")
COMMANDS_TABLE.add_row("/history", "Show command history")
COMMANDS_TABLE.add_row("/save <file>", "Save conversation")
COMMANDS_TABLE.add_row("/load <file>", "Load conversation")
COMMANDS_TABLE.add_row("/exit", "Exit")


class TerminalUI:
    def __init__(self):
        self.console = Console()
        self.no_color = os.environ.get("NO_COLOR") or "--no-color" in sys.argv
        if self.no_color:
            self.console = Console(no_color=True)

    def banner(self):
        self.console.print(BANNER)
        self.console.print("[dim]Autonomous Security Agent — Powered by DeepSeek[/dim]")
        self.console.print()

    def user_message(self, text):
        self.console.print()
        self.console.print(Panel(
            text, title="[bold blue]You[/bold blue]",
            border_style="blue", box=box.ROUNDED
        ))

    def agent_message(self, text):
        self.console.print()
        self.console.print(Panel(
            text, title="[bold green]Agent[/bold green]",
            border_style="green", box=box.ROUNDED
        ))

    def exec_command(self, cmd):
        self.console.print()
        self.console.print(Panel(
            Syntax(cmd, "bash", theme="monokai"),
            title="[bold yellow]EXEC[/bold yellow]",
            border_style="yellow", box=box.ROUNDED
        ))

    def command_output(self, output, max_lines=50):
        lines = output.strip().split("\n")
        if len(lines) > max_lines:
            display = "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
        else:
            display = output
        self.console.print(Panel(
            display, title="[dim]Output[/dim]",
            border_style="dim", box=box.ROUNDED
        ))

    def thinking(self, msg):
        self.console.print(f"  [yellow]{msg}[/yellow]")

    def error(self, msg):
        self.console.print(Panel(f"[red]{msg}[/red]", border_style="red"))

    def success(self, msg):
        self.console.print(f"  [green]{msg}[/green]")

    def info(self, msg):
        self.console.print(f"  [dim]{msg}[/dim]")

    def tools_list(self, tools):
        table = Table(title="Available Tools", box=box.ROUNDED, border_style="cyan")
        table.add_column("Tool", style="green")
        table.add_column("Description")
        for name, desc in tools:
            table.add_row(name, desc)
        self.console.print(table)

    def help(self):
        self.console.print(COMMANDS_TABLE)

    def prompt(self, session_count=0):
        try:
            return input(f"\033[92m[{session_count}]\033[0m \033[96m>>>\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return "/exit"

    def streaming_token(self, token, end=""):
        print(token, end=end, flush=True)

    def clear(self):
        os.system("clear" if os.name != "nt" else "cls")

    def todo_panel(self, todos: list):
        """Display the current todo list in a nice panel."""
        if not todos:
            return
        lines = []
        for i, t in enumerate(todos):
            mark  = "[green]✓[/green]" if t["done"] else "[yellow]○[/yellow]"
            style = "dim" if t["done"] else "white"
            lines.append(f"  {mark} [{style}][{i}] {t['item']}[/{style}]")
        done  = sum(1 for t in todos if t["done"])
        total = len(todos)
        bar   = "█" * done + "░" * (total - done)
        lines.append(f"\n  [cyan]{bar}[/cyan] [dim]{done}/{total}[/dim]")
        self.console.print(Panel(
            "\n".join(lines),
            title="[bold cyan]📋 Todo List[/bold cyan]",
            border_style="cyan", box=box.ROUNDED
        ))

    def todo_add(self, index: int, item: str):
        self.console.print(f"  [cyan]📝 Todo #{index}:[/cyan] {item}")

    def todo_done_msg(self, index: int, item: str, remaining: int):
        status = "[green]ALL DONE ✓[/green]" if remaining == 0 else f"[dim]{remaining} remaining[/dim]"
        self.console.print(f"  [green]✓ Done #{index}:[/green] {item} — {status}")
