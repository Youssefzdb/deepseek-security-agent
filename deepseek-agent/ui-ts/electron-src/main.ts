import { app, BrowserWindow, ipcMain, shell } from "electron";
import * as path from "path";
import * as child_process from "child_process";
import * as readline from "readline";

const DEV  = process.env.NODE_ENV === "development";
const ROOT = path.resolve(__dirname, "../../");

let win: BrowserWindow | null = null;

// ── Spawn Python bridge ──────────────────────────────────────────────────────
const agentProc = child_process.spawn(
  "python3",
  [path.join(ROOT, "bridge.py")],
  {
    cwd:   ROOT,
    stdio: ["pipe", "pipe", "pipe"],
    env:   { ...process.env },
  }
);

const rl = readline.createInterface({ input: agentProc.stdout! });

rl.on("line", (line) => {
  try {
    const event = JSON.parse(line);
    win?.webContents.send("agent-event", event);
  } catch {}
});

agentProc.stderr!.on("data", (d) => {
  win?.webContents.send("agent-stderr", d.toString());
});

// ── IPC: renderer → agent ────────────────────────────────────────────────────
ipcMain.on("agent-message", (_evt, payload: string) => {
  agentProc.stdin!.write(payload + "\n");
});

// ── Create window ────────────────────────────────────────────────────────────
function createWindow() {
  win = new BrowserWindow({
    width:           1280,
    height:          800,
    minWidth:        900,
    minHeight:       600,
    backgroundColor: "#0a0a0a",
    titleBarStyle:   "hiddenInset",
    frame:           false,          // frameless — we draw our own titlebar
    webPreferences: {
      preload:        path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
    icon: path.join(ROOT, "ui-ts", "assets", "icon.png"),
  });

  if (DEV) {
    win.loadURL("http://localhost:5173");
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    win.loadFile(path.join(__dirname, "../dist/renderer/index.html"));
  }

  win.on("closed", () => {
    win = null;
    agentProc.kill();
    app.quit();
  });
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
app.on("activate", () => { if (!win) createWindow(); });
