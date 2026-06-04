#!/usr/bin/env python3
"""
DeepSeek Security Agent — Autonomous terminal agent for security testing.
Usage: python main.py [--email EMAIL] [--password PASS] [--model MODEL] [--tor]
"""
import argparse, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.client import DeepSeekClient
from core.agent import Agent
from ui.terminal import TerminalUI
from tools.executor import Executor
from tools.predefined import PredefinedTools


def main():
    parser = argparse.ArgumentParser(description="DeepSeek Security Agent")
    parser.add_argument("--email", default=None, help="DeepSeek email (or DEEPSEEK_EMAIL env)")
    parser.add_argument("--password", default=None, help="DeepSeek password (or DEEPSEEK_PASSWORD env)")
    parser.add_argument("--config", default=None, help="JSON config file with email/password")
    parser.add_argument("--model", default="deepseek-v3", help="Model: deepseek-v3, deepseek-r1, deepseek-coder")
    parser.add_argument("--tor", action="store_true", help="Use Tor proxy")
    parser.add_argument("--proxy", default=None, help="SOCKS5 proxy (socks5://127.0.0.1:9050)")
    parser.add_argument("--max-rounds", type=int, default=20, help="Max agent rounds per task")
    parser.add_argument("--message", nargs="*", help="Single message (non-interactive)")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    args = parser.parse_args()

    ui = TerminalUI()

    email = args.email or os.environ.get("DEEPSEEK_EMAIL")
    password = args.password or os.environ.get("DEEPSEEK_PASSWORD")

    if args.config and os.path.exists(args.config):
        try:
            with open(args.config) as f:
                cfg = json.load(f)
            email = email or cfg.get("email")
            password = password or cfg.get("password")
        except Exception:
            pass

    if not email or not password:
        ui.error("Email and password required. Use --email/--password, env vars, or --config")
        sys.exit(1)

    proxies = None
    if args.proxy:
        proxies = {"http": args.proxy, "https": args.proxy}
    elif args.tor:
        proxies = {"http": "socks5://127.0.0.1:9050", "https": "socks5://127.0.0.1:9050"}

    ui.info("Connecting to DeepSeek...")
    try:
        client = DeepSeekClient(email, password, proxies=proxies)
    except Exception as e:
        ui.error(f"Connection failed: {e}")
        sys.exit(1)

    ui.success(f"Connected as {email}")

    agent = Agent(client, model=args.model, max_rounds=args.max_rounds)

    tools = [
        ("exec", "Execute any shell command"),
        ("nmap", "Network scanning"),
        ("gobuster", "Directory/DNS brute-force"),
        ("nikto", "Web vulnerability scanner"),
        ("sqlmap", "SQL injection"),
        ("subfinder", "Subdomain enumeration"),
        ("whatweb", "Web technology detection"),
        ("curl", "HTTP requests"),
        ("dig", "DNS queries"),
        ("whois", "Domain information"),
        ("ping", "Connectivity test"),
        ("read/write/edit", "File operations"),
    ]

    def agent_callback(action, detail):
        if action == "thinking":
            ui.thinking(detail)
        elif action == "exec":
            ui.exec_command(detail)
        elif action == "output":
            ui.command_output(detail)
        elif action == "write":
            ui.info(f"Writing: {detail}")
        elif action == "read":
            ui.info(f"Reading: {detail}")
        elif action == "done":
            ui.agent_message(detail)

    if args.message:
        msg = " ".join(args.message)
        ui.user_message(msg)
        result = agent.run(msg, callback=agent_callback)
        ui.agent_message(result)
        return

    ui.banner()
    ui.info(f"Model: {args.model} | Max rounds: {args.max_rounds}")
    ui.info("Type /help for commands, /exit to quit")
    ui.tools_list(tools)

    msg_count = 0
    while True:
        try:
            user_input = ui.prompt(msg_count)
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        if user_input == "/exit":
            break
        elif user_input == "/help":
            ui.help()
            continue
        elif user_input == "/clear":
            agent.messages.clear()
            ui.success("History cleared")
            continue
        elif user_input == "/new":
            agent.messages.clear()
            try:
                client.create_session()
                ui.success("New session created")
            except Exception as e:
                ui.error(f"Session error: {e}")
            continue
        elif user_input == "/tools":
            ui.tools_list(tools)
            continue
        elif user_input.startswith("/model "):
            model = user_input.split(maxsplit=1)[1]
            agent.model = model
            ui.success(f"Model: {model}")
            continue
        elif user_input.startswith("/save "):
            path = user_input.split(maxsplit=1)[1]
            try:
                Path(path).write_text(json.dumps(agent.messages, indent=2))
                ui.success(f"Saved to {path}")
            except Exception as e:
                ui.error(f"Save error: {e}")
            continue
        elif user_input.startswith("/load "):
            path = user_input.split(maxsplit=1)[1]
            try:
                agent.messages = json.loads(Path(path).read_text())
                ui.success(f"Loaded from {path}")
            except Exception as e:
                ui.error(f"Load error: {e}")
            continue
        elif user_input == "/history":
            for h in client.http.session.cookies:
                ui.info(str(h))
            continue

        ui.user_message(user_input)
        msg_count += 1

        try:
            result = agent.run(user_input, callback=agent_callback)
            if result:
                ui.agent_message(result)
        except KeyboardInterrupt:
            ui.info("Interrupted")
        except Exception as e:
            ui.error(f"Error: {e}")

    ui.info("Goodbye!")


if __name__ == "__main__":
    main()
