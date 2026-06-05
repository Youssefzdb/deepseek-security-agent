#!/usr/bin/env python3
"""
DeepSeek Security Agent — Autonomous terminal agent.
Usage: python main.py [--email EMAIL] [--password PASS] [--model MODEL]
"""
import argparse, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.client      import DeepSeekClient
from core.agent       import Agent
from ui.terminal      import TerminalUI
from tools.executor   import Executor
from tools.predefined import PredefinedTools


# ── All available tools (27 + exec + file ops) ────────────────────────────────
TOOLS = [
    # Network recon
    ("nmap",           "Port scan & service detection"),
    ("ping",           "Connectivity test"),
    ("traceroute",     "Route tracing"),
    ("whois",          "Domain / IP info"),
    ("dig",            "DNS queries"),
    ("curl",           "HTTP requests & headers"),
    ("nc_banner",      "TCP banner grab"),
    # Web recon
    ("whatweb",        "Web technology fingerprint"),
    ("nikto",          "Web vulnerability scanner"),
    ("wpscan",         "WordPress scanner"),
    # Dir / DNS brute-force
    ("gobuster_dir",   "Web directory brute-force"),
    ("gobuster_dns",   "DNS subdomain brute-force"),
    ("dirb",           "Alternative dir brute-force"),
    ("ffuf",           "Fast web fuzzer"),
    # Subdomain enumeration
    ("subfinder",      "Subdomain enumeration"),
    ("amass",          "Advanced subdomain enum"),
    # OSINT
    ("theHarvester",   "Email / host OSINT"),
    ("shodan_cli",     "Shodan search"),
    # Exploitation
    ("sqlmap",         "SQL injection"),
    ("hydra",          "Credential brute-force"),
    ("metasploit_run", "Run Metasploit resource file"),
    # SMB / AD
    ("enum4linux",     "SMB enumeration"),
    ("smbclient",      "SMB client access"),
    # Password cracking
    ("hash_identify",  "Hash type identification"),
    ("john",           "John the Ripper"),
    ("hashcat",        "GPU hash cracker"),
    # Built-in
    ("exec",           "Execute any shell command"),
    ("read_file",      "Read file contents"),
    ("write_file",     "Write / create file"),
    ("edit_file",      "Patch file (old → new)"),
]


def build_callback(agent: Agent, ui: TerminalUI):
    """Wire agent events → UI rendering."""
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
    parser = argparse.ArgumentParser(
        description="DeepSeek Security Agent",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--email",      default=None,  help="DeepSeek account email")
    parser.add_argument("--password",   default=None,  help="DeepSeek account password")
    parser.add_argument("--config",     default=None,  help="JSON config file {email, password}")
    parser.add_argument("--model",      default="deepseek-coder",
                        help="deepseek-coder (default) | deepseek-v3 | deepseek-r1")
    parser.add_argument("--max-rounds", default=40,    type=int,
                        help="Max executor rounds per task (default: 40)")
    parser.add_argument("--tor",        action="store_true", help="Route through Tor (socks5://127.0.0.1:9050)")
    parser.add_argument("--proxy",      default=None,  help="HTTP/SOCKS proxy URL")
    parser.add_argument("-m", "--message", nargs="+",  help="One-shot message (non-interactive)")
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
        ui.error(
            "Credentials required.\n"
            "Use --email/--password, env vars DEEPSEEK_EMAIL / DEEPSEEK_PASSWORD,\n"
            "or --config path/to/config.json"
        )
        sys.exit(1)

    # ── Proxy / Tor ───────────────────────────────────────────────────────────
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
    ui.info(f"Model: [bold]{args.model}[/bold]  ·  max-rounds: {args.max_rounds}  ·  {len(TOOLS)} tools loaded")
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

        cmd = user_input.lower().strip()

        # ── Slash commands ─────────────────────────────────────────────────────
        if cmd == "/exit" or cmd == "/quit":
            break

        elif cmd == "/help":
            ui.help()

        elif cmd == "/clear":
            agent.clear()
            ui.success("Conversation history cleared")

        elif cmd == "/new":
            agent.clear()
            try:
                client.create_session()
                ui.success("New chat session created")
            except Exception as e:
                ui.error(f"Session error: {e}")

        elif cmd == "/tools":
            ui.tools_list(TOOLS)

        elif user_input.startswith("/model "):
            m = user_input.split(maxsplit=1)[1].strip()
            agent.model = m
            ui.model    = m
            ui.success(f"Model → {m}")

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

        elif cmd == "/history":
            msgs = agent.messages[-10:]
            if not msgs:
                ui.info("No history yet.")
            for i, m in enumerate(msgs):
                role = m.get("role", "?")
                txt  = str(m.get("content", ""))[:100]
                ui.info(f"[{i}] {role}: {txt}")

        elif cmd == "/status":
            ui.info(f"Model     : {agent.model}")
            ui.info(f"Messages  : {len(agent.messages)}")
            ui.info(f"Todos     : {len(agent.todos)}")
            ui.info(f"Tools used: {', '.join(agent.tools_used[-5:]) or 'none'}")

        # ── Task ──────────────────────────────────────────────────────────────
        else:
            ui.user_message(user_input)
            msg_count += 1
            try:
                agent.run(user_input, callback=callback)
            except KeyboardInterrupt:
                ui.warn("Interrupted — Ctrl+C again to exit")
            except Exception as e:
                ui.error(f"Agent error: {e}")

    ui.info("Goodbye 👋")


if __name__ == "__main__":
    main()
