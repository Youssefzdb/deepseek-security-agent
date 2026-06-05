#!/usr/bin/env python3
"""
DeepSeek Security Agent — Autonomous terminal agent.
Usage: python main.py [--email EMAIL] [--password PASS] [--model MODEL]
"""
import argparse, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.client  import DeepSeekClient
from core.agent   import Agent
from ui.terminal  import TerminalUI
from tools.predefined import PredefinedTools


TOOLS = [
    ("exec",          "Execute any shell command"),
    ("nmap",          "Network scanning"),
    ("gobuster",      "Directory / DNS brute-force"),
    ("nikto",         "Web vulnerability scanner"),
    ("sqlmap",        "SQL injection"),
    ("subfinder",     "Subdomain enumeration"),
    ("whatweb",       "Web technology detection"),
    ("curl",          "HTTP requests"),
    ("dig",           "DNS queries"),
    ("whois",         "Domain info"),
    ("ping",          "Connectivity test"),
    ("read/write",    "File operations"),
]


def build_callback(agent: Agent, ui: TerminalUI):
    """Build the agent callback that drives the UI."""
    import json as _json

    def cb(action: str, detail: str):
        if action == "thinking":
            ui.thinking(detail)

        elif action == "exec":
            try:
                tc  = _json.loads(detail)
                cmd = tc.get("arguments", {}).get("command", detail)
            except Exception:
                cmd = detail
            ui.exec_command(cmd)

        elif action == "output":
            ui.command_output(detail)

        elif action == "write":
            ui.file_write(detail)

        elif action == "read":
            ui.file_read(detail)

        elif action == "todo_update":
            ui.todo_panel(agent.todos)

        elif action == "todo_summary":
            ui.todo_panel(agent.todos)
            ui.rule()

        elif action == "done":
            text = detail if detail and detail != "TASK_DONE" else "✅ Done."
            ui.agent_message(text)

    return cb


def main():
    parser = argparse.ArgumentParser(description="DeepSeek Security Agent")
    parser.add_argument("--email",      default=None)
    parser.add_argument("--password",   default=None)
    parser.add_argument("--config",     default=None, help="JSON config {email, password}")
    parser.add_argument("--model",      default="deepseek-coder",
                        help="deepseek-coder | deepseek-v3 | deepseek-r1")
    parser.add_argument("--tor",        action="store_true")
    parser.add_argument("--proxy",      default=None)
    parser.add_argument("--max-rounds", type=int, default=20)
    parser.add_argument("--message",    nargs="*", help="One-shot mode")
    parser.add_argument("--no-color",   action="store_true")
    args = parser.parse_args()

    ui = TerminalUI(model=args.model)

    # ── Credentials ───────────────────────────────────────────────────────────
    email    = args.email    or os.environ.get("DEEPSEEK_EMAIL")
    password = args.password or os.environ.get("DEEPSEEK_PASSWORD")

    if args.config and os.path.exists(args.config):
        try:
            cfg      = json.loads(Path(args.config).read_text())
            email    = email    or cfg.get("email")
            password = password or cfg.get("password")
        except Exception:
            pass

    if not email or not password:
        ui.error("Email and password required.\n"
                 "Use --email/--password, env DEEPSEEK_EMAIL/DEEPSEEK_PASSWORD, or --config.")
        sys.exit(1)

    # ── Proxy ─────────────────────────────────────────────────────────────────
    proxies = None
    if args.proxy:
        proxies = {"http": args.proxy, "https": args.proxy}
    elif args.tor:
        proxies = {"http": "socks5://127.0.0.1:9050", "https": "socks5://127.0.0.1:9050"}

    # ── Connect ───────────────────────────────────────────────────────────────
    ui.info("Connecting to DeepSeek…")
    try:
        client = DeepSeekClient(email, password, proxies=proxies)
    except Exception as e:
        ui.error(f"Connection failed: {e}")
        sys.exit(1)

    ui.success(f"Connected  ·  {email}")

    agent    = Agent(client, model=args.model, max_rounds=args.max_rounds)
    callback = build_callback(agent, ui)

    # ── One-shot mode ─────────────────────────────────────────────────────────
    if args.message:
        msg = " ".join(args.message)
        ui.user_message(msg)
        agent.run(msg, callback=callback)
        return

    # ── Interactive mode ──────────────────────────────────────────────────────
    ui.banner()
    ui.info(f"Model: [bold]{args.model}[/bold]  ·  max-rounds: {args.max_rounds}")
    ui.tools_list(TOOLS)

    msg_count = 0
    while True:
        try:
            user_input = ui.prompt(msg_count)
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        # ── Slash commands ─────────────────────────────────────────────────────
        if user_input == "/exit":
            break

        elif user_input == "/help":
            ui.help()

        elif user_input == "/clear":
            agent.clear()
            ui.success("History cleared")

        elif user_input == "/new":
            agent.clear()
            try:
                client.create_session()
                ui.success("New session created")
            except Exception as e:
                ui.error(f"Session error: {e}")

        elif user_input == "/tools":
            ui.tools_list(TOOLS)

        elif user_input.startswith("/model "):
            m = user_input.split(maxsplit=1)[1].strip()
            agent.model = m
            ui.model    = m
            ui.success(f"Model switched → {m}")

        elif user_input.startswith("/save "):
            path = user_input.split(maxsplit=1)[1].strip()
            try:
                Path(path).write_text(json.dumps(agent.messages, indent=2))
                ui.success(f"Saved → {path}")
            except Exception as e:
                ui.error(f"Save error: {e}")

        elif user_input.startswith("/load "):
            path = user_input.split(maxsplit=1)[1].strip()
            try:
                agent.messages = json.loads(Path(path).read_text())
                ui.success(f"Loaded ← {path}")
            except Exception as e:
                ui.error(f"Load error: {e}")

        elif user_input == "/history":
            for i, m in enumerate(agent.messages[-10:]):
                role = m.get("role", "?")
                txt  = m.get("content", "")[:80]
                ui.info(f"[{i}] {role}: {txt}")

        # ── Task ──────────────────────────────────────────────────────────────
        else:
            ui.user_message(user_input)
            msg_count += 1
            try:
                agent.run(user_input, callback=callback)
            except KeyboardInterrupt:
                ui.warn("Interrupted")
            except Exception as e:
                ui.error(f"Agent error: {e}")

    ui.info("Goodbye 👋")


if __name__ == "__main__":
    main()
