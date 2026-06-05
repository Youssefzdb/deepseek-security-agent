#!/usr/bin/env python3
"""
bridge.py — stdio JSON bridge between Electron renderer and Python agent.

Protocol (stdin):  {"id":"1", "message":"...", "model":"...", "provider":"...", ...credentials}
Protocol (stdout): {"id":"1", "action":"...", "detail":"..."}

Special messages:
  __AUTH_CHECK__  → validate credentials / provider connectivity
  __SET_CREDS__   → store credentials
  __GET_MODELS__  → list available models for a provider
"""
import sys, json, os, traceback
sys.path.insert(0, os.path.dirname(__file__))

from core.providers import build_provider, auto_detect_provider, PROVIDER_PRESETS, FREE_MODELS_OPENROUTER, FREE_MODELS_OPENCODE
from core.agent     import Agent

# ── State ─────────────────────────────────────────────────────────────────────
_creds:  dict = {}
_agents: dict = {}  # key → Agent


def emit(id: str, action: str, detail: str):
    line = json.dumps({"id": id, "action": action, "detail": detail})
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _make_provider(req: dict):
    """Build provider from request fields + stored creds."""
    provider_id = req.get("provider") or _creds.get("provider") or "auto"
    model       = req.get("model")    or _creds.get("model")
    api_key     = req.get("api_key")  or _creds.get("api_key") or os.environ.get(
        PROVIDER_PRESETS.get(provider_id, {}).get("env_key", "") or "", ""
    )
    email       = req.get("email")    or _creds.get("email")    or os.environ.get("DEEPSEEK_EMAIL", "")
    password    = req.get("password") or _creds.get("password") or os.environ.get("DEEPSEEK_PASSWORD", "")
    base_url    = req.get("base_url") or _creds.get("base_url")

    if provider_id == "auto":
        return auto_detect_provider(email=email, password=password)

    return build_provider(
        provider_id = provider_id,
        model       = model,
        api_key     = api_key,
        base_url    = base_url,
        email       = email,
        password    = password,
    )


def _agent_key(req: dict) -> str:
    return f"{req.get('provider','auto')}:{req.get('model','default')}"


def get_agent(req: dict) -> Agent:
    key = _agent_key(req)
    if key not in _agents:
        provider    = _make_provider(req)
        _agents[key] = Agent(provider, max_rounds=40)
    else:
        # Update provider if credentials changed
        _agents[key].provider = _make_provider(req)
    return _agents[key]


# ── Main loop ─────────────────────────────────────────────────────────────────
for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue

    try:
        req = json.loads(raw)
    except Exception as e:
        sys.stderr.write(f"[bridge] Parse error: {e}\n")
        continue

    msg_id  = req.get("id", "0")
    message = req.get("message", "")

    # ── Store credentials ─────────────────────────────────────────────────────
    if message == "__SET_CREDS__":
        _creds.update({k: v for k, v in req.items() if k not in ("id", "message")})
        _agents.clear()
        continue

    # ── Auth check ────────────────────────────────────────────────────────────
    if message == "__AUTH_CHECK__":
        try:
            provider = _make_provider(req)
            # Quick connectivity test
            test_result = provider.chat(
                messages=[{"role": "user", "content": "hi"}],
                on_token=None,
            )
            emit(msg_id, "auth_ok", f"Connected to {provider.name} ({provider.model})")
        except Exception as e:
            emit(msg_id, "auth_fail", str(e))
        continue

    # ── List models ───────────────────────────────────────────────────────────
    if message == "__GET_MODELS__":
        provider_id = req.get("provider", "openrouter")
        try:
            provider = _make_provider(req)
            if hasattr(provider, "models"):
                models = provider.models()
                emit(msg_id, "models", json.dumps(models))
            else:
                # Return known free models
                free = FREE_MODELS_OPENROUTER if provider_id == "openrouter" else FREE_MODELS_OPENCODE
                emit(msg_id, "models", json.dumps(free))
        except Exception as e:
            emit(msg_id, "error", str(e))
        continue

    # ── Normal message ────────────────────────────────────────────────────────
    try:
        agent = get_agent(req)
    except Exception as e:
        emit(msg_id, "error", f"Provider error: {e}")
        continue

    def cb(action: str, detail: str, _id: str = msg_id):
        emit(_id, action, detail)

    try:
        agent.run(message, callback=cb)
    except Exception as e:
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        emit(msg_id, "done", f"[Agent error] {e}")
