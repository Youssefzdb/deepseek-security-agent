import React from "react";
import { Box, Text } from "ink";
const roleColors = {
    user: "#4888cc",
    assistant: "#38a860",
    system: "#888878",
};
const roleLabels = {
    user: "You",
    assistant: "DeepSeek",
    system: "System",
};
export const MessageBubble = ({ role, content }) => {
    const color = roleColors[role];
    const label = roleLabels[role];
    const isUser = role === "user";
    return (React.createElement(Box, { flexDirection: "column", marginY: 1, paddingX: 2 },
        React.createElement(Text, { bold: true, color: color }, label),
        React.createElement(Box, { borderStyle: "round", borderColor: isUser ? "#284060" : "#1c3828", paddingX: 2, paddingY: 0 },
            React.createElement(Text, { color: "#c8c8b8", wrap: "wrap" }, content))));
};
