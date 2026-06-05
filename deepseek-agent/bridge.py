#!/usr/bin/env python3
"""
bridge.py — stdio JSON bridge between the TypeScript UI and the Python agent.

Protocol:
  stdin  (one JSON line per message):  {"id": "1", "message": "...", "model": "..."}
  stdout (multiple JSON lines per run): {"id": "1", "action": "exec|output|done|...", "detail": "..."}
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))

from core.client import DeepSeekClient
from core.agent  import Agent

# ── Credentials ───────────────────────────────────────────────────────────────
EMAIL    = os.environ.get("DEEPSEEK_EMAIL", "")
PASSWORD = os.environ.get("DEEPSEEK_PASSWORD", "")

if not EMAIL or not PASSWORD:
    sys.stderr.write("[bridge] DEEPSEEK_EMAIL / DEEPSEEK_PASSWORD not set\n")
    sys.exit(1)

# ── Connect (once) ────────────────────────────────────────────────────────────
try:
    client = DeepSeekClient(EMAIL, PASSWORD)
except Exception as e:
    sys.stderr.write(f"[bridge] Connection failed: {e}\n")
    sys.exit(1)

agents: dict[str, Agent] = {}


def emit(id: str, action: str, detail: str):
    """Write a JSON event line to stdout (read by the TS process)."""
    line = json.dumps({"id": id, "action": action, "detail": detail})
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def get_agent(msg_id: str, model: str) -> Agent:
    if model not in agents:
        agents[model] = Agent(client, model=model, max_rounds=40)
    return agents[model]


# ── Main loop ─────────────────────────────────────────────────────────────────
for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    try:
        req     = json.loads(raw)
        msg_id  = req["id"]
        message = req["message"]
        model   = req.get("model", "deepseek-coder")
    except Exception as e:
        sys.stderr.write(f"[bridge] Parse error: {e}\n")
        continue

    agent = get_agent(msg_id, model)

    def callback(action: str, detail: str, _id: str = msg_id):
        emit(_id, action, detail)

    try:
        agent.run(message, callback=callback)
    except Exception as e:
        emit(msg_id, "done", f"[Error] {e}")
