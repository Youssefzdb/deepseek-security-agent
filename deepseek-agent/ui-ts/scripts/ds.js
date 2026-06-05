#!/usr/bin/env node
/**
 * ds — Global launcher for DeepSeek Security Agent.
 *
 * Install globally:   npm install -g .   (from ui-ts/ directory)
 * Then run anywhere:  ds
 *
 * What it does:
 *   1. Builds Electron main process if needed
 *   2. Starts Vite dev server
 *   3. Launches Electron (login screen → 3D mask + terminal)
 */

const path  = require("path");
const { spawnSync, spawn } = require("child_process");
const fs    = require("fs");

const ROOT = path.resolve(__dirname, "..");

// ── Ensure electron main is compiled ─────────────────────────────────────────
const electronMain = path.join(ROOT, "electron", "main.js");
if (!fs.existsSync(electronMain)) {
  console.log("[ds] Building Electron main process…");
  const r = spawnSync(
    process.platform === "win32" ? "npx.cmd" : "npx",
    ["tsc", "-p", path.join(ROOT, "tsconfig.electron.json")],
    { cwd: ROOT, stdio: "inherit" }
  );
  if (r.status !== 0) {
    console.error("[ds] Build failed. Run `npm install` in ui-ts/ first.");
    process.exit(1);
  }
}

// ── Delegate to dev.js ────────────────────────────────────────────────────────
require(path.join(ROOT, "scripts", "dev.js"));
