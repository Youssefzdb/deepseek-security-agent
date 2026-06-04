#!/usr/bin/env python3
"""
DeepSeek Agent — mirrors opencode agent loop.

Key design (from opencode source):
  - Single agentic loop: model decides EVERYTHING
  - todowrite is a TOOL, not a planning phase
  - Model chooses when 3+ steps need a todo list
  - Tool results appended to history, loop continues
  - Loop ends on plain-text response (no JSON = done)
"""
import json, re, subprocess, os, time
from pathlib import Path
from .client import DeepSeekClient

# ─── System prompt ─────────────────────────────────────────────────────────────
# Mirrors opencode Gemini/Claude prompt philosophy:
# - Concise, no chitchat, tool-first
# - Todowrite rules copied from opencode/src/tool/todowrite.txt
SYSTEM_PROMPT = """You are an autonomous terminal agent on a real Linux system.
For every action, output a raw JSON tool call. When fully done, output plain text.

## Tool formats (use any of these — all are accepted):
{"name":"exec","arguments":{"command":"CMD"}}
{"name":"write_file","arguments":{"path":"/abs/path","content":"TEXT"}}
{"name":"read_file","arguments":{"path":"/abs/path"}}
{"name":"edit_file","arguments":{"path":"/abs/path","old":"OLD","new":"NEW"}}
{"name":"todowrite","arguments":{"todos":[{"content":"task","status":"pending","priority":"high"}]}}

Alternative exec format also accepted:
{"tool":"run_command","command":"CMD"}

## todowrite — when to use (from opencode rules)
USE when task has 3+ distinct steps, multiple tasks given, or mid-work sub-tasks found.
SKIP for single actions or informational questions.

## todowrite — rules
- Create ALL todos upfront (status=pending) before starting work
- Set exactly ONE to in_progress when you start it
- Set to completed only AFTER verifying the work is done
- Update in real time, never batch
- One in_progress at a time

## Output rules
- Output ONLY JSON for tool calls, ONLY plain text when done
- Use absolute file paths
- After each [Tool result], decide next action
"""

FEW_SHOT = [
    {"role": "user",
     "content": "JSON ONLY: show current date"},
    {"role": "assistant",
     "content": '{"tool":"run_command","command":"date"}'},
    {"role": "user",
     "content": "[Tool result]\nFri Jun  5 2026\n\nJSON ONLY: next tool or DONE: summary."},
    {"role": "assistant",
     "content": "Date: Fri Jun 5 2026"},

    {"role": "user",
     "content": "JSON ONLY: create /tmp/hi.py with print hi, then run it"},
    {"role": "assistant",
     "content": '{"name":"todowrite","arguments":{"todos":[{"content":"Create /tmp/hi.py","status":"in_progress","priority":"high"},{"content":"Run /tmp/hi.py","status":"pending","priority":"high"}]}}'},
    {"role": "user",
     "content": "[Tool result]\n[Todo updated]\n\nJSON ONLY: next tool or DONE: summary."},
    {"role": "assistant",
     "content": '{"name":"write_file","arguments":{"path":"/tmp/hi.py","content":"print(\'hi\')"}}'},
    {"role": "user",
     "content": "[Tool result]\n[Wrote 10 chars]\n\nJSON ONLY: next tool or DONE: summary."},
    {"role": "assistant",
     "content": '{"name":"todowrite","arguments":{"todos":[{"content":"Create /tmp/hi.py","status":"completed","priority":"high"},{"content":"Run /tmp/hi.py","status":"in_progress","priority":"high"}]}}'},
    {"role": "user",
     "content": "[Tool result]\n[Todo updated]\n\nJSON ONLY: next tool or DONE: summary."},
    {"role": "assistant",
     "content": '{"tool":"run_command","command":"python3 /tmp/hi.py"}'},
    {"role": "user",
     "content": "[Tool result]\nhi\n\nJSON ONLY: next tool or DONE: summary."},
    {"role": "assistant",
     "content": '{"name":"todowrite","arguments":{"todos":[{"content":"Create /tmp/hi.py","status":"completed","priority":"high"},{"content":"Run /tmp/hi.py","status":"completed","priority":"high"}]}}'},
    {"role": "user",
     "content": "[Tool result]\n[Todo updated]\n\nJSON ONLY: next tool or DONE: summary."},
    {"role": "assistant",
     "content": "Done: created /tmp/hi.py and ran it — output: hi"},
]

TOOL_ALIASES = {
    "execute_command":"exec","run_command":"exec","bash":"exec","shell":"exec",
    "execute":"exec","run":"exec","terminal":"exec","cmd":"exec","command":"exec",
    "file_read":"read_file","open_file":"read_file","cat":"read_file",
    "file_write":"write_file","create_file":"write_file","write":"write_file",
    "file_edit":"edit_file","modify_file":"edit_file","patch":"edit_file",
    "todo_write":"todowrite","todo_update":"todowrite","update_todos":"todowrite",
    "todo_add":"todowrite","todo":"todowrite","todos":"todowrite",
    "todo_list":"todowrite",
}


class Agent:
    def __init__(self, client: DeepSeekClient, model: str = "deepseek-v3", max_rounds: int = 40):
        self.client     = client
        self.model      = model
        self.max_rounds = max_rounds
        self.messages: list[dict] = []
        self.tools_used: list[str] = []
        self.todos: list[dict] = []

    # ── Shell ──────────────────────────────────────────────────────────────────
    def _exec(self, command: str) -> str:
        try:
            r = subprocess.run(command, shell=True, capture_output=True,
                               text=True, timeout=120, cwd=os.getcwd())
            out = (r.stdout + r.stderr).strip()
            return out[:8000] if out else f"[Exit code: {r.returncode}]"
        except subprocess.TimeoutExpired:
            return "[Timeout: > 120s]"
        except Exception as e:
            return f"[Exec error: {e}]"

    # ── Files ──────────────────────────────────────────────────────────────────
    def _write_file(self, path: str, content: str) -> str:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"[Wrote {len(content)} chars to {path}]"
        except Exception as e:
            return f"[Write error: {e}]"

    def _read_file(self, path: str) -> str:
        try:
            return Path(path).read_text()[:8000]
        except Exception as e:
            return f"[Read error: {e}]"

    def _edit_file(self, path: str, old: str, new: str) -> str:
        try:
            p = Path(path)
            text = p.read_text()
            if old not in text:
                return f"[Edit error: pattern not found in {path}]"
            p.write_text(text.replace(old, new, 1))
            return f"[Edited {path}]"
        except Exception as e:
            return f"[Edit error: {e}]"

    # ── Todo (mirrors opencode Todo.Info[]) ────────────────────────────────────
    def _todowrite(self, todos: list) -> str:
        normalised = []
        for t in todos:
            if isinstance(t, str):
                normalised.append({"content": t, "status": "pending", "priority": "medium"})
            elif isinstance(t, dict):
                normalised.append({
                    "content":  str(t.get("content", t.get("item", t.get("task", "")))),
                    "status":   str(t.get("status", "pending")),
                    "priority": str(t.get("priority", "medium")),
                })
        self.todos = normalised
        pending = sum(1 for t in self.todos if t["status"] not in ("completed", "cancelled"))
        return f"[Todo list updated — {len(self.todos)} items, {pending} pending]"

    def _todo_display(self) -> str:
        if not self.todos:
            return "[No todos]"
        icons = {"pending": "○", "in_progress": "▶", "completed": "✓", "cancelled": "✗"}
        pri_tag = {"high": "[H]", "medium": "[M]", "low": "[L]"}
        lines = []
        for t in self.todos:
            icon = icons.get(t["status"], "?")
            pri  = pri_tag.get(t.get("priority", "medium"), "")
            lines.append(f"  {icon} {pri} {t['content']}")
        done = sum(1 for t in self.todos if t["status"] == "completed")
        lines.append(f"\n  {done}/{len(self.todos)} completed")
        return "\n".join(lines)

    # ── Parse tool call ────────────────────────────────────────────────────────
    def _parse_tool_call(self, response: str) -> dict | None:
        text = re.sub(r"```(?:json)?\s*", "", response)
        text = re.sub(r"```", "", text).strip()

        def _alias(n: str) -> str:
            return TOOL_ALIASES.get(n, n)

        def _normalise(d) -> dict | None:
            if not isinstance(d, dict):
                return None
            # Canonical {name, arguments}
            if "name" in d and "arguments" in d:
                d["name"] = _alias(d["name"]); return d
            # {tool_calls: [{name, arguments}]}
            if "tool_calls" in d:
                calls = d["tool_calls"]
                if isinstance(calls, list) and calls:
                    tc = calls[0]
                    return {"name": _alias(tc.get("name", "")),
                            "arguments": tc.get("arguments", tc.get("parameters", {}))}
            # {function, parameters}
            if "function" in d:
                return {"name": _alias(d["function"]),
                        "arguments": d.get("parameters", d.get("arguments", {}))}
            # {name, *}
            if "name" in d:
                return {"name": _alias(d["name"]),
                        "arguments": d.get("arguments", d.get("parameters", d.get("args", {})))}
            # {tool, command/path/...}  — model-native variant
            if "tool" in d:
                raw  = d["tool"]
                name = _alias(raw)
                rest = {k: v for k, v in d.items() if k != "tool"}
                if name == "exec":
                    cmd = rest.get("command", rest.get("cmd",
                          " ".join(str(v) for v in rest.values())))
                    return {"name": "exec", "arguments": {"command": cmd}}
                if name == "write_file":
                    return {"name": "write_file",
                            "arguments": {"path":    rest.get("path", rest.get("filepath", "")),
                                          "content": rest.get("content", "")}}
                if name == "read_file":
                    return {"name": "read_file",
                            "arguments": {"path": rest.get("path", rest.get("filepath", ""))}}
                # Anything else: exec from tool name + args
                return {"name": "exec",
                        "arguments": {"command": raw + " " + " ".join(str(v) for v in rest.values())}}
            return None

        def _fix(tool: dict) -> dict:
            name = tool["name"]
            args = tool.get("arguments", {})
            if name == "exec":
                if isinstance(args, str):
                    tool["arguments"] = {"command": args}
                elif isinstance(args, dict):
                    for alias in ("cmd", "shell_command", "shell", "bash", "script", "command_string"):
                        if alias in args and "command" not in args:
                            args["command"] = args.pop(alias)
            if name in ("write_file", "create_file"):
                tool["name"] = "write_file"
                if isinstance(args, dict) and "filepath" in args and "path" not in args:
                    args["path"] = args.pop("filepath")
            if name in ("read_file", "open_file"):
                tool["name"] = "read_file"
                if isinstance(args, dict) and "filepath" in args and "path" not in args:
                    args["path"] = args.pop("filepath")
            if name == "todowrite":
                raw = args.get("todos", []) if isinstance(args, dict) else args if isinstance(args, list) else []
                normed = []
                for t in raw:
                    if isinstance(t, str):
                        normed.append({"content": t, "status": "pending", "priority": "medium"})
                    elif isinstance(t, dict):
                        normed.append({
                            "content":  t.get("content", t.get("item", t.get("task", ""))),
                            "status":   t.get("status", "pending" if not t.get("done") else "completed"),
                            "priority": t.get("priority", "medium"),
                        })
                if isinstance(args, dict):
                    tool["arguments"]["todos"] = normed
                else:
                    tool["arguments"] = {"todos": normed}
            return tool

        # Try full JSON
        try:
            r = _normalise(json.loads(text))
            if r: return _fix(r)
        except Exception:
            pass

        # Balanced braces
        depth = 0; start = None
        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0: start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        r = _normalise(json.loads(text[start:i + 1]))
                        if r: return _fix(r)
                    except Exception:
                        pass
                    start = None

        # Line by line
        for line in text.split("\n"):
            line = line.strip()
            if any(k in line for k in ('"name"', '"tool"', '"function"')):
                try:
                    r = _normalise(json.loads(line))
                    if r: return _fix(r)
                except Exception:
                    pass
        return None

    # ── Execute tool ───────────────────────────────────────────────────────────
    def _execute_tool(self, tool: dict) -> str:
        name = tool["name"]
        args = tool.get("arguments", {})
        self.tools_used.append(name)
        if name == "exec":       return self._exec(args.get("command", "echo no_cmd"))
        if name == "read_file":  return self._read_file(args.get("path", ""))
        if name == "write_file": return self._write_file(args.get("path", ""), args.get("content", ""))
        if name == "edit_file":  return self._edit_file(args.get("path", ""), args.get("old", ""), args.get("new", ""))
        if name == "todowrite":  return self._todowrite(args.get("todos", []))
        return f"[Unknown tool: {name}]"

    # ── Main agent loop ────────────────────────────────────────────────────────
    def run(self, user_input: str, callback=None) -> str:
        """
        Agentic loop — mirrors opencode session loop:
          build context → call LLM → tool call? → execute → append → loop
                                   → plain text? → done
        The model autonomously decides when to use todowrite.
        """
        self.tools_used = []
        self.messages.append({"role": "user", "content": f"JSON ONLY: {user_input}"})

        max_retries  = 3
        retries      = 0
        final_output = ""

        for round_num in range(1, self.max_rounds + 1):
            if callback:
                callback("thinking", f"Round {round_num}/{self.max_rounds}")

            full_messages = (
                [{"role": "system", "content": SYSTEM_PROMPT}]
                + FEW_SHOT
                + self.messages
            )

            try:
                response = self.client.send_message(full_messages, self.model)
            except Exception as e:
                err = f"[API error: {e}]"
                self.messages.append({"role": "assistant", "content": err})
                return err

            response = response.strip()

            if not response:
                retries += 1
                if callback:
                    callback("thinking", f"Empty response (retry {retries}/{max_retries})")
                if retries >= max_retries:
                    break
                self.messages.append({"role": "assistant", "content": ""})
                self.messages.append({
                    "role": "user",
                    "content": "JSON ONLY: continue — next tool call, or DONE: plain text summary."
                })
                continue

            retries = 0
            tool_call = self._parse_tool_call(response)

            if tool_call:
                if callback:
                    callback("exec", json.dumps(tool_call, ensure_ascii=False))

                output = self._execute_tool(tool_call)
                final_output = output

                if tool_call["name"] == "todowrite":
                    if callback:
                        callback("todo_update", self._todo_display())
                else:
                    if callback:
                        callback("output", output)

                self.messages.append({"role": "assistant", "content": response})
                self.messages.append({
                    "role": "user",
                    "content": (
                        f"[Tool result]\n{output}\n\n"
                        "JSON ONLY: next tool call, or DONE: plain text summary if finished."
                    )
                })

            else:
                # Plain text → done
                self.messages.append({"role": "assistant", "content": response})
                final_output = response

                if self.todos and callback:
                    callback("todo_summary", self._todo_display())
                if callback:
                    callback("done", response)
                return final_output

            time.sleep(1.5)

        if self.todos and callback:
            callback("todo_summary", self._todo_display())
        if callback:
            callback("done", final_output)
        return final_output

    def clear(self):
        self.messages   = []
        self.tools_used = []
        self.todos      = []
