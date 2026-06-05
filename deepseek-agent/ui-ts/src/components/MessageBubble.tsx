import React from "react";
import { Box, Text } from "ink";

export type Role = "user" | "assistant" | "system";

interface Props {
  role: Role;
  content: string;
}

const roleColors: Record<Role, string> = {
  user:      "#4888cc",
  assistant: "#38a860",
  system:    "#888878",
};

const roleLabels: Record<Role, string> = {
  user:      "You",
  assistant: "DeepSeek",
  system:    "System",
};

export const MessageBubble: React.FC<Props> = ({ role, content }) => {
  const color = roleColors[role];
  const label = roleLabels[role];
  const isUser = role === "user";

  return (
    <Box flexDirection="column" marginY={1} paddingX={2}>
      {/* Label */}
      <Text bold color={color}>{label}</Text>

      {/* Bubble */}
      <Box
        borderStyle="round"
        borderColor={isUser ? "#284060" : "#1c3828"}
        paddingX={2}
        paddingY={0}
      >
        <Text color="#c8c8b8" wrap="wrap">{content}</Text>
      </Box>
    </Box>
  );
};
