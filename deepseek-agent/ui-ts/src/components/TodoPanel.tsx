import React from "react";
import { Box, Text } from "ink";

export interface TodoItem {
  content: string;
  status: "pending" | "in_progress" | "completed" | "cancelled";
  priority?: "high" | "medium" | "low";
}

interface TodoPanelProps {
  todos: TodoItem[];
}

const STATUS_ICON: Record<TodoItem["status"], string> = {
  pending:     "○",
  in_progress: "▶",
  completed:   "✓",
  cancelled:   "✗",
};

const STATUS_COLOR: Record<TodoItem["status"], string> = {
  pending:     "#585858",
  in_progress: "#d4a72c",
  completed:   "#38a860",
  cancelled:   "#e06c75",
};

export const TodoPanel: React.FC<TodoPanelProps> = ({ todos }) => {
  if (!todos.length) return null;

  const done  = todos.filter(t => t.status === "completed").length;
  const total = todos.length;
  const pct   = Math.round((done / total) * 100);

  // Progress bar
  const barLen   = 30;
  const filled   = Math.round((done / total) * barLen);
  const bar      = "█".repeat(filled) + "░".repeat(barLen - filled);

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor="#383838"
      paddingX={2}
      paddingY={0}
      marginX={2}
      marginY={1}
    >
      {/* Title */}
      <Box marginBottom={1}>
        <Text bold color="#d4a72c">Task Progress  </Text>
        <Text color="#38a860">{done}</Text>
        <Text color="#585858">/{total}  </Text>
        <Text color="#56c8d8">{pct}%</Text>
      </Box>

      {/* Progress bar */}
      <Box marginBottom={1}>
        <Text color="#38a860">{bar.slice(0, filled)}</Text>
        <Text color="#383838">{bar.slice(filled)}</Text>
      </Box>

      {/* Items */}
      {todos.map((t, i) => {
        const icon  = STATUS_ICON[t.status];
        const color = STATUS_COLOR[t.status];
        const dim   = t.status === "completed" || t.status === "cancelled";
        return (
          <Box key={i}>
            <Text bold color={color}>{icon} </Text>
            <Text color={dim ? "#585858" : "#c8c8b8"} dimColor={dim}>
              {t.content}
            </Text>
          </Box>
        );
      })}
    </Box>
  );
};
