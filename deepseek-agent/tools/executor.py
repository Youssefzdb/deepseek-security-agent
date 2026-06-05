#!/usr/bin/env python3
"""
Executor — robust shell command runner.
Supports: sync, background, timeout, Termux auto-detect, history.
"""
import subprocess, os, time, shutil
from pathlib import Path


class Executor:
    def __init__(self, cwd: str | None = None, timeout: int = 120):
        self.cwd       = cwd or os.getcwd()
        self.timeout   = timeout
        self.is_termux = self._detect_termux()
        self.history: list[dict] = []

    # ── Environment ───────────────────────────────────────────────────────────
    def _detect_termux(self) -> bool:
        return (
            os.path.exists("/data/data/com.termux")
            or "TERMUX_VERSION" in os.environ
        )

    def _env(self) -> dict:
        env = os.environ.copy()
        if self.is_termux:
            env["PATH"] = (
                "/data/data/com.termux/files/usr/bin:" + env.get("PATH", "")
            )
        return env

    # ── Sync run ──────────────────────────────────────────────────────────────
    def run(self, command: str, timeout: int | None = None) -> tuple[str, int]:
        """
        Execute command synchronously.
        Returns (output_str, returncode).
        """
        t = timeout or self.timeout
        self.history.append({"command": command, "time": time.time()})
        try:
            r = subprocess.run(
                command, shell=True, capture_output=True,
                text=True, timeout=t, cwd=self.cwd, env=self._env()
            )
            out = (r.stdout + r.stderr).strip()
            return (out[:12000] if out else f"[exit {r.returncode}]"), r.returncode
        except subprocess.TimeoutExpired:
            return f"[Timeout >{t}s]", -1
        except Exception as e:
            return f"[Error: {e}]", -1

    # ── Background run ────────────────────────────────────────────────────────
    def run_background(self, command: str) -> int | str:
        """Run command in background. Returns PID or error string."""
        try:
            proc = subprocess.Popen(
                command, shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=self.cwd, env=self._env()
            )
            return proc.pid
        except Exception as e:
            return f"[Error: {e}]"

    # ── Tool availability ─────────────────────────────────────────────────────
    def is_available(self, tool: str) -> bool:
        """Check if a tool exists on PATH."""
        return shutil.which(tool) is not None

    def install_if_missing(self, tool: str) -> bool:
        """Auto-install missing tool via pkg (Termux) or apt."""
        if self.is_available(tool):
            return False
        if self.is_termux:
            self.run(f"pkg install -y {tool}", timeout=180)
        else:
            self.run(f"apt-get install -y {tool}", timeout=180)
        return True

    # ── History ───────────────────────────────────────────────────────────────
    def last(self, n: int = 5) -> list[dict]:
        return self.history[-n:]

    def clear_history(self):
        self.history.clear()
