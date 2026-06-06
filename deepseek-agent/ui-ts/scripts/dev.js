#!/usr/bin/env node
/**
 * scripts/dev.js
 * Starts Vite dev server then launches Electron.
 */
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

const ROOT      = path.resolve(__dirname, "..");
const VITE_PORT = 5173;
const VITE_URL  = `http://localhost:${VITE_PORT}`;

// ── 1. Start Vite ─────────────────────────────────────────────────────────────
const vite = spawn(
  process.platform === "win32" ? "npx.cmd" : "npx",
  ["vite", "--port", String(VITE_PORT)],
  { cwd: ROOT, stdio: "inherit", env: { ...process.env, NODE_ENV: "development" } }
);

vite.on("error", (err) => { console.error("[vite]", err.message); process.exit(1); });

// ── 2. Wait for Vite, then launch Electron with --no-sandbox (needed for root) ─
function waitForVite(retries = 40) {
  http.get(VITE_URL, (res) => {
    if (res.statusCode && res.statusCode < 500) {
      startElectron();
    } else {
      retry(retries);
    }
  }).on("error", () => retry(retries));
}

function retry(remaining) {
  if (remaining <= 0) {
    console.error("[ds] Vite did not start in time.");
    vite.kill();
    process.exit(1);
  }
  setTimeout(() => waitForVite(remaining - 1), 500);
}

function startElectron() {
  const electron = spawn(
    process.platform === "win32" ? "npx.cmd" : "npx",
    ["electron", ".", "--no-sandbox"],   // ← fix for root user
    { cwd: ROOT, stdio: "inherit", env: { ...process.env, NODE_ENV: "development" } }
  );

  electron.on("close", (code) => {
    vite.kill();
    process.exit(code ?? 0);
  });
}

setTimeout(() => waitForVite(), 1000);
process.on("SIGINT", () => { vite.kill(); process.exit(0); });
