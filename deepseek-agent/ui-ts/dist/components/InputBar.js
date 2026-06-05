import React, { useState } from "react";
import { Box, Text, useInput } from "ink";
export const InputBar = ({ onSubmit, disabled = false, placeholder = 'Try "scan 192.168.1.1" or /help', }) => {
    const [value, setValue] = useState("");
    useInput((input, key) => {
        if (disabled)
            return;
        if (key.return) {
            const trimmed = value.trim();
            if (trimmed) {
                onSubmit(trimmed);
                setValue("");
            }
            return;
        }
        if (key.backspace || key.delete) {
            setValue(v => v.slice(0, -1));
            return;
        }
        if (!key.ctrl && !key.meta && input) {
            setValue(v => v + input);
        }
    });
    return (React.createElement(Box, { borderStyle: "round", borderColor: disabled ? "#383838" : "#56c8d8", paddingX: 2, marginX: 1, marginY: 1 },
        React.createElement(Text, { bold: true, color: disabled ? "#383838" : "#56c8d8" }, "\u276F "),
        value ? (React.createElement(Text, { color: "#c8c8b8" }, value)) : (React.createElement(Text, { color: "#484838", italic: true }, placeholder)),
        !disabled && React.createElement(Text, { color: "#c8aa50", bold: true }, "\u2588")));
};
