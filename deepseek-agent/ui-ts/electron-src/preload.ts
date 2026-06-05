import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("agent", {
  send: (payload: string) => ipcRenderer.send("agent-message", payload),
  on:   (cb: (event: { id: string; action: string; detail: string }) => void) => {
    ipcRenderer.on("agent-event",  (_e, data) => cb(data));
  },
  onStderr: (cb: (msg: string) => void) => {
    ipcRenderer.on("agent-stderr", (_e, msg) => cb(msg));
  },
});
