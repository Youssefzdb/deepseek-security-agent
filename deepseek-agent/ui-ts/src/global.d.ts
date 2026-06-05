/// <reference types="vite/client" />

interface AgentBridge {
  send:     (payload: string) => void;
  on:       (cb: (e: { id: string; action: string; detail: string }) => void) => void;
  onStderr: (cb: (msg: string) => void) => void;
}

interface Window {
  agent?: AgentBridge;
}
