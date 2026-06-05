#!/usr/bin/env python3
"""
agent.py — Plan-then-Execute agent with multi-provider support.

Architecture (OpenCode-style):
  1. Receive user message
  2. Decide: direct execution (≤3 steps) OR plan decomposition (>3 steps)
  3. Execute steps sequentially, calling tools as needed
  4. Report each action back to the UI via callback
"""
import json, re, subprocess, os, sys
from typing import Callable, Optional

from core.providers import OpenAICompatProvider, DeepSeekChatProvider, build_provider, auto_detect_provider

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are DeepSeek Security Agent — an elite autonomous security tool.

## Rules
- Respond ONLY with valid JSON. No markdown, no explanations outside JSON.
- For SIMPLE tasks (≤3 steps): respond with action JSON directly.
- For COMPLEX tasks (>3 steps): first produce a plan, then execute step-by-step.

## Response formats

### Direct execution (simple task):
{
  "type": "exec",
  "command": "nmap -sV 192.168.1.1",
  "reason": "brief reason"
}

### Plan (complex task):
{
  "type": "plan",
  "title": "Task title",
  "steps": [
    {"id": 1, "desc": "description", "command": "bash command or null"},
    {"id": 2, "desc": "description", "command": "bash command or null"}
  ]
}

### Answer (no execution needed):
{
  "type": "answer",
  "text": "your answer here"
}

### Tool call (file read/write):
{
  "type": "tool",
  "tool": "read_file|write_file|grep",
  "args": {"path": "...", "content": "..."}
}

### Done:
{
  "type": "done",
  "summary": "what was accomplished"
}

## Available tools:
nmap, ping, traceroute, whois, dig, curl, nc, ffuf, gobuster, nikto, whatweb,
hydra, john, hashcat, sqlmap, wpscan, dirb, enum4linux, smbclient, smtp_check,
amass, subfinder, dnsx, httpx, nuclei, arjun, xsstrike, commix, tshark,
read_file, write_file, grep, bash

## Format reminder
Always output valid JSON. No text before or after the JSON object.
"""

CONTINUE_PROMPT = """Continue with the next step. Output JSON only. Format reminder: valid JSON, no markdown."""

# ── Tool executor ─────────────────────────────────────────────────────────────
def _run_cmd(cmd: str, timeout: int = 30) -> str:
    """Run a shell command and return output (truncated)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        out = (result.stdout or "") + (result.stderr or "")
        lines = out.strip().split("\n")
        if len(lines) > 60:
            out = "\n".join(lines[:60]) + f"\n... ({len(lines)-60} more lines)"
        return out.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[timeout after {timeout}s]"
    except Exception as e:
        return f"[error: {e}]"


def _tool_dispatch(tool: str, args: dict) -> str:
    """Execute a built-in tool and return result."""
    if tool == "read_file":
        path = args.get("path", "")
        try:
            with open(path) as f:
                content = f.read()
            lines = content.split("\n")
            if len(lines) > 80:
                return "\n".join(lines[:80]) + f"\n... ({len(lines)-80} more lines)"
            return content
        except Exception as e:
            return f"[read error: {e}]"

    if tool == "write_file":
        path    = args.get("path", "")
        content = args.get("content", "")
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return f"Written {len(content)} bytes to {path}"
        except Exception as e:
            return f"[write error: {e}]"

    if tool == "grep":
        pattern = args.get("pattern", "")
        path    = args.get("path", ".")
        return _run_cmd(f"grep -r --include='*.py' --include='*.ts' --include='*.js' -n {pattern!r} {path}", timeout=10)

    if tool == "bash":
        return _run_cmd(args.get("command", "echo 'no command'"), timeout=args.get("timeout", 30))

    return f"[unknown tool: {tool}]"


# ── JSON extraction ───────────────────────────────────────────────────────────
def _extract_json(text: str) -> Optional[dict]:
    """Extract first valid JSON object from text."""
    # Direct parse
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # Find first {...}
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    # Try to find between code fences
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None


# ── Agent class ───────────────────────────────────────────────────────────────
class Agent:
    def __init__(
        self,
        provider,               # OpenAICompatProvider | DeepSeekChatProvider
        max_rounds: int = 40,
        callback:   Callable[[str, str], None] | None = None,
    ):
        self.provider   = provider
        self.max_rounds = max_rounds
        self.callback   = callback
        self.history:   list[dict] = []

    def _emit(self, action: str, detail: str):
        if self.callback:
            self.callback(action, detail)

    def _chat(self, messages: list[dict]) -> str:
        """Call the provider and collect full response."""
        tokens = []
        def on_tok(t):
            tokens.append(t)

        try:
            result = self.provider.chat(messages=messages, on_token=on_tok)
            return result.get("content", "".join(tokens))
        except Exception as e:
            return json.dumps({"type": "done", "summary": f"Provider error: {e}"})

    def _exec_step(self, step: dict) -> str:
        """Execute a plan step and return output."""
        cmd  = step.get("command")
        desc = step.get("desc", "")

        self._emit("step_start", json.dumps({"desc": desc, "command": cmd}))

        if cmd:
            self._emit("exec", cmd)
            output = _run_cmd(cmd)
            self._emit("output", output)
            return output
        return "(no command — informational step)"

    def run(self, user_message: str, callback: Callable[[str, str], None] | None = None):
        """Main entry point."""
        if callback:
            self.callback = callback

        self._emit("thinking", "Analyzing task…")

        # Build messages
        messages = [
            {"role": "system",  "content": SYSTEM_PROMPT},
            *self.history,
            {"role": "user",    "content": user_message},
        ]

        raw = self._chat(messages)
        action = _extract_json(raw)

        if not action:
            # Model returned plain text — treat as answer
            self._emit("done", raw or "No response.")
            self._history_append(user_message, raw)
            return

        atype = action.get("type", "answer")

        # ── Direct execution ──────────────────────────────────────────────────
        if atype == "exec":
            cmd    = action.get("command", "")
            reason = action.get("reason", "")
            self._emit("thinking", reason or "Executing…")
            self._emit("exec", cmd)
            output = _run_cmd(cmd)
            self._emit("output", output)
            # Follow-up: summarize
            self._finish_with_summary(messages, user_message, raw, output)

        # ── Plan → step-by-step ───────────────────────────────────────────────
        elif atype == "plan":
            steps = action.get("steps", [])
            self._emit("todo_update", json.dumps([
                {"content": s["desc"], "status": "pending"} for s in steps
            ]))
            outputs = []
            for i, step in enumerate(steps):
                # Mark in_progress
                todo = [
                    {"content": s["desc"],
                     "status": "completed" if j < i else ("in_progress" if j == i else "pending")}
                    for j, s in enumerate(steps)
                ]
                self._emit("todo_update", json.dumps(todo))
                out = self._exec_step(step)
                outputs.append(f"Step {step['id']}: {out[:200]}")

            # All done
            self._emit("todo_update", json.dumps([
                {"content": s["desc"], "status": "completed"} for s in steps
            ]))
            summary = "\n".join(outputs)
            self._emit("done", f"✅ {action.get('title','Task')} complete.\n{summary[:400]}")
            self._history_append(user_message, raw)

        # ── Tool call ─────────────────────────────────────────────────────────
        elif atype == "tool":
            tool   = action.get("tool", "")
            args   = action.get("args", {})
            self._emit("thinking", f"Using tool: {tool}")
            if tool in ("write_file",):
                self._emit("write", args.get("path", ""))
            elif tool == "read_file":
                self._emit("read", args.get("path", ""))
            result = _tool_dispatch(tool, args)
            self._emit("output", result)
            # Continue with result in context
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user",      "content": f"Tool result:\n{result}\n\nContinue. {CONTINUE_PROMPT}"})
            self._run_continuation(messages, user_message, depth=1)

        # ── Plain answer ──────────────────────────────────────────────────────
        elif atype == "answer":
            self._emit("done", action.get("text", raw))
            self._history_append(user_message, raw)

        # ── Already done ──────────────────────────────────────────────────────
        elif atype == "done":
            self._emit("done", action.get("summary", "Done."))
            self._history_append(user_message, raw)

        else:
            self._emit("done", raw)
            self._history_append(user_message, raw)

    def _run_continuation(self, messages: list[dict], user_msg: str, depth: int = 0):
        """Continue after a tool call (up to max_rounds)."""
        if depth >= self.max_rounds:
            self._emit("done", "Max rounds reached.")
            return

        self._emit("thinking", "Continuing…")
        raw    = self._chat(messages)
        action = _extract_json(raw)

        if not action or action.get("type") in ("done", "answer"):
            text = (action or {}).get("text") or (action or {}).get("summary") or raw
            self._emit("done", text)
            self._history_append(user_msg, raw)
            return

        atype = action.get("type")
        if atype == "exec":
            cmd = action.get("command", "")
            self._emit("exec", cmd)
            out = _run_cmd(cmd)
            self._emit("output", out)
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user",      "content": f"Output:\n{out}\n\nContinue. {CONTINUE_PROMPT}"})
            self._run_continuation(messages, user_msg, depth + 1)

        elif atype == "tool":
            tool   = action.get("tool", "")
            args   = action.get("args", {})
            result = _tool_dispatch(tool, args)
            self._emit("output", result)
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user",      "content": f"Tool result:\n{result}\n\nContinue. {CONTINUE_PROMPT}"})
            self._run_continuation(messages, user_msg, depth + 1)

        else:
            self._emit("done", raw)
            self._history_append(user_msg, raw)

    def _finish_with_summary(self, messages, user_msg, assistant_raw, cmd_output):
        """After a direct exec, ask model to summarize the output."""
        messages.append({"role": "assistant", "content": assistant_raw})
        messages.append({
            "role": "user",
            "content": (
                f"Command output:\n```\n{cmd_output[:1500]}\n```\n"
                f"Summarize findings or continue if needed. {CONTINUE_PROMPT}"
            )
        })
        raw    = self._chat(messages)
        action = _extract_json(raw)
        if action and action.get("type") in ("exec", "plan", "tool"):
            self._run_continuation(messages, user_msg, depth=1)
        else:
            text = ""
            if action:
                text = action.get("text") or action.get("summary") or raw
            else:
                text = raw
            self._emit("done", text or "Done.")
            self._history_append(user_msg, raw)

    def _history_append(self, user_msg: str, assistant_raw: str):
        """Keep last 10 turns in history."""
        self.history.append({"role": "user",      "content": user_msg})
        self.history.append({"role": "assistant", "content": assistant_raw})
        if len(self.history) > 20:
            self.history = self.history[-20:]
