#!/usr/bin/env python3
"""
Terminal UI — Claude Code style.

Layout:
  ┌─────────────────────────────────────────────────────────┐
  │  header bar: model + session info                       │
  ├─────────────────────────────────────────────────────────┤
  │                                                         │
  │  conversation area (scrollable)                         │
  │                                                         │
  │   ╭─ You ──────────────────────────────────────────╮   │
  │   │  <message>                                     │   │
  │   ╰────────────────────────────────────────────────╯   │
  │                                                         │
  │   ● Thinking…                                           │
  │                                                         │
  │   ╭─ bash ─────────────────────────────────────────╮   │
  │   │  $ ls -la /tmp                                 │   │
  │   ╰────────────────────────────────────────────────╯   │
  │   ╭─ output ───────────────────────────────────────╮   │
  │   │  total 8 ...                                   │   │
  │   ╰────────────────────────────────────────────────╯   │
  │                                                         │
  │   ╭─ Assistant ─────────────────────────────────────╮  │
  │   │  <reply>                                        │  │
  │   ╰─────────────────────────────────────────────────╯  │
  │                                                         │
  ├─────────────────────────────────────────────────────────┤
  │  ❯  <input>                                             │
  └─────────────────────────────────────────────────────────┘

Colours (closest to Claude Code defaults):
  • User bubble     — white text, dim blue border
  • Assistant       — white text, dim green border
  • Bash block      — dark bg, orange label
  • Output block    — dark bg, dim border
  • Todo            — cyan checkboxes
  • Thinking        — italic orange dots
  • Error           — red
  • Header          — bold on dark bg
"""

import os, sys, re
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.table import Table
from rich.rule import Rule
from rich.spinner import Spinner
from rich.live import Live
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.padding import Padding

try:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.styles import Style as PtStyle
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.formatted_text import HTML
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False


# ─── Colour palette (Claude Code–like) ────────────────────────────────────────
ORANGE   = "#d4a72c"
BLUE_DIM = "#4a90d9"
GREEN_DIM= "#3dba6f"
CYAN     = "#56c8d8"
GREY     = "#666666"
BG_CODE  = "on #1a1a1a"
WHITE    = "white"
PURPLE   = "#b48ead"


# ─── Box styles ───────────────────────────────────────────────────────────────
USER_BOX      = box.ROUNDED
AGENT_BOX     = box.ROUNDED
CODE_BOX      = box.SIMPLE_HEAD
OUTPUT_BOX    = box.SIMPLE_HEAD
TODO_BOX      = box.MINIMAL
MINIMAL_BOX   = box.MINIMAL


class TerminalUI:
    def __init__(self, model: str = "deepseek-coder"):
        self.model      = model
        self.no_color   = os.environ.get("NO_COLOR") or "--no-color" in sys.argv
        self.console    = Console(no_color=self.no_color, highlight=False)
        self._session_start = datetime.now().strftime("%H:%M")
        self._cmd_count = 0
        self._width     = self.console.width
        if HAS_PROMPT_TOOLKIT:
            self._pt_history = InMemoryHistory()

    # ─── Header ───────────────────────────────────────────────────────────────
    def banner(self):
        """Claude Code–style compact header bar."""
        self.console.print()
        title = Text()
        title.append("  ◆ ", style=f"bold {ORANGE}")
        title.append("DeepSeek", style="bold white")
        title.append(" Agent", style="bold cyan")
        title.append(f"  [{self.model}]", style=f"dim {CYAN}")
        title.append(f"  ·  {self._session_start}", style=GREY)

        self.console.print(
            Panel(title, box=box.HORIZONTALS, style="on #111111",
                  padding=(0, 1))
        )
        self.console.print(
            f"  [dim]Type [bold]/help[/bold] for commands · [bold]Ctrl+C[/bold] to interrupt · [bold]/exit[/bold] to quit[/dim]"
        )
        self.console.print()

    # ─── User bubble ──────────────────────────────────────────────────────────
    def user_message(self, text: str):
        self.console.print()
        label = Text("  You", style=f"bold {BLUE_DIM}")
        self.console.print(label)
        self.console.print(
            Panel(
                Text(text, style=WHITE),
                border_style=BLUE_DIM,
                box=USER_BOX,
                padding=(0, 2),
            )
        )

    # ─── Assistant bubble ─────────────────────────────────────────────────────
    def agent_message(self, text: str):
        self.console.print()
        label = Text("  Assistant", style=f"bold {GREEN_DIM}")
        self.console.print(label)
        # Render markdown inside the panel
        try:
            content = Markdown(text)
        except Exception:
            content = Text(text)
        self.console.print(
            Panel(
                content,
                border_style=GREEN_DIM,
                box=AGENT_BOX,
                padding=(0, 2),
            )
        )

    # ─── Thinking indicator ───────────────────────────────────────────────────
    def thinking(self, msg: str = "Thinking…"):
        self.console.print(f"  [italic {ORANGE}]● {msg}[/italic {ORANGE}]")

    def thinking_live(self, msg: str = "Thinking…"):
        """Returns a Live context you can use as a spinner."""
        spinner = Spinner("dots", text=f"[italic {ORANGE}] {msg}[/italic {ORANGE}]")
        return Live(spinner, console=self.console, refresh_per_second=10)

    # ─── Tool: bash block ─────────────────────────────────────────────────────
    def exec_command(self, cmd: str):
        """Render a bash command block exactly like Claude Code."""
        self.console.print()
        # Label line
        self.console.print(
            f"  [bold {ORANGE}]▸ bash[/bold {ORANGE}]  "
            f"[{GREY}]cmd #{self._cmd_count + 1}[/{GREY}]"
        )
        self._cmd_count += 1

        # Detect single-line vs multi-line
        lines = cmd.strip().split("\n")
        if len(lines) == 1:
            display = f"[bold {CYAN}]$[/bold {CYAN}] {cmd.strip()}"
            self.console.print(
                Panel(Text.from_markup(display),
                      border_style=ORANGE, box=CODE_BOX,
                      padding=(0, 2))
            )
        else:
            syn = Syntax(cmd, "bash", theme="monokai",
                         background_color="#1a1a1a", word_wrap=True)
            self.console.print(
                Panel(syn, border_style=ORANGE, box=CODE_BOX, padding=(0, 1))
            )

    # ─── Tool: output block ───────────────────────────────────────────────────
    def command_output(self, output: str, max_lines: int = 40):
        lines = output.strip().split("\n")
        truncated = False
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True

        text = Text("\n".join(lines), style=f"dim {WHITE}")
        if truncated:
            text.append(f"\n… ({len(output.split(chr(10))) - max_lines} more lines)", style=GREY)

        self.console.print(
            Panel(text, title=Text("output", style=GREY),
                  border_style=GREY, box=OUTPUT_BOX,
                  padding=(0, 2))
        )

    # ─── File operations ──────────────────────────────────────────────────────
    def file_write(self, path: str):
        self.console.print(
            f"  [bold {PURPLE}]▸ write[/bold {PURPLE}]  [{GREY}]{path}[/{GREY}]"
        )

    def file_read(self, path: str):
        self.console.print(
            f"  [bold {PURPLE}]▸ read[/bold {PURPLE}]   [{GREY}]{path}[/{GREY}]"
        )

    # ─── Todo list (Claude Code style) ────────────────────────────────────────
    def todo_panel(self, todos: list[dict]):
        """
        Render todo list with Claude Code–style checkboxes.
        Each item: {"content": str, "status": "pending"|"in_progress"|"completed"|"cancelled"}
        """
        if not todos:
            return

        lines = Text()
        icons = {
            "pending":     ("○", GREY),
            "in_progress": ("▶", ORANGE),
            "completed":   ("✓", GREEN_DIM),
            "cancelled":   ("✗", "red"),
        }
        for t in todos:
            icon, color = icons.get(t.get("status", "pending"), ("○", GREY))
            status = t.get("status", "pending")
            dim    = status in ("completed", "cancelled")

            lines.append(f"  {icon} ", style=f"bold {color}")
            content = t.get("content", "")
            lines.append(content + "\n", style=f"dim {WHITE}" if dim else WHITE)

        done  = sum(1 for t in todos if t.get("status") == "completed")
        total = len(todos)
        bar_filled  = "█" * done
        bar_empty   = "░" * (total - done)
        lines.append(f"\n  {bar_filled}", style=f"bold {GREEN_DIM}")
        lines.append(bar_empty, style=GREY)
        lines.append(f"  {done}/{total}", style=f"dim {WHITE}")

        self.console.print()
        self.console.print(
            Panel(
                lines,
                title=Text("📋 Tasks", style=f"bold {CYAN}"),
                border_style=CYAN,
                box=TODO_BOX,
                padding=(0, 1),
            )
        )

    def todo_step(self, content: str, status: str):
        """Single inline step update (compact, no panel)."""
        icons = {
            "pending":     (f"○", GREY),
            "in_progress": ("▶", ORANGE),
            "completed":   ("✓", GREEN_DIM),
        }
        icon, color = icons.get(status, ("●", WHITE))
        self.console.print(
            f"  [{color}]{icon}[/{color}] [dim]{content[:80]}[/dim]"
        )

    # ─── Info / Error / Success ───────────────────────────────────────────────
    def error(self, msg: str):
        self.console.print()
        self.console.print(
            Panel(Text(msg, style="bold red"),
                  border_style="red", box=box.ROUNDED, padding=(0, 2))
        )

    def success(self, msg: str):
        self.console.print(f"  [{GREEN_DIM}]✓ {msg}[/{GREEN_DIM}]")

    def info(self, msg: str):
        self.console.print(f"  [{GREY}]{msg}[/{GREY}]")

    def warn(self, msg: str):
        self.console.print(f"  [{ORANGE}]⚠ {msg}[/{ORANGE}]")

    def rule(self, title: str = ""):
        self.console.print(Rule(title, style=GREY))

    # ─── Tools / Help tables ──────────────────────────────────────────────────
    def tools_list(self, tools: list[tuple[str, str]]):
        table = Table(box=box.SIMPLE_HEAD, border_style=GREY,
                      show_header=True, header_style=f"bold {CYAN}",
                      pad_edge=False)
        table.add_column("Tool", style=f"bold {ORANGE}", min_width=18)
        table.add_column("Description", style=WHITE)
        for name, desc in tools:
            table.add_row(name, desc)
        self.console.print()
        self.console.print(Padding(table, (0, 2)))

    def help(self):
        table = Table(box=box.SIMPLE_HEAD, border_style=GREY,
                      show_header=True, header_style=f"bold {CYAN}",
                      pad_edge=False)
        table.add_column("Command", style=f"bold {ORANGE}", min_width=20)
        table.add_column("Description", style=WHITE)
        rows = [
            ("/help",           "Show this help"),
            ("/new",            "New conversation + session"),
            ("/clear",          "Clear conversation history"),
            ("/model <name>",   "Switch model (deepseek-coder, deepseek-v3 …)"),
            ("/tools",          "List available tools"),
            ("/save <file>",    "Save conversation to JSON"),
            ("/load <file>",    "Load conversation from JSON"),
            ("/exit",           "Quit"),
        ]
        for cmd, desc in rows:
            table.add_row(cmd, desc)
        self.console.print()
        self.console.print(Padding(table, (0, 2)))
        self.console.print()
        self.console.print(f"  [{GREY}]Keyboard shortcuts: Ctrl+C interrupt  ·  Up/Down history[/{GREY}]")
        self.console.print()

    # ─── Input prompt ─────────────────────────────────────────────────────────
    def prompt(self, session_count: int = 0) -> str:
        """
        Claude Code–style input prompt:
            ❯  …
        Uses prompt_toolkit for history / arrow keys if available.
        """
        self.console.print()

        if HAS_PROMPT_TOOLKIT:
            pt_style = PtStyle.from_dict({
                "prompt":      f"bold {ORANGE}",
                "input":       WHITE,
            })
            try:
                text = pt_prompt(
                    HTML(f'<ansibrightwhite>❯  </ansibrightwhite>'),
                    history=self._pt_history,
                    style=pt_style,
                    enable_history_search=True,
                )
                return (text or "").strip()
            except (EOFError, KeyboardInterrupt):
                return "/exit"
        else:
            try:
                return input("\033[1;33m❯  \033[0m").strip()
            except (EOFError, KeyboardInterrupt):
                return "/exit"

    # ─── Streaming token ──────────────────────────────────────────────────────
    def streaming_token(self, token: str, end: str = ""):
        print(token, end=end, flush=True)

    # ─── Screen ───────────────────────────────────────────────────────────────
    def clear(self):
        os.system("clear" if os.name != "nt" else "cls")

    # ─── Legacy compatibility (old todo format) ───────────────────────────────
    def todo_add(self, index: int, item: str):
        self.todo_step(item, "in_progress")

    def todo_done_msg(self, index: int, item: str, remaining: int):
        self.todo_step(item, "completed")
