import React from "react";
import { Box, Text } from "ink";
const STATUS_ICON = {
    pending: "○",
    in_progress: "▶",
    completed: "✓",
    cancelled: "✗",
};
const STATUS_COLOR = {
    pending: "#585858",
    in_progress: "#d4a72c",
    completed: "#38a860",
    cancelled: "#e06c75",
};
export const TodoPanel = ({ todos }) => {
    if (!todos.length)
        return null;
    const done = todos.filter(t => t.status === "completed").length;
    const total = todos.length;
    const pct = Math.round((done / total) * 100);
    // Progress bar
    const barLen = 30;
    const filled = Math.round((done / total) * barLen);
    const bar = "█".repeat(filled) + "░".repeat(barLen - filled);
    return (React.createElement(Box, { flexDirection: "column", borderStyle: "round", borderColor: "#383838", paddingX: 2, paddingY: 0, marginX: 2, marginY: 1 },
        React.createElement(Box, { marginBottom: 1 },
            React.createElement(Text, { bold: true, color: "#d4a72c" }, "Task Progress  "),
            React.createElement(Text, { color: "#38a860" }, done),
            React.createElement(Text, { color: "#585858" },
                "/",
                total,
                "  "),
            React.createElement(Text, { color: "#56c8d8" },
                pct,
                "%")),
        React.createElement(Box, { marginBottom: 1 },
            React.createElement(Text, { color: "#38a860" }, bar.slice(0, filled)),
            React.createElement(Text, { color: "#383838" }, bar.slice(filled))),
        todos.map((t, i) => {
            const icon = STATUS_ICON[t.status];
            const color = STATUS_COLOR[t.status];
            const dim = t.status === "completed" || t.status === "cancelled";
            return (React.createElement(Box, { key: i },
                React.createElement(Text, { bold: true, color: color },
                    icon,
                    " "),
                React.createElement(Text, { color: dim ? "#585858" : "#c8c8b8", dimColor: dim }, t.content)));
        })));
};
