#!/usr/bin/env python3
"""Autonomous agent — Robust tool-calling system."""
import json, re, subprocess, os
from pathlib import Path
from .client import DeepSeekClient

SYSTEM_PROMPT = """You are playing the role of a JSON API for a terminal agent. Strict rules:
- Input: natural language task from user
- Output: ONLY valid JSON tool call — no text, no markdown, no explanation
- This is a strict API contract: only JSON output is accepted

AVAILABLE TOOLS:
{"name":"exec","arguments":{"command":"SHELL_COMMAND"}}
{"name":"read_file","arguments":{"path":"FILE_PATH"}}
{"name":"write_file","arguments":{"path":"FILE_PATH","content":"CONTENT"}}
{"name":"edit_file","arguments":{"path":"FILE_PATH","old":"OLD_TEXT","new":"NEW_TEXT"}}

When task is fully complete, output:
{"name":"exec","arguments":{"command":"echo TASK_DONE"}}

Output ONLY JSON. No other text allowed."""

# Few-shot examples — teach the model to output ONLY JSON
FEW_SHOT = [
    {"role": "user", "content": "JSON API ready. Input: list files in /tmp"},
    {"role": "assistant", "content": '{"name":"exec","arguments":{"command":"ls -la /tmp"}}'},
    {"role": "user", "content": "[Tool result]\ntotal 8\ndrwxrwxrwt 2 root root 4096 Jun 4 10:00 .\n\nInput: what is my username"},
    {"role": "assistant", "content": '{"name":"exec","arguments":{"command":"whoami"}}'},
    {"role": "user", "content": "[Tool result]\nroot\n\nInput: create file /tmp/hello.txt with content: hello"},
    {"role": "assistant", "content": '{"name":"write_file","arguments":{"path":"/tmp/hello.txt","content":"hello"}}'},
    {"role": "user", "content": "[Tool result]\n[Written 5 bytes to /tmp/hello.txt]\n\nTask complete. Signal done."},
    {"role": "assistant", "content": '{"name":"exec","arguments":{"command":"echo TASK_DONE"}}'},
]


class Agent:
    def __init__(self, client: DeepSeekClient, model="deepseek-v3", max_rounds=20):
        self.client = client
        self.model = model
        self.max_rounds = max_rounds
        self.messages = []
        self.tools_used = []

    def exec_command(self, command):
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=120, cwd=os.getcwd()
            )
            out = (result.stdout + result.stderr).strip()
            return out[:8000] if out else f"[Exit code: {result.returncode}]"
        except subprocess.TimeoutExpired:
            return "[Timeout: command took more than 120s]"
        except Exception as e:
            return f"[Error: {e}]"

    def write_file(self, path, content):
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"[Written {len(content)} bytes to {path}]"
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
            content = p.read_text()
            if old not in content:
                return "[Pattern not found in file]"
            content = content.replace(old, new, 1)
            p.write_text(content)
            return f"[Edited {path} successfully]"
        except Exception as e:
            return f"[Error editing: {e}]"

    def parse_tool_call(self, response):
        """Extract and normalize a tool call from model response - handles multiple formats."""
        # Strip markdown code blocks
        response = re.sub(r'```(?:json)?\s*', '', response)
        response = re.sub(r'```', '', response).strip()

        def normalize(d):
            """Normalize various tool call formats to {name, arguments}."""
            if not isinstance(d, dict):
                return None
            # Format 1: {name, arguments} - already correct
            if 'name' in d and 'arguments' in d:
                return d
            # Format 2: {tool_calls: [{name, arguments}]}
            if 'tool_calls' in d:
                calls = d['tool_calls']
                if isinstance(calls, list) and calls:
                    tc = calls[0]
                    if 'name' in tc:
                        name = tc['name']
                        args = tc.get('arguments', tc.get('parameters', tc.get('args', {})))
                        # map common name variants
                        name = _map_name(name)
                        return {'name': name, 'arguments': args}
            # Format 3: {function, parameters}
            if 'function' in d:
                name = _map_name(d['function'])
                args = d.get('parameters', d.get('arguments', d.get('args', {})))
                return {'name': name, 'arguments': args}
            # Format 4: {name, parameters}
            if 'name' in d and ('parameters' in d or 'args' in d):
                name = _map_name(d['name'])
                args = d.get('parameters', d.get('args', {}))
                return {'name': name, 'arguments': args}
            return None

        def _map_name(name):
            """Map common name variants to canonical names."""
            m = {
                'execute_command': 'exec', 'run_command': 'exec',
                'shell': 'exec', 'bash': 'exec', 'terminal': 'exec',
                'run_shell': 'exec', 'execute': 'exec', 'command': 'exec',
                'file_read': 'read_file', 'open_file': 'read_file',
                'file_write': 'write_file', 'create_file': 'write_file',
                'file_edit': 'edit_file', 'modify_file': 'edit_file',
            }
            return m.get(name, name)

        def _fix_args(tool):
            """Fix argument key variants."""
            if tool['name'] == 'exec':
                args = tool['arguments']
                if isinstance(args, dict):
                    # map 'cmd', 'shell_command' etc to 'command'
                    for k in ['cmd', 'shell_command', 'shell', 'bash', 'script']:
                        if k in args and 'command' not in args:
                            args['command'] = args.pop(k)
                elif isinstance(args, str):
                    tool['arguments'] = {'command': args}
            return tool

        # Strategy 1: entire response is JSON
        try:
            parsed = json.loads(response)
            result = normalize(parsed)
            if result:
                return _fix_args(result)
        except:
            pass

        # Strategy 2: balanced brace extraction
        depth = 0
        start = None
        for i, ch in enumerate(response):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    candidate = response[start:i+1]
                    try:
                        parsed = json.loads(candidate)
                        result = normalize(parsed)
                        if result:
                            return _fix_args(result)
                    except:
                        pass
                    start = None

        # Strategy 3: line by line
        for line in response.split('\n'):
            line = line.strip()
            if ('"name"' in line or '"function"' in line) and ('"arguments"' in line or '"parameters"' in line):
                try:
                    parsed = json.loads(line)
                    result = normalize(parsed)
                    if result:
                        return _fix_args(result)
                except:
                    pass

        return None

    def execute_tool(self, tool):
        name = tool['name']
        args = tool.get('arguments', {})
        self.tools_used.append(name)
        if name == 'exec':
            return self.exec_command(args.get('command', 'echo no_command'))
        elif name == 'read_file':
            return self.read_file(args.get('path', ''))
        elif name == 'write_file':
            return self.write_file(args.get('path', ''), args.get('content', ''))
        elif name == 'edit_file':
            return self.edit_file(args.get('path', ''), args.get('old', ''), args.get('new', ''))
        else:
            return f"[Unknown tool: {name}]"

    def is_task_done(self, tool_call):
        if tool_call.get('name') == 'exec':
            cmd = tool_call.get('arguments', {}).get('command', '')
            if 'TASK_DONE' in cmd:
                return True
        return False

    def run(self, user_input, callback=None):
        self.messages.append({"role": "user", "content": f"{user_input}\n\n(respond ONLY with JSON: {{\"name\":\"exec\",\"arguments\":{{\"command\":\"CMD\"}}}} or other tool JSON. No text. JSON only.)"})
        last_output = ""
        retries = 0
        max_retries = 3

        for round_num in range(self.max_rounds):
            if callback:
                callback("thinking", f"Round {round_num + 1}/{self.max_rounds}")

            full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + FEW_SHOT + self.messages[-10:]

            try:
                response = self.client.send_message(full_messages, self.model)
            except Exception as e:
                return f"[API error: {e}]"

            response = response.strip()
            tool_call = self.parse_tool_call(response)

            if tool_call:
                retries = 0
                if callback:
                    callback("exec", json.dumps(tool_call, ensure_ascii=False))

                output = self.execute_tool(tool_call)
                last_output = output

                if callback:
                    callback("output", output)

                if self.is_task_done(tool_call):
                    self.messages.append({"role": "assistant", "content": response})
                    if callback:
                        callback("done", last_output)
                    return last_output

                self.messages.append({"role": "assistant", "content": response})
                self.messages.append({
                    "role": "user",
                    "content": f"[Tool result]\n{output}\n\nIf task is done, respond with: {{\"name\":\"exec\",\"arguments\":{{\"command\":\"echo TASK_DONE\"}}}}. Otherwise continue with JSON tool call."
                })

            else:
                retries += 1
                if callback:
                    callback("thinking", f"No tool call (retry {retries}/{max_retries})")

                if retries >= max_retries:
                    if callback:
                        callback("done", last_output or response)
                    return last_output or response

                self.messages.append({"role": "assistant", "content": response})
                self.messages.append({
                    "role": "user",
                    "content": 'Output ONLY JSON. No text. Example: {"name":"exec","arguments":{"command":"whoami"}}'
                })

        if callback:
            callback("done", last_output)
        return last_output or f"[Max rounds. Tools: {', '.join(self.tools_used)}]"

    def clear(self):
        self.messages = []
        self.tools_used = []
