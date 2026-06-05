#!/usr/bin/env python3
"""
Terminal UI — exact Claude Code v2.0.0 style.

Layout:
  ┌─────────────────────────────────────────────────────┐
  │  ● ● ●  (title bar)                                 │
  ├─────────────────────────────────────────────────────┤
  │  ┌─────────────────────────────────────────────┐    │
  │  │ ── DeepSeek Agent v1.0 ──  │ Recent activity│    │
  │  │  Welcome back!             │ ...            │    │
  │  │  [ANON MASK rotating]      │ What's new     │    │
  │  │  model · path              │ ...            │    │
  │  └─────────────────────────────────────────────┘    │
  │                                                     │
  │   You: ...          (scrollable conversation)       │
  │   ● Thinking…                                       │
  │   ▸ bash  $ cmd                                     │
  │     output                                          │
  │   Assistant: ...                                    │
  ├─────────────────────────────────────────────────────┤
  │  ❯ █  Try "edit <filepath> to ..."                  │
  └─────────────────────────────────────────────────────┘
"""

import os, sys, time, threading
from datetime import datetime

from rich.console import Console
from rich.panel   import Panel
from rich.text    import Text
from rich.table   import Table
from rich.syntax  import Syntax
from rich.markdown import Markdown
from rich.columns  import Columns
from rich.padding  import Padding
from rich.rule     import Rule
from rich.live     import Live
from rich.spinner  import Spinner
from rich          import box

try:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.formatted_text import HTML
    HAS_PT = True
except ImportError:
    HAS_PT = False


# ── Palette (matches HTML clone) ─────────────────────────────────────────────
GOLD    = "#c8aa50"
ORANGE  = "#d4a72c"
TEAL    = "#56c8d8"
GREEN   = "#38a860"
BLUE    = "#4888cc"
GREY    = "#585848"
DGREY   = "#484838"
LIME    = "#90b870"
WHITE   = "#c8c8b8"
DWHITE  = "#888878"
RUST    = "#e06c75"
CODE_G  = "#98c379"

# ── Anonymous mask frames (CSS rotateY approximated in Unicode/braille) ───────
# We use a simple text-art mask that "wobbles" via Rich Live
MASK_FRAMES = [
    "[dim white]   .=.[/dim white]\n  [white](o o)[/white]\n  [dim]|   |[/dim]\n  [white] ‾‾‾ [/white]",
    "[dim white]  .===.[/dim white]\n [white] (o o)[/white]\n [dim] |   | [/dim]\n  [white] ‾‾‾ [/white]",
    "[white]  .=====.[/white]\n [white](o   o)[/white]\n[dim]|     |[/dim]\n [white] ‾‾‾‾‾ [/white]",
    "[dim white]  .===.[/dim white]\n [white] (o o)[/white]\n [dim] |   | [/dim]\n  [white] ‾‾‾ [/white]",
]


class TerminalUI:
    def __init__(self, model: str = "deepseek-coder", path: str = "/root/deepseek-agent"):
        self.model   = model
        self.path    = path
        self.no_color = os.environ.get("NO_COLOR") or "--no-color" in sys.argv
        self.console  = Console(no_color=self.no_color, highlight=False)
        self._cmd_n   = 0
        self._start   = datetime.now().strftime("%H:%M")
        if HAS_PT:
            self._pt_hist = InMemoryHistory()

    # ─── Welcome screen (Claude Code style) ──────────────────────────────────
    def banner(self, recent: list[tuple[str,str]] | None = None):
        """
        Print the full welcome card exactly like Claude Code v2.0.0.
        recent: list of (time_ago, description)
        """
        if recent is None:
            recent = [
                ("1m ago",  "Updated project memory"),
                ("8m ago",  "Executed bash plan-execute loop"),
                ("2d ago",  "Refactored SSE stream parser"),
                ("1w ago",  "Added PoW C-solver"),
            ]

        # ── Left pane ─────────────────────────────────────────────────────────
        left = Text()

        # header line
        left.append("── ", style=DGREY)
        left.append("DeepSeek Agent v1.0", style=f"bold {GOLD}")
        left.append(" ──\n", style=DGREY)
        left.append("\n")

        # greeting
        left.append("   Welcome back!\n\n", style=WHITE)

        # mask (static Unicode art — animated version done separately)
        left.append("      .=====.\n", style="bold white")
        left.append("     (o     o)\n", style="bold white")
        left.append("     |  ___  |\n", style="dim white")
        left.append("     | |   | |\n", style="dim white")
        left.append("      ‾‾‾‾‾‾‾\n\n", style="bold white")

        # meta
        left.append(f"  {self.model} · Max 20x\n", style=GREY)
        left.append(f"  {self.path}", style=GREY)

        left_panel = Panel(
            left,
            border_style=DGREY,
            box=box.MINIMAL_DOUBLE_HEAD,
            padding=(0, 1),
            width=28,
        )

        # ── Right pane ────────────────────────────────────────────────────────
        right = Text()

        # Recent activity
        right.append("Recent activity\n", style=f"bold {ORANGE}")
        for t, d in recent:
            right.append(f"{t:<8}", style=GREY)
            right.append(f"{d}\n",  style=DWHITE)
        right.append("... /history for more\n", style=DGREY)

        right.append("\n")

        # What's new
        right.append("What's new\n", style=f"bold {ORANGE}")
        news = [
            ("/plan to preview task steps",   LIME),
            ("/model to switch models",        DWHITE),
            ("ctrl+c to interrupt task",       DWHITE),
        ]
        for txt, col in news:
            right.append(f"{txt}\n", style=col)
        right.append("... /help for more", style=DGREY)

        right_panel = Panel(
            right,
            border_style=DGREY,
            box=box.MINIMAL_DOUBLE_HEAD,
            padding=(0, 1),
        )

        # ── Render side-by-side ───────────────────────────────────────────────
        self.console.print()
        self.console.print(Columns([left_panel, right_panel], equal=False, expand=True))
        self.console.print()
        self.console.print(
            f"  [{DGREY}]Type [bold white]/help[/bold white] for commands "
            f"· [bold white]Ctrl+C[/bold white] to interrupt "
            f"· [bold white]/exit[/bold white] to quit[/{DGREY}]"
        )
        self.console.print()

    # ─── Animated welcome (Live spinner mask) ─────────────────────────────────
    def banner_animated(self, seconds: float = 0.0, recent=None):
        """
        Show the welcome banner with a spinning Anonymous mask.
        seconds=0 → just print static version.
        """
        self.banner(recent)

    # ─── User bubble ─────────────────────────────────────────────────────────
    def user_message(self, text: str):
        self.console.print()
        self.console.print(f"  [{BLUE}]You[/{BLUE}]")
        self.console.print(
            Panel(Text(text, style=WHITE),
                  border_style="#284060", box=box.ROUNDED, padding=(0, 2))
        )

    # ─── Assistant bubble ────────────────────────────────────────────────────
    def agent_message(self, text: str):
        self.console.print()
        self.console.print(f"  [{GREEN}]Assistant[/{GREEN}]")
        try:
            content = Markdown(text)
        except Exception:
            content = Text(text, style=WHITE)
        self.console.print(
            Panel(content, border_style="#1c3828", box=box.ROUNDED, padding=(0, 2))
        )

    # ─── Thinking ────────────────────────────────────────────────────────────
    def thinking(self, msg: str = "Thinking…"):
        self.console.print(f"  [italic {ORANGE}]● {msg}[/italic {ORANGE}]")

    # ─── Bash block ──────────────────────────────────────────────────────────
    def exec_command(self, cmd: str):
        self.console.print()
        self._cmd_n += 1
        self.console.print(
            f"  [bold {ORANGE}]▸ bash[/bold {ORANGE}]"
            f"  [{DGREY}]cmd #{self._cmd_n}[/{DGREY}]"
        )
        lines = cmd.strip().split("\n")
        if len(lines) == 1:
            display = Text()
            display.append("$ ", style=f"bold {TEAL}")
            display.append(cmd.strip(), style=WHITE)
            self.console.print(
                Panel(display, border_style=f"dim {ORANGE}",
                      box=box.SIMPLE_HEAD, padding=(0, 2))
            )
        else:
            syn = Syntax(cmd, "bash", theme="monokai",
                         background_color="#191919", word_wrap=True)
            self.console.print(
                Panel(syn, border_style=f"dim {ORANGE}",
                      box=box.SIMPLE_HEAD, padding=(0, 1))
            )

    # ─── Output block ────────────────────────────────────────────────────────
    def command_output(self, output: str, max_lines: int = 35):
        lines = output.strip().split("\n")
        if len(lines) > max_lines:
            shown = lines[:max_lines]
            tail  = f"\n… ({len(lines)-max_lines} more lines)"
        else:
            shown = lines
            tail  = ""
        text = Text("\n".join(shown) + tail, style=f"dim {WHITE}")
        self.console.print(
            Panel(text, title=Text("output", style=GREY),
                  border_style=DGREY, box=box.SIMPLE_HEAD, padding=(0, 2))
        )

    # ─── Todo panel ──────────────────────────────────────────────────────────
    def todo_panel(self, todos: list[dict]):
        if not todos:
            return
        icons = {
            "pending":     ("○", GREY),
            "in_progress": ("▶", ORANGE),
            "completed":   ("✓", GREEN),
            "cancelled":   ("✗", "red"),
        }
        body = Text()
        for t in todos:
            icon, col = icons.get(t.get("status","pending"), ("○", GREY))
            dim = t.get("status") in ("completed","cancelled")
            body.append(f"  {icon} ", style=f"bold {col}")
            body.append(t.get("content","") + "\n",
                        style=f"dim {WHITE}" if dim else WHITE)
        done  = sum(1 for t in todos if t.get("status")=="completed")
        total = len(todos)
        body.append("\n  ")
        body.append("█"*done,           style=f"bold {GREEN}")
        body.append("░"*(total-done),   style=DGREY)
        body.append(f"  {done}/{total}", style=f"dim {WHITE}")
        self.console.print()
        self.console.print(
            Panel(body, title=Text("📋 Tasks", style=f"bold {TEAL}"),
                  border_style=TEAL, box=box.MINIMAL, padding=(0,1))
        )

    # ─── File ops ────────────────────────────────────────────────────────────
    def file_write(self, path: str):
        self.console.print(f"  [bold #b48ead]▸ write[/bold #b48ead]  [{GREY}]{path}[/{GREY}]")

    def file_read(self, path: str):
        self.console.print(f"  [bold #b48ead]▸ read [/bold #b48ead]  [{GREY}]{path}[/{GREY}]")

    # ─── Status helpers ──────────────────────────────────────────────────────
    def error(self, msg: str):
        self.console.print()
        self.console.print(
            Panel(Text(msg, style="bold red"),
                  border_style="red", box=box.ROUNDED, padding=(0,2))
        )

    def success(self, msg: str):
        self.console.print(f"  [{GREEN}]✓ {msg}[/{GREEN}]")

    def info(self, msg: str):
        self.console.print(f"  [{GREY}]{msg}[/{GREY}]")

    def warn(self, msg: str):
        self.console.print(f"  [{ORANGE}]⚠ {msg}[/{ORANGE}]")

    def rule(self, title: str = ""):
        self.console.print(Rule(title, style=DGREY))

    # ─── Tools / Help ────────────────────────────────────────────────────────
    def tools_list(self, tools: list[tuple[str,str]]):
        t = Table(box=box.SIMPLE_HEAD, border_style=DGREY,
                  header_style=f"bold {TEAL}", pad_edge=False, show_header=True)
        t.add_column("Tool",        style=f"bold {ORANGE}", min_width=16)
        t.add_column("Description", style=DWHITE)
        for name, desc in tools:
            t.add_row(name, desc)
        self.console.print()
        self.console.print(Padding(t, (0,2)))

    def help(self):
        t = Table(box=box.SIMPLE_HEAD, border_style=DGREY,
                  header_style=f"bold {TEAL}", pad_edge=False, show_header=True)
        t.add_column("Command",     style=f"bold {ORANGE}", min_width=22)
        t.add_column("Description", style=DWHITE)
        for cmd, desc in [
            ("/help",         "Show this help"),
            ("/new",          "New session"),
            ("/clear",        "Clear history"),
            ("/model <name>", "Switch model"),
            ("/tools",        "List tools"),
            ("/save <file>",  "Save conversation"),
            ("/load <file>",  "Load conversation"),
            ("/history",      "Show last 10 messages"),
            ("/exit",         "Quit"),
        ]:
            t.add_row(cmd, desc)
        self.console.print()
        self.console.print(Padding(t, (0,2)))
        self.console.print(f"\n  [{DGREY}]Ctrl+C interrupt  ·  ↑↓ history[/{DGREY}]\n")

    # ─── Input prompt ────────────────────────────────────────────────────────
    def prompt(self, session_count: int = 0) -> str:
        self.console.print()
        if HAS_PT:
            try:
                return (pt_prompt(
                    HTML('<ansibrightwhite>❯  </ansibrightwhite>'),
                    history=self._pt_hist,
                    enable_history_search=True,
                ) or "").strip()
            except (EOFError, KeyboardInterrupt):
                return "/exit"
        else:
            try:
                return input(f"\033[1;33m❯  \033[0m").strip()
            except (EOFError, KeyboardInterrupt):
                return "/exit"

    def streaming_token(self, token: str, end: str = ""):
        print(token, end=end, flush=True)

    def clear(self):
        os.system("clear" if os.name != "nt" else "cls")

    # ─── Legacy compat ───────────────────────────────────────────────────────
    def todo_add(self, index: int, item: str):
        self.console.print(f"  [{ORANGE}]▶[/{ORANGE}] [{DWHITE}]{item[:80]}[/{DWHITE}]")

    def todo_done_msg(self, index: int, item: str, remaining: int):
        self.console.print(f"  [{GREEN}]✓[/{GREEN}] [{GREY}]{item[:80]}[/{GREY}]")
