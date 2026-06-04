#!/usr/bin/env python3
"""Autonomous agent — Plan-then-Execute with Todo List for reliable long tasks."""
import json, re, subprocess, os
from pathlib import Path
from .client import DeepSeekClient

# ─── Prompts ──────────────────────────────────────────────────────────────────

PLANNER_PROMPT = """You are a task planner API. Given a task, output ONLY a JSON array of concrete steps.
Rules:
- Output ONLY a JSON array of strings, nothing else
- Maximum 8 steps, each step is one concrete action
- Steps must be clear and actionable
- No markdown, no explanation

Example:
Input: "create a python script and run it"
Output: ["Create /tmp/script.py with print('hello')", "Run the script with python3", "Show the output"]"""

EXECUTOR_PROMPT = """You are a JSON API for a terminal agent. Rules:
- Input: one specific step to execute
- Output: ONLY a valid JSON tool call, nothing else

TOOLS:
{"name":"exec","arguments":{"command":"SHELL_COMMAND"}}
{"name":"read_file","arguments":{"path":"FILE_PATH"}}
{"name":"write_file","arguments":{"path":"FILE_PATH","content":"CONTENT"}}
{"name":"edit_file","arguments":{"path":"FILE_PATH","old":"OLD_TEXT","new":"NEW_TEXT"}}

Output ONLY JSON. No text. No markdown."""

EXECUTOR_FEW_SHOT = [
    {"role": "user", "content": "Execute: list files in /tmp (respond ONLY with JSON)"},
    {"role": "assistant", "content": '{"name":"exec","arguments":{"command":"ls -la /tmp"}}'},
    {"role": "user", "content": "Execute: create file /tmp/hello.txt with content: hello world (respond ONLY with JSON)"},
    {"role": "assistant", "content": '{"name":"write_file","arguments":{"path":"/tmp/hello.txt","content":"hello world"}}'},
    {"role": "user", "content": "Execute: show current user and hostname (respond ONLY with JSON)"},
    {"role": "assistant", "content": '{"name":"exec","arguments":{"command":"whoami && hostname"}}'},
    {"role": "user", "content": "Execute: check if nginx is running (respond ONLY with JSON)"},
    {"role": "assistant", "content": '{"name":"exec","arguments":{"command":"systemctl status nginx 2>/dev/null || service nginx status 2>/dev/null || echo not running"}}'},
    {"role": "user", "content": "Execute: read the file /etc/os-release (respond ONLY with JSON)"},
    {"role": "assistant", "content": '{"name":"read_file","arguments":{"path":"/etc/os-release"}}'},
]


class Agent:
    def __init__(self, client, model="deepseek-v3", max_rounds=40):
        self.client     = client
        self.model      = model
        self.max_rounds = max_rounds
        self.messages   = []        # kept for non-plan mode
        self.tools_used = []
        self.todos      = []        # [{item: str, done: bool, output: str}]

    # ── Shell ──────────────────────────────────────────────────────────────
    def exec_command(self, command):
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=120, cwd=os.getcwd()
            )
            out = (result.stdout + result.stderr).strip()
            return out[:8000] if out else f"[Exit code: {result.returncode}]"
        except subprocess.TimeoutExpired:
            return "[Timeout: >120s]"
        except Exception as e:
            return f"[Error: {e}]"

    # ── File ops ───────────────────────────────────────────────────────────
    def write_file(self, path, content):
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"[Written {len(content)} chars to {path}]"
        except Exception as e:
            return f"[Error writing: {e}]"

    def read_file(self, path):
        try:
            return Path(path).read_text()[:8000]
        except Exception as e:
            return f"[Error reading: {e}]"

    def edit_file(self, path, old, new):
        try:
            p = Path(path)
            text = p.read_text()
            if old not in text:
                return "[Pattern not found]"
            p.write_text(text.replace(old, new, 1))
            return f"[Edited {path}]"
        except Exception as e:
            return f"[Error editing: {e}]"

    # ── Todo ops ───────────────────────────────────────────────────────────
    def todo_add(self, item):
        idx = len(self.todos)
        self.todos.append({"item": item, "done": False, "output": ""})
        return f"[TODO #{idx} added: {item}]"

    def todo_done(self, index, output=""):
        if index < 0 or index >= len(self.todos):
            return f"[TODO error: index {index} out of range]"
        self.todos[index]["done"]   = True
        self.todos[index]["output"] = output
        pending = sum(1 for t in self.todos if not t["done"])
        return f"[TODO #{index} ✓ — {pending} remaining]"

    def todo_list(self):
        if not self.todos:
            return "[No todos]"
        lines = []
        for i, t in enumerate(self.todos):
            mark = "✓" if t["done"] else "○"
            lines.append(f"  {mark} [{i}] {t['item']}")
        done = sum(1 for t in self.todos if t["done"])
        lines.append(f"\n  {done}/{len(self.todos)} done")
        return "\n".join(lines)

    # ── Parse tool call ────────────────────────────────────────────────────
    def parse_tool_call(self, response):
        response = re.sub(r'```(?:json)?\s*', '', response)
        response = re.sub(r'```', '', response).strip()

        def _map(name):
            m = {
                "execute_command": "exec", "run_command": "exec",
                "shell": "exec", "bash": "exec", "execute": "exec",
                "file_read": "read_file", "open_file": "read_file",
                "file_write": "write_file", "create_file": "write_file",
                "file_edit": "edit_file", "modify_file": "edit_file",
            }
            return m.get(name, name)

        def normalize(d):
            if not isinstance(d, dict): return None
            if "name" in d and "arguments" in d:
                d["name"] = _map(d["name"]); return d
            if "tool_calls" in d:
                calls = d["tool_calls"]
                if isinstance(calls, list) and calls:
                    tc = calls[0]
                    return {"name": _map(tc.get("name","")),
                            "arguments": tc.get("arguments", tc.get("parameters", {}))}
            if "function" in d:
                return {"name": _map(d["function"]),
                        "arguments": d.get("parameters", d.get("arguments", {}))}
            if "name" in d:
                return {"name": _map(d["name"]),
                        "arguments": d.get("parameters", d.get("args", {}))}
            return None

        def fix(tool):
            name = tool["name"]; args = tool["arguments"]
            if name == "exec":
                if isinstance(args, str): tool["arguments"] = {"command": args}
                elif isinstance(args, dict):
                    for k in ["cmd","shell_command","shell","bash","script"]:
                        if k in args and "command" not in args:
                            args["command"] = args.pop(k)
            return tool

        # Try full JSON
        try:
            r = normalize(json.loads(response))
            if r: return fix(r)
        except: pass

        # Balanced braces
        depth = start = None
        depth = 0
        for i, ch in enumerate(response):
            if ch=="{":
                if depth==0: start=i
                depth+=1
            elif ch=="}":
                depth-=1
                if depth==0 and start is not None:
                    try:
                        r = normalize(json.loads(response[start:i+1]))
                        if r: return fix(r)
                    except: pass
                    start=None

        # Line by line
        for line in response.split("\n"):
            line = line.strip()
            if '"name"' in line:
                try:
                    r = normalize(json.loads(line))
                    if r: return fix(r)
                except: pass
        return None

    def execute_tool(self, tool):
        name = tool["name"]
        args = tool.get("arguments", {})
        self.tools_used.append(name)
        if   name == "exec":       return self.exec_command(args.get("command","echo no_cmd"))
        elif name == "read_file":  return self.read_file(args.get("path",""))
        elif name == "write_file": return self.write_file(args.get("path",""), args.get("content",""))
        elif name == "edit_file":  return self.edit_file(args.get("path",""), args.get("old",""), args.get("new",""))
        return f"[Unknown tool: {name}]"

    # ── Planning phase ─────────────────────────────────────────────────────
    def plan(self, task: str, callback=None) -> list[str]:
        """Ask the model to break task into steps. Returns list of step strings."""
        if callback: callback("planning", "Analyzing task and creating plan...")
        messages = [
            {"role": "system", "content": PLANNER_PROMPT},
            {"role": "user", "content": f"Task: {task}\n\nOutput ONLY a JSON array of steps."},
        ]
        try:
            resp = self.client.send_message(messages, self.model)
        except Exception as e:
            if callback: callback("planning", f"Plan failed: {e}, running as single task")
            return [task]

        resp = resp.strip()
        resp = re.sub(r'```(?:json)?\s*', '', resp)
        resp = re.sub(r'```', '', resp).strip()

        # Extract JSON array
        start = resp.find("[")
        end   = resp.rfind("]") + 1
        if start != -1 and end > start:
            try:
                steps = json.loads(resp[start:end])
                if isinstance(steps, list) and steps:
                    # Normalize: handle both ["step"] and [{"step":"..."}] formats
                    normalized = []
                    for s in steps:
                        if isinstance(s, str):
                            normalized.append(s)
                        elif isinstance(s, dict):
                            # Try common keys
                            for key in ["step", "description", "action", "task", "item", "name"]:
                                if key in s:
                                    normalized.append(str(s[key]))
                                    break
                            else:
                                # Join all values
                                normalized.append(": ".join(str(v) for v in s.values() if v))
                    if normalized:
                        if callback: callback("planning", f"Plan: {len(normalized)} steps")
                        return normalized
            except: pass

        if callback: callback("planning", "No plan found, running as single task")
        return [task]

    # ── Execute one step ───────────────────────────────────────────────────
    def execute_step(self, step: str, context: str = "", callback=None) -> str:
        """Execute a single step with up to 5 retries."""
        ctx_note = f"\n\nContext from previous steps:\n{context[-1000:]}" if context else ""
        user_msg = (
            f"Execute this specific step: {step}{ctx_note}\n\n"
            "(respond ONLY with JSON tool call, no text)"
        )
        messages = [{"role": "system", "content": EXECUTOR_PROMPT}] + EXECUTOR_FEW_SHOT
        messages.append({"role": "user", "content": user_msg})

        last_output = ""
        for attempt in range(5):
            try:
                resp = self.client.send_message(messages, self.model)
            except Exception as e:
                return f"[API error: {e}]"

            resp      = resp.strip()
            tool_call = self.parse_tool_call(resp)

            if tool_call:
                if callback:
                    callback("exec", json.dumps(tool_call, ensure_ascii=False))
                output      = self.execute_tool(tool_call)
                last_output = output
                if callback:
                    callback("output", output)
                return output
            else:
                if callback:
                    callback("thinking", f"No tool call for step (attempt {attempt+1}/5)")
                messages.append({"role": "assistant", "content": resp})
                messages.append({"role": "user",
                                 "content": 'Output ONLY JSON. Example: {"name":"exec","arguments":{"command":"ls"}}'})

        return last_output or "[Step failed: no tool call generated]"

    # ── Main run (plan + execute) ───────────────────────────────────────────
    def run(self, user_input: str, callback=None) -> str:
        self.todos = []

        # Decide if task is simple (1 action) or complex (multi-step)
        simple_keywords = ["whoami","hostname","ls","pwd","ps","df","uname","echo","cat ","id "]
        is_simple = len(user_input.split()) < 6 or any(k in user_input.lower() for k in simple_keywords)

        if is_simple:
            # Run directly without planning
            steps = [user_input]
        else:
            # Plan first
            import time; time.sleep(2)  # rate limit buffer
            steps = self.plan(user_input, callback)
            time.sleep(2)

        # Add all steps as todos
        for step in steps:
            self.todo_add(step)
        if callback and self.todos:
            callback("todo_list", self.todo_list())

        # Execute each step
        context_log = ""
        final_output = ""

        for idx, todo in enumerate(self.todos):
            step = todo["item"]
            if callback:
                callback("step_start", f"[{idx+1}/{len(self.todos)}] {step}")

            output = self.execute_step(step, context=context_log, callback=callback)

            # Mark done
            self.todo_done(idx, output)
            final_output = output
            context_log += f"\nStep {idx+1} ({step}):\n{output[:500]}\n"

            if callback:
                callback("step_done", f"[{idx+1}/{len(self.todos)}] done")

            # Delay between steps to avoid rate limiting
            if idx < len(self.todos) - 1:
                import time; time.sleep(3)

        if callback:
            callback("todo_summary", self.todo_list())
            callback("done", final_output if final_output != "TASK_DONE" else "✅ All steps completed!")

        return final_output

    def clear(self):
        self.messages   = []
        self.tools_used = []
        self.todos      = []
