#!/usr/bin/env python3
"""
bridge.py — stdio JSON bridge between Electron renderer and Python agent.

Protocol (stdin):
  {"id":"1", "message":"...", "model":"...", "email":"...", "password":"..."}

Special messages:
  message == "__AUTH_CHECK__"  → try to login, respond with auth_ok or auth_fail
  message == "__SET_CREDS__"   → store credentials for future sessions

Protocol (stdout):
  {"id":"1", "action":"exec|output|done|error|auth_ok|auth_fail", "detail":"..."}
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))

from core.client import DeepSeekClient
from core.agent  import Agent

# ── Credentials store ─────────────────────────────────────────────────────────
EMAIL    = os.environ.get("DEEPSEEK_EMAIL", "")
PASSWORD = os.environ.get("DEEPSEEK_PASSWORD", "")

# Runtime client (created lazily when credentials arrive)
_client: DeepSeekClient | None = None
_agents: dict[str, Agent] = {}


def emit(id: str, action: str, detail: str):
    line = json.dumps({"id": id, "action": action, "detail": detail})
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def get_client(email: str, password: str) -> DeepSeekClient:
    global _client, EMAIL, PASSWORD
    if _client is None or email != EMAIL or password != PASSWORD:
        _client  = DeepSeekClient(email, password)
        EMAIL    = email
        PASSWORD = password
        _agents.clear()
    return _client


def get_agent(model: str) -> Agent:
    global _client
    if _client is None:
        raise RuntimeError("Not authenticated")
    if model not in _agents:
        _agents[model] = Agent(_client, model=model, max_rounds=40)
    return _agents[model]


# ── Main loop ─────────────────────────────────────────────────────────────────
for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue

    try:
        req      = json.loads(raw)
        msg_id   = req.get("id", "0")
        message  = req.get("message", "")
        model    = req.get("model", "deepseek-coder")
        email    = req.get("email", EMAIL)
        password = req.get("password", PASSWORD)
    except Exception as e:
        sys.stderr.write(f"[bridge] Parse error: {e}\n")
        continue

    # ── Special: store credentials only ──────────────────────────────────────
    if message == "__SET_CREDS__":
        EMAIL    = email
        PASSWORD = password
        _client  = None          # will reconnect on next real message
        _agents.clear()
        continue

    # ── Special: auth check from login screen ─────────────────────────────────
    if message == "__AUTH_CHECK__":
        if not email or not password:
            emit(msg_id, "auth_fail", "Email and password are required.")
            continue
        try:
            get_client(email, password)   # triggers real login
            emit(msg_id, "auth_ok", "Authenticated successfully.")
        except Exception as e:
            emit(msg_id, "auth_fail", str(e))
        continue

    # ── Normal agent message ──────────────────────────────────────────────────
    if not email or not password:
        emit(msg_id, "error", "Not authenticated. Please restart and log in.")
        continue

    try:
        client = get_client(email, password)
        agent  = get_agent(model)
    except Exception as e:
        emit(msg_id, "error", f"[Auth error] {e}")
        continue

    def callback(action: str, detail: str, _id: str = msg_id):
        emit(_id, action, detail)

    try:
        agent.run(message, callback=callback)
    except Exception as e:
        emit(msg_id, "done", f"[Error] {e}")
