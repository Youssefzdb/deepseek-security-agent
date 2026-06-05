import React, { useState, useCallback } from "react";
import { Box, Text, useApp } from "ink";
import { Banner }       from "./components/Banner.js";
import { MessageBubble, Role } from "./components/MessageBubble.js";
import { BashBlock, OutputBlock } from "./components/BashBlock.js";
import { TodoPanel, TodoItem }   from "./components/TodoPanel.js";
import { StatusBar }    from "./components/StatusBar.js";
import { InputBar }     from "./components/InputBar.js";

// ── Message types ─────────────────────────────────────────────────────────────
type MsgType =
  | { type: "chat";    role: Role;    content: string }
  | { type: "bash";    cmd: string;   n: number       }
  | { type: "output";  output: string                  }
  | { type: "thinking"; msg: string                    }
  | { type: "file";    action: "read" | "write"; path: string }
  | { type: "rule"                                      };

interface AppProps {
  model: string;
  path: string;
  toolCount: number;
  onMessage: (msg: string, cb: (action: string, detail: string) => void) => void;
}

export const App: React.FC<AppProps> = ({ model, path, toolCount, onMessage }) => {
  const { exit } = useApp();

  const [messages,  setMessages]  = useState<MsgType[]>([]);
  const [todos,     setTodos]     = useState<TodoItem[]>([]);
  const [thinking,  setThinking]  = useState(false);
  const [thinkMsg,  setThinkMsg]  = useState("Thinking…");
  const [busy,      setBusy]      = useState(false);
  const [msgCount,  setMsgCount]  = useState(0);
  const [cmdN,      setCmdN]      = useState(0);
  const [showBanner, setShowBanner] = useState(true);

  const push = useCallback((m: MsgType) => {
    setMessages(prev => [...prev, m]);
  }, []);

  const handleSubmit = useCallback((input: string) => {
    const cmd = input.trim();

    // ── Slash commands ─────────────────────────────────────────────────────────
    if (cmd === "/exit" || cmd === "/quit") { exit(); return; }
    if (cmd === "/clear") {
      setMessages([]); setTodos([]); setCmdN(0);
      push({ type: "chat", role: "system", content: "History cleared." });
      return;
    }
    if (cmd === "/help") {
      push({ type: "chat", role: "system", content: [
        "Commands:",
        "  /exit /quit   — quit",
        "  /clear        — clear history",
        "  /tools        — list tools",
        "  /model <name> — switch model",
        "  /save <path>  — save history",
        "  /load <path>  — load history",
        "  /status       — show status",
        "  /history      — last 10 msgs",
      ].join("\n") });
      return;
    }

    // ── Normal message ─────────────────────────────────────────────────────────
    setShowBanner(false);
    push({ type: "chat", role: "user", content: cmd });
    setMsgCount(c => c + 1);
    setBusy(true);
    setThinking(true);
    setThinkMsg("Thinking…");

    let localCmdN = cmdN;

    const callback = (action: string, detail: string) => {
      switch (action) {
        case "thinking":
          setThinkMsg(detail || "Thinking…");
          setThinking(true);
          break;
        case "exec": {
          setThinking(false);
          localCmdN++;
          setCmdN(localCmdN);
          let parsed = detail;
          try {
            const obj = JSON.parse(detail);
            parsed = obj?.arguments?.command ?? detail;
          } catch {}
          push({ type: "bash", cmd: parsed, n: localCmdN });
          break;
        }
        case "output":
          push({ type: "output", output: detail });
          break;
        case "write":
          push({ type: "file", action: "write", path: detail });
          break;
        case "read":
          push({ type: "file", action: "read", path: detail });
          break;
        case "todo_update":
        case "todo_summary":
          try {
            const t = JSON.parse(detail);
            if (Array.isArray(t)) setTodos(t);
          } catch {}
          break;
        case "done":
          setThinking(false);
          setBusy(false);
          push({ type: "chat", role: "assistant",
                 content: detail && detail !== "TASK_DONE" ? detail : "✅ Done." });
          break;
        default:
          break;
      }
    };

    onMessage(cmd, callback);
  }, [cmdN, push, exit, onMessage]);

  return (
    <Box flexDirection="column" height="100%">

      {/* ── Banner (shown until first message) ─────────────────────── */}
      {showBanner && (
        <Banner model={model} path={path} toolCount={toolCount} />
      )}

      {/* ── Conversation scroll area ────────────────────────────────── */}
      <Box flexDirection="column" flexGrow={1} overflow="hidden">
        {messages.map((m, i) => {
          switch (m.type) {
            case "chat":
              return <MessageBubble key={i} role={m.role} content={m.content} />;
            case "bash":
              return <BashBlock key={i} cmd={m.cmd} n={m.n} />;
            case "output":
              return <OutputBlock key={i} output={m.output} />;
            case "file":
              return (
                <Box key={i} paddingX={4}>
                  <Text color={m.action === "write" ? "#d4a72c" : "#56c8d8"}>
                    {m.action === "write" ? "✎ wrote " : "📖 read "}
                  </Text>
                  <Text color="#888878">{m.path}</Text>
                </Box>
              );
            case "thinking":
              return (
                <Box key={i} paddingX={4}>
                  <Text italic color="#d4a72c">● {m.msg}</Text>
                </Box>
              );
            case "rule":
              return (
                <Box key={i} paddingX={2}>
                  <Text color="#383838">{"─".repeat(58)}</Text>
                </Box>
              );
            default:
              return null;
          }
        })}

        {/* Live thinking indicator */}
        {thinking && (
          <Box paddingX={4}>
            <Text italic color="#d4a72c">● {thinkMsg}</Text>
          </Box>
        )}

        {/* Todo panel */}
        {todos.length > 0 && <TodoPanel todos={todos} />}
      </Box>

      {/* ── Status bar ──────────────────────────────────────────────── */}
      <StatusBar
        model={model}
        thinking={thinking}
        thinkingMsg={thinkMsg}
        msgCount={msgCount}
      />

      {/* ── Input bar ───────────────────────────────────────────────── */}
      <InputBar onSubmit={handleSubmit} disabled={busy && !thinking} />

    </Box>
  );
};
