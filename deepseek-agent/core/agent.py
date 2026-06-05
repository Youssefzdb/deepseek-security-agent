#!/usr/bin/env python3
"""
DeepSeek Agent — opencode-style Plan-then-Execute loop.

Strategy for chat.deepseek.com free API:
  1. PLANNER: ask deepseek-coder to generate ONLY bash commands (numbered list)
  2. Parse numbered list → steps (strict filter: must start with shell token)
  3. If 3+ steps → todowrite; else run directly
  4. Execute each step; after each ask EXECUTOR: CONTINUE / DONE / fix_cmd
"""

import json, re, subprocess, os, time
from pathlib import Path
from .client import DeepSeekClient

# ─── Prompts ──────────────────────────────────────────────────────────────────

PLANNER_PROMPT = """You are a Linux bash command generator. Given a task, output ONLY a numbered list of Linux bash commands.
Rules:
- ONLY output the numbered list — no explanation, no prose, no markdown, no comments
- ONE command per line — do NOT chain with && or ; or |
- Format: 1. <bash_command>
- Linux/bash ONLY — no Windows or PowerShell commands
- Use absolute paths
- mkdir before creating files
- To write a file: cat > /abs/path << 'HEREDOC'
  content here
  HEREDOC
Example for "create /tmp/app/main.py with print(42), run it, list dir":
1. mkdir -p /tmp/app
2. cat > /tmp/app/main.py << 'HEREDOC'
print(42)
HEREDOC
3. python3 /tmp/app/main.py
4. ls /tmp/app"""

EXECUTOR_PROMPT = """\
You are checking if a bash step succeeded and deciding what to do next.
Rules:
- If step succeeded and there are more steps: respond with exactly: CONTINUE
- If all work is done (no more steps): respond with exactly: DONE: <one line summary>
- If step failed and needs fixing: respond with exactly one bash command to fix it
- Output ONLY one of these three options. No explanation."""

SUMMARY_PROMPT = "You are a concise assistant. Given what was executed and the outputs, write a 1-2 sentence summary of what was accomplished."

# ─── Shell token regex — a line is a command if it starts with these ──────────
CMD_START = re.compile(
    r'^(?:sudo|cd|ls|echo|printf|cat|mkdir|rm|cp|mv|chmod|chown|curl|wget|'
    r'git|pip|pip3|python|python3|node|npm|npx|java|gcc|make|apt|apt-get|'
    r'yum|brew|systemctl|service|export|source|\.|bash|sh|env|which|find|'
    r'grep|sed|awk|sort|head|tail|wc|touch|stat|file|tar|zip|unzip|'
    r'ping|ssh|scp|rsync|docker|kubectl|terraform|ansible|'
    r'[/~$]|[a-zA-Z_][a-zA-Z0-9_-]*\s*[=>|&])'  # variable assign / redirect
)

TOOL_ALIASES = {
    "run_command":"exec","execute_command":"exec","bash":"exec","shell":"exec",
    "execute":"exec","run":"exec","cmd":"exec","command":"exec",
    "file_write":"write_file","create_file":"write_file",
    "file_read":"read_file","open_file":"read_file",
    "todo_write":"todowrite","todo_update":"todowrite",
}


class Agent:
    def __init__(self, client: DeepSeekClient, model: str = "deepseek-coder", max_rounds: int = 40):
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
            return out[:6000] if out else f"[exit {r.returncode}]"
        except subprocess.TimeoutExpired:
            return "[Timeout >120s]"
        except Exception as e:
            return f"[Error: {e}]"

    # ── Files ──────────────────────────────────────────────────────────────────
    def _write_file(self, path: str, content: str) -> str:
        try:
            p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"[Wrote {len(content)} chars → {path}]"
        except Exception as e:
            return f"[Write error: {e}]"

    def _read_file(self, path: str) -> str:
        try: return Path(path).read_text()[:6000]
        except Exception as e: return f"[Read error: {e}]"

    def _edit_file(self, path: str, old: str, new: str) -> str:
        try:
            p = Path(path); text = p.read_text()
            if old not in text: return f"[pattern not found in {path}]"
            p.write_text(text.replace(old, new, 1)); return f"[Edited {path}]"
        except Exception as e: return f"[Edit error: {e}]"

    # ── Todo ───────────────────────────────────────────────────────────────────
    def _set_todos(self, items: list[str]):
        self.todos = [{"content": s, "status": "pending", "priority": "high"} for s in items]

    def _mark_in_progress(self, idx: int):
        for t in self.todos:
            if t["status"] == "in_progress": t["status"] = "pending"
        if idx < len(self.todos): self.todos[idx]["status"] = "in_progress"

    def _mark_done(self, idx: int):
        if idx < len(self.todos): self.todos[idx]["status"] = "completed"

    def _todo_display(self) -> str:
        icons = {"pending":"○","in_progress":"▶","completed":"✓","cancelled":"✗"}
        lines = [f"  {icons.get(t['status'],'?')} {t['content']}" for t in self.todos]
        done  = sum(1 for t in self.todos if t["status"] == "completed")
        lines.append(f"\n  {done}/{len(self.todos)} completed")
        return "\n".join(lines)

    # ── Parse bash script / numbered list from planner ───────────────────────
    def _parse_steps(self, text: str) -> list[str]:
        """
        Extract executable steps from planner output.
        Handles:
        - Numbered lists: "1. command"
        - Plain bash scripts (with heredoc support)
        Groups heredoc blocks as single steps.
        """
        # Remove markdown fences
        text = re.sub(r"```(?:bash|sh)?\n?", "", text)
        text = re.sub(r"```", "", text).strip()

        steps      = []
        buf        = []
        heredoc_end = None

        lines = text.split("\n")
        for line in lines:
            raw      = line
            stripped = line.strip()

            # ── Inside heredoc ─────────────────────────────────────────────────
            if heredoc_end is not None:
                buf.append(raw)
                if stripped == heredoc_end:
                    steps.append("\n".join(buf))
                    buf = []
                    heredoc_end = None
                continue

            # ── Empty / comment ────────────────────────────────────────────────
            if not stripped or stripped.startswith("#"):
                continue

            # ── Extract command from numbered list ─────────────────────────────
            m = re.match(r"^\s*\d+[.)]\s+(.+)$", stripped)
            cmd = m.group(1).strip() if m else stripped

            # ── Detect heredoc start ───────────────────────────────────────────
            hd = re.search(r"<<\s*['\"](\w+)['\"]", cmd)
            if hd is None:
                hd = re.search(r"<<\s*(\w+)", cmd)
            if hd:
                heredoc_end = hd.group(1)
                buf = [cmd]
                continue

            # ── Must look like a shell command ─────────────────────────────────
            if CMD_START.match(cmd):
                steps.append(cmd)

        if buf:  # unterminated heredoc — add anyway
            steps.append("\n".join(buf))

        # Clean trailing && \ or ; continuations from each step
        cleaned = []
        for s in steps:
            # Remove trailing && \ or ; at end of command
            s = re.sub(r'\s*&&\s*\\?\s*$', '', s).strip()
            s = re.sub(r'\s*;\s*\\?\s*$',  '', s).strip()
            s = re.sub(r'\s*\\\s*$',         '', s).strip()
            if s:
                cleaned.append(s)
        steps = cleaned

        # Filter out Windows-only commands (echo %var%, @echo, etc.)
        steps = [s for s in steps if not re.match(r'^echo %|^@echo|^set |^REM |^rem ', s)]

        return steps

    # ── LLM call ──────────────────────────────────────────────────────────────
    def _call(self, system: str, messages: list[dict]) -> str:
        try:
            return self.client.send_message(
                [{"role":"system","content":system}] + messages, self.model
            ).strip()
        except Exception as e:
            return f"[API error: {e}]"

    # ── Parse JSON tool call (fallback for simple queries) ────────────────────
    def _parse_tool_call(self, response: str) -> dict | None:
        text = re.sub(r"```(?:json)?\s*", "", response)
        text = re.sub(r"```", "", text).strip()

        def alias(n): return TOOL_ALIASES.get(n, n)

        def norm(d):
            if not isinstance(d, dict): return None
            if "name" in d and "arguments" in d:
                d["name"] = alias(d["name"]); return d
            if "tool" in d:
                name = alias(d["tool"])
                rest = {k:v for k,v in d.items() if k!="tool"}
                if name == "exec":
                    cmd = rest.get("command", rest.get("cmd",""))
                    return {"name":"exec","arguments":{"command":cmd}}
                if name == "write_file":
                    return {"name":"write_file","arguments":{"path":rest.get("path",""),"content":rest.get("content","")}}
            return None

        try:
            r = norm(json.loads(text))
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
                        r=norm(json.loads(text[start:i+1]))
                        if r: return r
                    except: pass
                    start=None
        return None

    # ── Execute tool ───────────────────────────────────────────────────────────
    def _run_tool(self, tool: dict) -> str:
        name=tool["name"]; args=tool.get("arguments",{})
        self.tools_used.append(name)
        if name=="exec":       return self._exec(args.get("command",""))
        if name=="read_file":  return self._read_file(args.get("path",""))
        if name=="write_file": return self._write_file(args.get("path",""),args.get("content",""))
        if name=="edit_file":  return self._edit_file(args.get("path",""),args.get("old",""),args.get("new",""))
        return f"[Unknown tool: {name}]"

    # ── Main loop ──────────────────────────────────────────────────────────────
    def run(self, user_input: str, callback=None) -> str:
        self.tools_used = []
        self.messages.append({"role":"user","content":user_input})

        if callback: callback("thinking", "Planning...")

        # ── Phase 1: Plan ──────────────────────────────────────────────────────
        plan_raw = self._call(PLANNER_PROMPT, [{"role":"user","content":f"Task: {user_input}"}])
        steps    = self._parse_steps(plan_raw)

        # Fallback: maybe it's a JSON tool call
        if not steps:
            tc = self._parse_tool_call(plan_raw)
            if tc:
                if callback: callback("exec", json.dumps(tc, ensure_ascii=False))
                out = self._run_tool(tc)
                if callback: callback("output", out)
                self.messages.append({"role":"assistant","content":out})
                if callback: callback("done", out)
                return out
            # Conversational response
            self.messages.append({"role":"assistant","content":plan_raw})
            if callback: callback("done", plan_raw)
            return plan_raw

        if callback: callback("thinking", f"Got {len(steps)} step(s)")

        # ── Phase 2: Todo (opencode rule: 3+ steps) ────────────────────────────
        use_todo = len(steps) >= 3
        if use_todo:
            self._set_todos(steps)
            if callback: callback("todo_update", self._todo_display())

        # ── Phase 3: Execute ───────────────────────────────────────────────────
        exec_log   = []   # [{step, output}]
        final_out  = ""

        for idx, step in enumerate(steps[:self.max_rounds]):
            if use_todo:
                self._mark_in_progress(idx)
                if callback: callback("todo_update", self._todo_display())

            if callback:
                callback("exec", json.dumps({"name":"exec","arguments":{"command":step}}, ensure_ascii=False))

            output = self._exec(step)
            self.tools_used.append("exec")
            final_out = output

            if callback: callback("output", output)

            exec_log.append({"step": step, "output": output})

            if use_todo:
                self._mark_done(idx)
                if callback: callback("todo_update", self._todo_display())

            # Ask executor if more steps remain
            remaining = steps[idx+1:]
            if not remaining:
                break

            time.sleep(1.0)
            if callback: callback("thinking", f"Step {idx+1}/{len(steps)} done, checking...")

            ctx = (
                f"Step {idx+1}/{len(steps)}: {step}\n"
                f"Output: {output[:400]}\n"
                f"Next steps: {remaining[:2]}"
            )
            decision = self._call(EXECUTOR_PROMPT, [{"role":"user","content":ctx}])
            decision_clean = decision.strip()

            if decision_clean.upper().startswith("DONE"):
                final_out = decision_clean[4:].lstrip(":").strip() or output
                break
            elif decision_clean.upper() == "CONTINUE":
                time.sleep(1.0)
                continue
            else:
                # Fix command — must look like a bash command
                if CMD_START.match(decision_clean.split("\n")[0]):
                    fix_cmd = decision_clean.split("\n")[0]
                    if callback:
                        callback("exec", json.dumps({"name":"exec","arguments":{"command":fix_cmd}}, ensure_ascii=False))
                    fix_out = self._exec(fix_cmd)
                    if callback: callback("output", fix_out)
                    exec_log.append({"step": fix_cmd, "output": fix_out})
                    final_out = fix_out
                # else ignore bad response and continue
                time.sleep(1.0)

        # ── Phase 4: Summary ───────────────────────────────────────────────────
        if use_todo:
            for t in self.todos:
                if t["status"] == "in_progress": t["status"] = "completed"
            if callback: callback("todo_summary", self._todo_display())

        if callback: callback("thinking", "Summarizing...")

        log_str = "\n".join(f"$ {e['step']}\n→ {e['output'][:200]}" for e in exec_log[-5:])
        summary = self._call(
            SUMMARY_PROMPT,
            [{"role":"user","content":f"Task: {user_input}\n\nExecuted:\n{log_str}"}]
        )
        self.messages.append({"role":"assistant","content":summary})
        if callback: callback("done", summary)
        return summary

    def clear(self):
        self.messages=[]; self.tools_used=[]; self.todos=[]
