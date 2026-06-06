"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const path = __importStar(require("path"));
const child_process = __importStar(require("child_process"));
const readline = __importStar(require("readline"));
const DEV = process.env.NODE_ENV === "development";
const ROOT = path.resolve(__dirname, "../../");
let win = null;
// ── Spawn Python bridge ──────────────────────────────────────────────────────
const agentProc = child_process.spawn("python3", [path.join(ROOT, "bridge.py")], {
    cwd: ROOT,
    stdio: ["pipe", "pipe", "pipe"],
    env: { ...process.env },
});
const rl = readline.createInterface({ input: agentProc.stdout });
rl.on("line", (line) => {
    try {
        const event = JSON.parse(line);
        win?.webContents.send("agent-event", event);
    }
    catch { }
});
agentProc.stderr.on("data", (d) => {
    win?.webContents.send("agent-stderr", d.toString());
});
// ── IPC: renderer → agent ────────────────────────────────────────────────────
electron_1.ipcMain.on("agent-message", (_evt, payload) => {
    agentProc.stdin.write(payload + "\n");
});
// ── Create window ────────────────────────────────────────────────────────────
function createWindow() {
    win = new electron_1.BrowserWindow({
        width: 1280,
        height: 800,
        minWidth: 900,
        minHeight: 600,
        backgroundColor: "#0a0a0a",
        titleBarStyle: "hiddenInset",
        frame: false, // frameless — we draw our own titlebar
        webPreferences: {
            preload: path.join(__dirname, "preload.js"),
            nodeIntegration: false,
            contextIsolation: true,
        },
        icon: path.join(ROOT, "ui-ts", "assets", "icon.png"),
    });
    if (DEV) {
        win.loadURL("http://localhost:5173");
        win.webContents.openDevTools({ mode: "detach" });
    }
    else {
        win.loadFile(path.join(__dirname, "../dist/renderer/index.html"));
    }
    win.on("closed", () => {
        win = null;
        agentProc.kill();
        electron_1.app.quit();
    });
}
electron_1.app.whenReady().then(createWindow);
electron_1.app.on("window-all-closed", () => { if (process.platform !== "darwin")
    electron_1.app.quit(); });
electron_1.app.on("activate", () => { if (!win)
    createWindow(); });
//# sourceMappingURL=main.js.map