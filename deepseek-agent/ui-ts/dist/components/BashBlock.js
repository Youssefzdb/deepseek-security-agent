import React from "react";
import { Box, Text } from "ink";
export const BashBlock = ({ cmd, n }) => {
    const lines = cmd.trim().split("\n");
    return (React.createElement(Box, { flexDirection: "column", marginY: 1, paddingX: 2 },
        React.createElement(Box, null,
            React.createElement(Text, { bold: true, color: "#d4a72c" }, "\u25B8 bash  "),
            React.createElement(Text, { color: "#484838" },
                "cmd #",
                n)),
        React.createElement(Box, { borderStyle: "single", borderColor: "#d4a72c", paddingX: 2, paddingY: 0 }, lines.length === 1 ? (React.createElement(Box, null,
            React.createElement(Text, { bold: true, color: "#56c8d8" }, "$ "),
            React.createElement(Text, { color: "#c8c8b8" }, cmd.trim()))) : (React.createElement(Box, { flexDirection: "column" }, lines.map((line, i) => (React.createElement(Box, { key: i },
            React.createElement(Text, { bold: true, color: "#56c8d8" }, i === 0 ? "$ " : "  "),
            React.createElement(Text, { color: "#c8c8b8" }, line)))))))));
};
export const OutputBlock = ({ output, maxLines = 35 }) => {
    const allLines = output.trim().split("\n");
    const truncated = allLines.length > maxLines;
    const lines = truncated ? allLines.slice(0, maxLines) : allLines;
    return (React.createElement(Box, { flexDirection: "column", paddingX: 2 },
        React.createElement(Box, { borderStyle: "single", borderColor: "#383838", paddingX: 2, paddingY: 0 },
            React.createElement(Box, { flexDirection: "column" },
                React.createElement(Text, { color: "#585858" }, "output"),
                lines.map((line, i) => (React.createElement(Text, { key: i, color: "#888878", dimColor: true }, line))),
                truncated && (React.createElement(Text, { color: "#585858", dimColor: true },
                    "\u2026 (",
                    allLines.length - maxLines,
                    " more lines)"))))));
};
