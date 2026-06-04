#!/usr/bin/env python3
"""Execute any shell command — no restrictions."""
import subprocess, os, time, signal
from pathlib import Path


class Executor:
    def __init__(self, cwd=None, timeout=120):
        self.cwd = cwd or os.getcwd()
        self.timeout = timeout
        self.is_termux = self._detect_termux()
        self.history = []

    def _detect_termux(self):
        return os.path.exists("/data/data/com.termux") or "TERMUX_VERSION" in os.environ

    def run(self, command, timeout=None):
        """Execute command, return (stdout+stderr, returncode)."""
        timeout = timeout or self.timeout
        self.history.append({"command": command, "time": time.time()})
        try:
            env = os.environ.copy()
            if self.is_termux:
                env["PATH"] = "/data/data/com.termux/files/usr/bin:" + env.get("PATH", "")

            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=self.cwd, env=env
            )
            output = result.stdout + result.stderr
            return output[:10000] if output else f"Exit code: {result.returncode}", result.returncode
        except subprocess.TimeoutExpired:
            return f"Timed out after {timeout}s", -1
        except Exception as e:
            return f"Error: {e}", -1

    def run_background(self, command):
        """Run command in background, return PID."""
        try:
            proc = subprocess.Popen(
                command, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, cwd=self.cwd
            )
            return proc.pid
        except Exception as e:
            return f"Error: {e}"

    def install_if_missing(self, tool):
        """Auto-install missing tool."""
        check, _ = self.run(f"which {tool}", timeout=10)
        if "not found" in check or check.strip() == "":
            if self.is_termux:
                self.run(f"pkg install -y {tool}", timeout=120)
            else:
                self.run(f"apt-get install -y {tool}", timeout=120)
            return True
        return False
