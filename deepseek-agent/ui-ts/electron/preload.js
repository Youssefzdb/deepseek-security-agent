"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
electron_1.contextBridge.exposeInMainWorld("agent", {
    send: (payload) => electron_1.ipcRenderer.send("agent-message", payload),
    on: (cb) => {
        electron_1.ipcRenderer.on("agent-event", (_e, data) => cb(data));
    },
    onStderr: (cb) => {
        electron_1.ipcRenderer.on("agent-stderr", (_e, msg) => cb(msg));
    },
});
//# sourceMappingURL=preload.js.map