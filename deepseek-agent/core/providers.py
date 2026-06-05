#!/usr/bin/env python3
"""
providers.py — Multi-provider AI client.

Supported backends:
  - deepseek_chat   : DeepSeek chat.deepseek.com (PoW auth, free)
  - openrouter      : openrouter.ai  (requires OPENROUTER_API_KEY, free tier available)
  - opencode        : opencode.ai/zen/v1 (requires OPENCODE_API_KEY, free models)
  - openai_compat   : any OpenAI-compatible endpoint
  - deepseek_api    : api.deepseek.com (requires DEEPSEEK_API_KEY, paid but cheap)
"""
import json, os, time, requests
from typing import Iterator, Optional, Callable

# ── Token / streaming helpers ─────────────────────────────────────────────────

def _sse_lines(resp: requests.Response) -> Iterator[str]:
    """Yield data lines from an SSE stream."""
    for raw in resp.iter_lines(decode_unicode=True):
        if raw.startswith("data:"):
            yield raw[5:].strip()

def _parse_token(line: str) -> Optional[str]:
    """Parse a single SSE data line → token text (or None)."""
    if not line or line == "[DONE]":
        return None
    try:
        d = json.loads(line)
        # OpenAI style
        delta = d.get("choices", [{}])[0].get("delta", {})
        return delta.get("content") or ""
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. OpenAI-compatible provider (OpenRouter, OpenCode Zen, DeepSeek API, etc.)
# ─────────────────────────────────────────────────────────────────────────────
class OpenAICompatProvider:
    """Generic OpenAI-compatible streaming provider."""

    def __init__(
        self,
        base_url:  str,
        api_key:   str,
        model:     str,
        name:      str = "openai-compat",
        extra_headers: dict | None = None,
        timeout:   int = 90,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key  = api_key
        self.model    = model
        self.name     = name
        self.extra_headers = extra_headers or {}
        self.timeout  = timeout

    @property
    def headers(self) -> dict:
        h = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        h.update(self.extra_headers)
        return h

    def chat(
        self,
        messages:  list[dict],
        tools:     list[dict] | None = None,
        on_token:  Callable[[str], None] | None = None,
    ) -> dict:
        """
        Stream a chat completion.
        Returns { "content": str, "tool_calls": list, "model": str }
        """
        payload: dict = {
            "model":       self.model,
            "messages":    messages,
            "stream":      True,
            "temperature": 0.0,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        with requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=payload,
            stream=True,
            timeout=self.timeout,
        ) as resp:
            resp.raise_for_status()
            return self._collect(resp, on_token)

    def _collect(self, resp: requests.Response, on_token) -> dict:
        content = ""
        tool_calls_acc: dict[int, dict] = {}

        for line in _sse_lines(resp):
            if not line or line == "[DONE]":
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue

            choice = (d.get("choices") or [{}])[0]
            delta  = choice.get("delta", {})

            # Regular text token
            tok = delta.get("content") or ""
            if tok:
                content += tok
                if on_token:
                    on_token(tok)

            # Tool call chunks
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {
                        "id":       tc.get("id", ""),
                        "type":     "function",
                        "function": {"name": "", "arguments": ""},
                    }
                fn = tc.get("function", {})
                tool_calls_acc[idx]["function"]["name"]      += fn.get("name", "")
                tool_calls_acc[idx]["function"]["arguments"] += fn.get("arguments", "")

        tool_calls = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
        return {
            "content":    content,
            "tool_calls": tool_calls,
            "model":      self.model,
        }

    def models(self) -> list[str]:
        """Return list of available model IDs."""
        try:
            r = requests.get(
                f"{self.base_url}/models",
                headers=self.headers,
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            models = data.get("data", data) if isinstance(data, dict) else data
            return [m.get("id", "") for m in models if isinstance(m, dict)]
        except Exception:
            return []


# ─────────────────────────────────────────────────────────────────────────────
# 2. DeepSeek chat.deepseek.com (PoW auth, completely free)
# ─────────────────────────────────────────────────────────────────────────────
class DeepSeekChatProvider:
    """
    Wraps the existing DeepSeekClient (PoW-based, free).
    Falls back gracefully if the PoW lib isn't available.
    """

    def __init__(self, email: str, password: str, model: str = "deepseek-coder"):
        # Lazy import — only fails if you use this provider without credentials
        from core.client import DeepSeekClient
        self.client = DeepSeekClient(email, password)
        self.model  = model
        self.name   = "deepseek-chat"

    def chat(
        self,
        messages:  list[dict],
        tools:     list[dict] | None = None,
        on_token:  Callable[[str], None] | None = None,
    ) -> dict:
        # Convert messages → single prompt string (DeepSeek chat API style)
        content = self.client.chat(
            messages  = messages,
            model     = self.model,
            on_token  = on_token,
        )
        return {
            "content":    content,
            "tool_calls": [],
            "model":      self.model,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Provider factory
# ─────────────────────────────────────────────────────────────────────────────

FREE_MODELS_OPENROUTER = [
    "qwen/qwen3-coder:free",
    "openai/gpt-oss-120b:free",
    "moonshotai/kimi-k2.6:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-4-31b-it:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "openrouter/free",
]

FREE_MODELS_OPENCODE = [
    "deepseek-v4-flash-free",
    "mimo-v2.5-free",
    "qwen3.6-plus-free",
    "minimax-m3-free",
    "nemotron-3-super-free",
    "nemotron-3-ultra-free",
    "big-pickle",
]

PROVIDER_PRESETS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_key":  "OPENROUTER_API_KEY",
        "default_model": "qwen/qwen3-coder:free",
        "extra_headers": {
            "HTTP-Referer":  "https://github.com/Youssefzdb/deepseek-security-agent",
            "X-Title":       "DeepSeek Security Agent",
        },
    },
    "opencode": {
        "base_url": "https://opencode.ai/zen/v1",
        "env_key":  "OPENCODE_API_KEY",
        "default_model": "deepseek-v4-flash-free",
    },
    "deepseek_api": {
        "base_url": "https://api.deepseek.com/v1",
        "env_key":  "DEEPSEEK_API_KEY",
        "default_model": "deepseek-coder",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_key":  "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "env_key":  None,
        "default_model": "qwen2.5-coder:7b",
    },
}


def build_provider(
    provider_id: str = "openrouter",
    model:       str | None = None,
    api_key:     str | None = None,
    base_url:    str | None = None,
    email:       str | None = None,
    password:    str | None = None,
) -> OpenAICompatProvider | DeepSeekChatProvider:
    """
    Build the right provider from id / env / args.

    Priority: explicit args > env vars > preset defaults.
    """
    if provider_id == "deepseek_chat":
        return DeepSeekChatProvider(
            email    = email    or os.environ.get("DEEPSEEK_EMAIL", ""),
            password = password or os.environ.get("DEEPSEEK_PASSWORD", ""),
            model    = model or "deepseek-coder",
        )

    preset = PROVIDER_PRESETS.get(provider_id, {})
    env_key_name = preset.get("env_key")

    resolved_key     = api_key  or (os.environ.get(env_key_name, "") if env_key_name else "")
    resolved_url     = base_url or preset.get("base_url", "")
    resolved_model   = model    or preset.get("default_model", "gpt-3.5-turbo")
    resolved_headers = preset.get("extra_headers", {})
    resolved_name    = provider_id

    return OpenAICompatProvider(
        base_url       = resolved_url,
        api_key        = resolved_key,
        model          = resolved_model,
        name           = resolved_name,
        extra_headers  = resolved_headers,
    )


def auto_detect_provider(
    email: str = "", password: str = ""
) -> OpenAICompatProvider | DeepSeekChatProvider:
    """
    Pick the best available provider automatically:
    1. OPENROUTER_API_KEY → openrouter/qwen3-coder:free
    2. OPENCODE_API_KEY   → opencode/deepseek-v4-flash-free
    3. DEEPSEEK_API_KEY   → deepseek_api/deepseek-coder
    4. GROQ_API_KEY       → groq/llama-3.3-70b
    5. email+password     → deepseek_chat (PoW)
    6. OLLAMA running     → ollama/qwen2.5-coder:7b
    """
    if os.environ.get("OPENROUTER_API_KEY"):
        return build_provider("openrouter")
    if os.environ.get("OPENCODE_API_KEY"):
        return build_provider("opencode")
    if os.environ.get("DEEPSEEK_API_KEY"):
        return build_provider("deepseek_api")
    if os.environ.get("GROQ_API_KEY"):
        return build_provider("groq")
    if email and password:
        return build_provider("deepseek_chat", email=email, password=password)
    # Try Ollama
    try:
        r = requests.get("http://localhost:11434/api/version", timeout=2)
        if r.status_code == 200:
            return build_provider("ollama")
    except Exception:
        pass
    raise RuntimeError(
        "No AI provider configured. Set OPENROUTER_API_KEY, OPENCODE_API_KEY, "
        "DEEPSEEK_API_KEY, GROQ_API_KEY, or provide email/password for DeepSeek chat."
    )
