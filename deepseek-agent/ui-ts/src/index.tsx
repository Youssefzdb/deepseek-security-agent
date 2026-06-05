#!/usr/bin/env node
/**
 * DeepSeek Security Agent — TypeScript/Ink UI entry point.
 *
 * Usage:
 *   npm run dev
 *   node dist/index.js --model deepseek-coder
 */
import React from "react";
import { render } from "ink";
import { App } from "./App.js";

// ── CLI args ──────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const modelIdx = args.indexOf("--model");
const model    = modelIdx !== -1 ? args[modelIdx + 1] : "deepseek-coder";
const pathArg  = process.cwd();

// ── Python bridge — spawn the Python agent and communicate via stdio ──────────
import { spawn } from "child_process";
import * as readline from "readline";
import * as path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AGENT_DIR = path.resolve(__dirname, "../../");

/**
 * Spawn Python agent as a subprocess.
 * The Python side reads JSON lines from stdin and writes JSON events to stdout.
 */
const agentProc = spawn("python3", [path.join(AGENT_DIR, "bridge.py")], {
  cwd:   AGENT_DIR,
  stdio: ["pipe", "pipe", "inherit"],
  env:   { ...process.env },
});

const rl = readline.createInterface({ input: agentProc.stdout! });

// ── Callbacks registry ────────────────────────────────────────────────────────
const pendingCallbacks = new Map<string, (action: string, detail: string) => void>();

rl.on("line", (line) => {
  try {
    const event = JSON.parse(line) as {
      id: string; action: string; detail: string;
    };
    const cb = pendingCallbacks.get(event.id);
    if (cb) {
      cb(event.action, event.detail);
      if (event.action === "done") {
        pendingCallbacks.delete(event.id);
      }
    }
  } catch {}
});

let msgId = 0;

function sendMessage(
  msg: string,
  callback: (action: string, detail: string) => void
) {
  const id = String(++msgId);
  pendingCallbacks.set(id, callback);
  const payload = JSON.stringify({ id, message: msg, model }) + "\n";
  agentProc.stdin!.write(payload);
}

// ── Render ────────────────────────────────────────────────────────────────────
const TOOL_COUNT = 30;

render(
  <App
    model={model}
    path={pathArg}
    toolCount={TOOL_COUNT}
    onMessage={sendMessage}
  />,
  { exitOnCtrlC: true }
);
