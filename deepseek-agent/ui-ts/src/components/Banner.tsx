import React from "react";
import { Box, Text } from "ink";
import { Mask } from "./Mask.js";

interface BannerProps {
  model: string;
  path: string;
  toolCount: number;
}

const recent = [
  { ago: "1m ago",  desc: "Updated project memory"         },
  { ago: "8m ago",  desc: "Plan-execute loop ran"           },
  { ago: "2d ago",  desc: "Refactored SSE stream parser"    },
  { ago: "1w ago",  desc: "Added PoW C-solver"              },
];

const news = [
  "/plan  — preview task steps",
  "/model — switch model",
  "/tools — list all 27 tools",
  "ctrl+c — interrupt task",
];

export const Banner: React.FC<BannerProps> = ({ model, path, toolCount }) => {
  return (
    <Box flexDirection="column" marginBottom={1}>

      {/* ── Top border ─────────────────────────────────────────────── */}
      <Box>
        <Text color="yellow">{"─".repeat(62)}</Text>
      </Box>

      {/* ── Two-column layout ──────────────────────────────────────── */}
      <Box flexDirection="row" paddingX={1} paddingY={1}>

        {/* Left — mask + meta */}
        <Box flexDirection="column" width={24} alignItems="center" marginRight={3}>
          <Text bold color="yellow">DeepSeek Agent</Text>
          <Text color="gray">v1.0</Text>
          <Box marginY={1}>
            <Mask animate={true} fps={6} />
          </Box>
          <Text color="gray">{model}</Text>
          <Text color="gray" dimColor>{path}</Text>
          <Text color="cyan">{toolCount} tools loaded</Text>
        </Box>

        {/* Divider */}
        <Box flexDirection="column" marginRight={3}>
          {Array.from({ length: 14 }).map((_, i) => (
            <Text key={i} color="gray">│</Text>
          ))}
        </Box>

        {/* Right — activity + news */}
        <Box flexDirection="column" flexGrow={1}>
          <Text bold color="#d4a72c">Recent activity</Text>
          <Box marginBottom={1} flexDirection="column">
            {recent.map((r, i) => (
              <Box key={i}>
                <Text color="gray">{r.ago.padEnd(9)}</Text>
                <Text color="#888878">{r.desc}</Text>
              </Box>
            ))}
            <Text color="gray" dimColor>... /history for more</Text>
          </Box>

          <Text bold color="#d4a72c">What{"'"}s new</Text>
          {news.map((n, i) => (
            <Text key={i} color={i === 0 ? "#90b870" : "#888878"}>{n}</Text>
          ))}
          <Text color="gray" dimColor>... /help for more</Text>
        </Box>
      </Box>

      {/* ── Bottom border ───────────────────────────────────────────── */}
      <Box>
        <Text color="yellow">{"─".repeat(62)}</Text>
      </Box>

      {/* ── Hint line ───────────────────────────────────────────────── */}
      <Box marginTop={1} paddingX={2}>
        <Text color="gray">
          Type <Text color="white" bold>/help</Text> for commands ·{" "}
          <Text color="white" bold>Ctrl+C</Text> to interrupt ·{" "}
          <Text color="white" bold>/exit</Text> to quit
        </Text>
      </Box>
    </Box>
  );
};
