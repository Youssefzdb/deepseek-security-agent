import React from "react";
import { Box, Text } from "ink";
import Spinner from "ink-spinner";
export const StatusBar = ({ model, thinking, thinkingMsg = "Thinking…", msgCount, }) => {
    return (React.createElement(Box, { borderStyle: "single", borderColor: "#282828", paddingX: 2, justifyContent: "space-between" },
        React.createElement(Box, null,
            React.createElement(Text, { color: "#585858" }, "model: "),
            React.createElement(Text, { color: "#c8aa50", bold: true }, model)),
        thinking ? (React.createElement(Box, null,
            React.createElement(Text, { color: "#d4a72c" },
                React.createElement(Spinner, { type: "dots" })),
            React.createElement(Text, { color: "#d4a72c", italic: true },
                "  ",
                thinkingMsg))) : (React.createElement(Text, { color: "#383838" }, "\u2500\u2500")),
        React.createElement(Box, null,
            React.createElement(Text, { color: "#585858" }, "msgs: "),
            React.createElement(Text, { color: "#888878" }, msgCount))));
};
