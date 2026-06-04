#!/usr/bin/env python3
"""
DeepSeek Agent — opencode-style agent loop.

Strategy (adapted for chat.deepseek.com free API):
  - deepseek-coder generates a bash script / plan from the user request
  - We parse the script into ordered steps (todo list)
  - Execute each step, feed result back to model for next decision
  - For simple tasks (1-2 steps): skip todo, run directly
  - For complex tasks (3+ steps): create todo list, mark in_progress/completed per step

This mirrors opencode's architecture:
  - todowrite rules: use when task has 3+ distinct steps
  - Single in_progress at a time
  - Mark completed only after verifying the output
  - Model decides what to do next after each result
"""

import json, re, subprocess, os, time
from pathlib import Path
from .client import DeepSeekClient

# ─── System prompts ────────────────────────────────────────────────────────────

# Phase 1: Planner — generates a bash script from the task
PLANNER_PROMPT = """You are a bash automation expert. Given a task, output ONLY a pure bash script.
Rules:
- Output ONLY bash commands, nothing else
- No markdown fences, no explanation
- Use printf or heredoc for multi-line file content
- All paths must be absolute
- One logical action per line
- Comments allowed (# ...)"""

# Phase 2: Executor — decides what to do after seeing a step result
EXECUTOR_PROMPT = """You are a terminal agent observer. Given a completed step and its output, decide what to do.
If the output looks correct and there are more steps: respond with CONTINUE
If something failed and needs fixing: respond with a bash command to fix it (one line only)
If all work is done: respond with DONE: <brief summary>
Output ONLY one of: CONTINUE / a bash command / DONE: summary"""

# ─── Aliases ──────────────────────────────────────────────────────────────────
TOOL_ALIASES = {
    "run_command":"exec","execute_command":"exec","bash":"exec","shell":"exec",
    "execute":"exec","run":"exec","cmd":"exec","command":"exec",
    "file_write":"write_file","create_file":"write_file",
    "file_read":"read_file","open_file":"read_file",
    "todo_write":"todowrite","todo_update":"todowrite","update_todos":"todowrite",
}


class Agent:
    def __init__(self, client: DeepSeekClient, model: str = "deepseek-coder", max_rounds: int = 40):
        self.client     = client
        self.model      = model
        self.max_rounds = max_rounds
        self.messages: list[dict] = []   # persistent conversation history
        self.tools_used: list[str] = []
        self.todos: list[dict] = []      # [{content, status, priority}]

    # ── Shell ──────────────────────────────────────────────────────────────────
    def _exec(self, command: str) -> str:
        try:
            r = subprocess.run(command, shell=True, capture_output=True,
                               text=True, timeout=120, cwd=os.getcwd())
            out = (r.stdout + r.stderr).strip()
            return out[:6000] if out else f"[exit {r.returncode}]"
        except subprocess.TimeoutExpired:
            return "[Timeout >120s]"
        except Exception as e:
            return f"[Error: {e}]"

    # ── Files ──────────────────────────────────────────────────────────────────
    def _write_file(self, path: str, content: str) -> str:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"[Wrote {len(content)} chars → {path}]"
        except Exception as e:
            return f"[Write error: {e}]"

    def _read_file(self, path: str) -> str:
        try:
            return Path(path).read_text()[:6000]
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

    # ── Todo ───────────────────────────────────────────────────────────────────
    def _set_todos(self, items: list[str], priority: str = "medium"):
        """Initialize todo list from a list of strings."""
        self.todos = [
            {"content": item, "status": "pending", "priority": priority}
            for item in items
        ]

    def _mark_in_progress(self, idx: int):
        for i, t in enumerate(self.todos):
            if t["status"] == "in_progress":
                t["status"] = "pending"  # reset previous
        if idx < len(self.todos):
            self.todos[idx]["status"] = "in_progress"

    def _mark_done(self, idx: int):
        if idx < len(self.todos):
            self.todos[idx]["status"] = "completed"

    def _todo_display(self) -> str:
        if not self.todos:
            return "[No todos]"
        icons = {"pending": "○", "in_progress": "▶", "completed": "✓", "cancelled": "✗"}
        pri   = {"high": "[H]", "medium": "[M]", "low": "[L]"}
        lines = []
        for t in self.todos:
            lines.append(f"  {icons.get(t['status'],'?')} {pri.get(t.get('priority','medium'),'')} {t['content']}")
        done = sum(1 for t in self.todos if t["status"] == "completed")
        lines.append(f"\n  {done}/{len(self.todos)} completed")
        return "\n".join(lines)

    # ── Script parser ──────────────────────────────────────────────────────────
    def _parse_script(self, script: str) -> list[str]:
        """
        Extract ordered bash commands from a script string.
        Groups logical multi-line constructs (heredoc, if, for) together.
        Returns list of command strings.
        """
        # Remove markdown fences
        script = re.sub(r"```(?:bash|sh)?\n?", "", script)
        script = re.sub(r"```", "", script).strip()

        steps = []
        buffer = []
        heredoc_end = None

        for line in script.split("\n"):
            stripped = line.strip()

            # Inside heredoc
            if heredoc_end:
                buffer.append(line)
                if stripped == heredoc_end:
                    steps.append("\n".join(buffer))
                    buffer = []
                    heredoc_end = None
                continue

            # Empty or comment-only
            if not stripped or stripped.startswith("#"):
                if buffer:
                    buffer.append(line)
                continue

            # Detect heredoc start
            hd = re.search(r"<<\s*['\"]?(\w+)['\"]?", line)
            if hd:
                buffer.append(line)
                heredoc_end = hd.group(1)
                continue

            # Continuation
            if stripped.endswith("\\") or stripped.startswith("&&") or stripped.startswith("||") or stripped.startswith("|"):
                buffer.append(line)
                continue

            # Normal line
            if buffer:
                # Check if prev line ends with \ meaning continuation
                if buffer[-1].rstrip().endswith("\\"):
                    buffer.append(line)
                    continue
                else:
                    steps.append("\n".join(buffer))
                    buffer = []

            steps.append(line.strip())

        if buffer:
            steps.append("\n".join(buffer))

        # Filter out empty
        return [s for s in steps if s.strip() and not s.strip().startswith("#")]

    # ── LLM call ──────────────────────────────────────────────────────────────
    def _call_model(self, system: str, messages: list[dict]) -> str:
        full = [{"role": "system", "content": system}] + messages
        try:
            return self.client.send_message(full, self.model).strip()
        except Exception as e:
            return f"[API error: {e}]"

    # ── Parse inline tool call (fallback for simple single-tool responses) ─────
    def _parse_tool_call(self, response: str) -> dict | None:
        text = re.sub(r"```(?:json)?\s*", "", response)
        text = re.sub(r"```", "", text).strip()

        def _alias(n):
            return TOOL_ALIASES.get(n, n)

        def _normalise(d):
            if not isinstance(d, dict):
                return None
            if "name" in d and "arguments" in d:
                d["name"] = _alias(d["name"]); return d
            if "tool_calls" in d:
                calls = d["tool_calls"]
                if isinstance(calls, list) and calls:
                    tc = calls[0]
                    return {"name": _alias(tc.get("name","")),
                            "arguments": tc.get("arguments",tc.get("parameters",{}))}
            if "function" in d:
                return {"name": _alias(d["function"]),
                        "arguments": d.get("parameters",d.get("arguments",{}))}
            if "name" in d:
                return {"name": _alias(d["name"]),
                        "arguments": d.get("arguments",d.get("parameters",d.get("args",{})))}
            if "tool" in d:
                raw=d["tool"]; name=_alias(raw)
                rest={k:v for k,v in d.items() if k!="tool"}
                if name=="exec":
                    cmd=rest.get("command",rest.get("cmd"," ".join(str(v) for v in rest.values())))
                    return {"name":"exec","arguments":{"command":cmd}}
                if name=="write_file":
                    return {"name":"write_file","arguments":{"path":rest.get("path",rest.get("filepath","")),"content":rest.get("content","")}}
                if name=="read_file":
                    return {"name":"read_file","arguments":{"path":rest.get("path",rest.get("filepath",""))}}
                return {"name":"exec","arguments":{"command":raw+" "+" ".join(str(v) for v in rest.values())}}
            return None

        try:
            r=_normalise(json.loads(text))
            if r: return r
        except: pass

        depth=0; start=None
        for i,ch in enumerate(text):
            if ch=="{":
                if depth==0: start=i
                depth+=1
            elif ch=="}":
                depth-=1
                if depth==0 and start is not None:
                    try:
                        r=_normalise(json.loads(text[start:i+1]))
                        if r: return r
                    except: pass
                    start=None
        return None

    # ── Execute parsed tool ────────────────────────────────────────────────────
    def _execute_tool(self, tool: dict) -> str:
        name=tool["name"]; args=tool.get("arguments",{})
        self.tools_used.append(name)
        if name=="exec":       return self._exec(args.get("command","echo no_cmd"))
        if name=="read_file":  return self._read_file(args.get("path",""))
        if name=="write_file": return self._write_file(args.get("path",""),args.get("content",""))
        if name=="edit_file":  return self._edit_file(args.get("path",""),args.get("old",""),args.get("new",""))
        return f"[Unknown tool: {name}]"

    # ── Main agent loop ────────────────────────────────────────────────────────
    def run(self, user_input: str, callback=None) -> str:
        """
        opencode-style agent loop:

        1. Ask model to generate a bash script / plan (PLANNER)
        2. Parse script into steps
        3. If 1-2 steps: run directly (no todo)
           If 3+ steps: create todo list (mirrors opencode todowrite rules)
        4. For each step:
           - Mark in_progress
           - Execute
           - Feed result to EXECUTOR model
           - EXECUTOR says CONTINUE / fix command / DONE
        5. Mark completed, move to next
        """
        self.tools_used = []

        # Save to conversation history
        self.messages.append({"role": "user", "content": user_input})

        if callback:
            callback("thinking", "Planning task...")

        # ── Phase 1: Generate plan ─────────────────────────────────────────────
        plan_resp = self._call_model(PLANNER_PROMPT, [{"role":"user","content":f"Task: {user_input}"}])

        # Check if it's a direct tool call (simple case)
        tool_call = self._parse_tool_call(plan_resp)
        if tool_call:
            if callback:
                callback("exec", json.dumps(tool_call, ensure_ascii=False))
            output = self._execute_tool(tool_call)
            if callback:
                callback("output", output)
            self.messages.append({"role":"assistant","content":output})
            if callback:
                callback("done", output)
            return output

        # Parse into steps
        steps = self._parse_script(plan_resp)

        if not steps:
            # Model returned plain text — conversational response
            self.messages.append({"role":"assistant","content":plan_resp})
            if callback:
                callback("done", plan_resp)
            return plan_resp

        # ── Phase 2: Create todo if 3+ steps (opencode rule) ──────────────────
        use_todo = len(steps) >= 3

        if use_todo:
            self._set_todos(steps, priority="high")
            if callback:
                callback("todo_update", self._todo_display())

        # ── Phase 3: Execute each step ─────────────────────────────────────────
        exec_history = []
        final_output = ""

        for idx, step in enumerate(steps):
            if idx >= self.max_rounds:
                break

            # Mark in_progress
            if use_todo:
                self._mark_in_progress(idx)
                if callback:
                    callback("todo_update", self._todo_display())

            # Show step
            if callback:
                callback("exec", json.dumps({"name":"exec","arguments":{"command":step}},ensure_ascii=False))

            output = self._exec(step)
            final_output = output
            self.tools_used.append("exec")

            if callback:
                callback("output", output)

            exec_history.append({"role":"user","content":f"Step: {step}"})
            exec_history.append({"role":"user","content":f"Output: {output}"})

            # Mark done
            if use_todo:
                self._mark_done(idx)
                if callback:
                    callback("todo_update", self._todo_display())

            time.sleep(1.2)

            # ── Ask executor if we should continue or fix ──────────────────────
            remaining = steps[idx+1:]
            if not remaining:
                break

            exec_ctx = (
                f"Completed step {idx+1}/{len(steps)}: {step}\n"
                f"Output: {output[:500]}\n"
                f"Remaining steps: {remaining[:3]}"
            )
            executor_resp = self._call_model(EXECUTOR_PROMPT,
                                             exec_history + [{"role":"user","content":exec_ctx}])

            if executor_resp.upper().startswith("DONE"):
                summary = executor_resp[4:].lstrip(":").strip()
                final_output = summary or output
                break

            if executor_resp.upper() == "CONTINUE":
                continue

            # Model returned a fix command
            if callback:
                callback("exec", json.dumps({"name":"exec","arguments":{"command":executor_resp}},ensure_ascii=False))
            fix_out = self._exec(executor_resp)
            if callback:
                callback("output", fix_out)
            exec_history.append({"role":"user","content":f"Fix: {executor_resp}\nOutput: {fix_out}"})
            final_output = fix_out

        # ── Final summary ──────────────────────────────────────────────────────
        if use_todo:
            # Mark any remaining as done if we exited early
            for t in self.todos:
                if t["status"] == "in_progress":
                    t["status"] = "completed"
            if callback:
                callback("todo_summary", self._todo_display())

        # Ask model for a clean summary
        if callback:
            callback("thinking", "Generating summary...")

        summary_msgs = (
            [{"role":"user","content":user_input}]
            + exec_history[-6:]
            + [{"role":"user","content":"Summarize what was done in 1-2 sentences."}]
        )
        summary = self._call_model(
            "You are a concise technical assistant. Summarize what the agent did.",
            summary_msgs
        )
        self.messages.append({"role":"assistant","content":summary})

        if callback:
            callback("done", summary)

        return summary

    def clear(self):
        self.messages   = []
        self.tools_used = []
        self.todos      = []
