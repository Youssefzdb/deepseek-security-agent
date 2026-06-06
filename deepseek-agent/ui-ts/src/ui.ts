import { showLogin } from "./login.js";

/**
 * ui.ts — Terminal UI logic (runs in Electron renderer / Vite dev)
 *
 * Communicates with the Python agent via window.agent (injected by preload.ts)
 * Falls back to a mock in browser-only mode (npm run dev without Electron).
 */

interface AgentEvent {
  id:     string;
  action: string;
  detail: string;
}

interface TodoItem {
  content: string;
  status:  "pending" | "in_progress" | "completed" | "cancelled";
}

// ── DOM refs ──────────────────────────────────────────────────────────────────
const msgs       = document.getElementById("msgs")!;
const inp        = document.getElementById("inp") as HTMLInputElement;
const think      = document.getElementById("think")!;
const sbModel    = document.getElementById("sb-model")!;
const sbStatus   = document.getElementById("sb-status")!;
const sbCount    = document.getElementById("sb-count")!;
const sbSpin     = document.getElementById("sb-spin")!;
const todo       = document.getElementById("todo")!;
const toFill     = document.getElementById("to-fill")!;
const toItems    = document.getElementById("to-items")!;

// ── State ──────────────────────────────────────────────────────────────────────
let msgCount  = 0;
let cmdCount  = 0;
let busy      = false;
let msgId     = 0;
let activeCreds: Record<string, string> = {};

// ── Helpers ───────────────────────────────────────────────────────────────────
function scrollBottom() {
  msgs.scrollTop = msgs.scrollHeight;
}

function setThinking(on: boolean, text = "Thinking…") {
  think.textContent = text;
  think.classList.toggle("vis", on);
  sbSpin.classList.toggle("vis", on);
  sbStatus.textContent = on ? text : "idle";
}

function setBusy(on: boolean) {
  busy = on;
  inp.disabled = on;
}

// ── Render functions ──────────────────────────────────────────────────────────
function appendBubble(role: "u" | "a" | "s", content: string) {
  const labels: Record<string, string> = { u: "You", a: "Agent", s: "System" };
  const d = document.createElement("div");
  d.className = "msg";
  d.innerHTML = `
    <span class="ml ${role}">${labels[role]}</span>
    <div class="mb ${role}">${escHtml(content)}</div>
  `;
  msgs.appendChild(d);
  scrollBottom();
}

function appendBash(cmd: string, n: number) {
  const lines = cmd.trim().split("\n");
  const inner = lines.map((l, i) =>
    `<span class="pr">${i === 0 ? "$ " : "  "}</span><span>${escHtml(l)}</span>`
  ).join("<br>");

  const d = document.createElement("div");
  d.className = "bash";
  d.innerHTML = `
    <div class="bh">
      <span class="ar">▸ bash</span>
      <span class="bn">  cmd #${n}</span>
    </div>
    <div class="bc">${inner}</div>
  `;
  msgs.appendChild(d);
  scrollBottom();
}

function appendOutput(output: string) {
  const lines = output.trim().split("\n");
  const MAX   = 30;
  const shown = lines.slice(0, MAX).map(l => escHtml(l)).join("\n");
  const extra = lines.length > MAX ? `\n… (${lines.length - MAX} more lines)` : "";
  const d = document.createElement("div");
  d.className = "out";
  d.innerHTML = `<div class="out-title">output</div><pre style="margin:0;font-family:inherit;font-size:11px">${shown}${extra}</pre>`;
  msgs.appendChild(d);
  scrollBottom();
}

function appendFile(action: "read" | "write", path: string) {
  const d   = document.createElement("div");
  d.className = "fev";
  const icon = action === "write" ? "✎" : "📖";
  const col  = action === "write" ? "var(--orange)" : "var(--teal)";
  d.innerHTML = `<span style="color:${col}">${icon} ${action}</span> <span style="color:var(--dwhite)">${escHtml(path)}</span>`;
  msgs.appendChild(d);
  scrollBottom();
}

function renderTodo(items: TodoItem[]) {
  if (!items.length) { todo.classList.remove("vis"); return; }

  const done  = items.filter(t => t.status === "completed").length;
  const total = items.length;
  const pct   = Math.round((done / total) * 100);
  toFill.style.width = pct + "%";

  const iconMap: Record<string, [string, string]> = {
    pending:     ["○", "p"],
    in_progress: ["▶", "i"],
    completed:   ["✓", "c"],
    cancelled:   ["✗", "x"],
  };

  toItems.innerHTML = items.map(t => {
    const [icon, cls] = iconMap[t.status] ?? ["○", "p"];
    const textCls = (t.status === "completed" || t.status === "cancelled") ? "d" : "";
    return `<div class="to-item">
      <span class="ti ${cls}">${icon}</span>
      <span class="tt ${textCls}">${escHtml(t.content)}</span>
    </div>`;
  }).join("");

  todo.classList.add("vis");
}

function escHtml(s: string) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── Agent communication ───────────────────────────────────────────────────────
function handleEvent(e: AgentEvent) {
  switch (e.action) {

    case "thinking":
      setThinking(true, e.detail || "Thinking…");
      break;

    case "step_start": {
      try {
        const s = JSON.parse(e.detail);
        setThinking(true, s.desc || "Executing step…");
      } catch { setThinking(true, "Executing step…"); }
      break;
    }

    case "exec": {
      setThinking(false);
      cmdCount++;
      let cmd = e.detail;
      try { cmd = JSON.parse(e.detail)?.arguments?.command ?? e.detail; } catch {}
      appendBash(cmd, cmdCount);
      break;
    }

    case "output":
      appendOutput(e.detail);
      break;

    case "write":
      appendFile("write", e.detail);
      break;

    case "read":
      appendFile("read", e.detail);
      break;

    case "todo_update":
    case "todo_summary":
      try { renderTodo(JSON.parse(e.detail)); } catch {}
      break;

    case "done":
      setThinking(false);
      setBusy(false);
      appendBubble("a", e.detail && e.detail !== "TASK_DONE" ? e.detail : "✅ Done.");
      break;

    case "error":
      setThinking(false);
      setBusy(false);
      appendBubble("s", "⚠ " + e.detail);
      break;

    case "auth_ok":
      break; // handled in login.ts

    case "auth_fail":
      break; // handled in login.ts
  }
}

function sendMessage(text: string) {
  const id      = String(++msgId);
  const payload = JSON.stringify({
    id,
    message: text,
    ...activeCreds,         // provider, model, api_key, email, etc.
  });

  if ((window as any).agent) {
    (window as any).agent.send(payload);
  } else {
    // Dev-mode mock
    setTimeout(() => handleEvent({ id, action: "done", detail: `[mock] ${text}` }), 800);
  }
}

// ── Wire up IPC ───────────────────────────────────────────────────────────────
if ((window as any).agent) {
  (window as any).agent.on(handleEvent);
  (window as any).agent.onStderr((msg: string) => {
    console.warn("[agent stderr]", msg);
  });
}

// ── Slash commands ────────────────────────────────────────────────────────────
const COMMANDS: Record<string, () => void> = {
  "/help": () => appendBubble("s", [
    "Commands:",
    "  /exit /quit   — quit",
    "  /clear        — clear history",
    "  /tools        — list available tools",
    "  /status       — connection status",
  ].join("\n")),

  "/clear": () => {
    msgs.innerHTML = "";
    renderTodo([]);
    cmdCount = 0;
    appendBubble("s", "History cleared.");
  },

  "/tools": () => appendBubble("s", [
    "Tools: nmap, ping, traceroute, whois, dig, curl, nc,",
    "  ffuf, gobuster, nikto, whatweb, hydra, john, hashcat,",
    "  sqlmap, wpscan, dirb, enum4linux, smbclient, amass,",
    "  subfinder, dnsx, httpx, nuclei, arjun, xsstrike,",
    "  commix, tshark, read_file, write_file, grep, bash",
  ].join("\n")),

  "/exit":   () => window.close(),
  "/quit":   () => window.close(),

  "/status": () => appendBubble("s",
    `provider: ${activeCreds.provider || "auto"} · model: ${activeCreds.model || "default"} · msgs: ${msgCount} · cmds: ${cmdCount}`
  ),
};

// ── Input handling ────────────────────────────────────────────────────────────
inp.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" || busy) return;
  const raw = inp.value.trim();
  if (!raw) return;
  inp.value = "";

  const base = raw.split(" ")[0].toLowerCase();
  if (COMMANDS[base]) { COMMANDS[base](); return; }

  msgCount++;
  sbCount.textContent = String(msgCount);
  appendBubble("u", raw);
  setBusy(true);
  setThinking(true);
  sendMessage(raw);
});

document.addEventListener("click", () => {
  if (!document.getElementById("login-overlay")) inp.focus();
});

// ── Boot — show login, then reveal UI ────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const app = document.getElementById("app");
  if (app) app.style.opacity = "0";
});

showLogin((creds) => {
  activeCreds = creds;

  // Update statusbar model badge
  sbModel.textContent  = creds.model || "—";

  // Send creds to bridge
  if ((window as any).agent) {
    (window as any).agent.send(JSON.stringify({
      id: "__creds__",
      message: "__SET_CREDS__",
      ...creds,
    }));
  }

  const app = document.getElementById("app")!;
  app.style.transition = "opacity 0.4s";
  app.style.opacity    = "1";
  inp.focus();

  appendBubble("s",
    `Connected · provider: ${creds.provider} · model: ${creds.model}\nType /help for commands.`
  );
});
