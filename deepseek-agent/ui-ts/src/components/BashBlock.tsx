import React from "react";
import { Box, Text } from "ink";

interface BashBlockProps {
  cmd: string;
  n: number;
}

export const BashBlock: React.FC<BashBlockProps> = ({ cmd, n }) => {
  const lines = cmd.trim().split("\n");

  return (
    <Box flexDirection="column" marginY={1} paddingX={2}>
      {/* Header */}
      <Box>
        <Text bold color="#d4a72c">▸ bash  </Text>
        <Text color="#484838">cmd #{n}</Text>
      </Box>

      {/* Command box */}
      <Box borderStyle="single" borderColor="#d4a72c" paddingX={2} paddingY={0}>
        {lines.length === 1 ? (
          <Box>
            <Text bold color="#56c8d8">$ </Text>
            <Text color="#c8c8b8">{cmd.trim()}</Text>
          </Box>
        ) : (
          <Box flexDirection="column">
            {lines.map((line, i) => (
              <Box key={i}>
                <Text bold color="#56c8d8">{i === 0 ? "$ " : "  "}</Text>
                <Text color="#c8c8b8">{line}</Text>
              </Box>
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
};

interface OutputBlockProps {
  output: string;
  maxLines?: number;
}

export const OutputBlock: React.FC<OutputBlockProps> = ({ output, maxLines = 35 }) => {
  const allLines = output.trim().split("\n");
  const truncated = allLines.length > maxLines;
  const lines = truncated ? allLines.slice(0, maxLines) : allLines;

  return (
    <Box flexDirection="column" paddingX={2}>
      <Box borderStyle="single" borderColor="#383838" paddingX={2} paddingY={0}>
        <Box flexDirection="column">
          {/* title */}
          <Text color="#585858">output</Text>
          {lines.map((line, i) => (
            <Text key={i} color="#888878" dimColor>{line}</Text>
          ))}
          {truncated && (
            <Text color="#585858" dimColor>
              … ({allLines.length - maxLines} more lines)
            </Text>
          )}
        </Box>
      </Box>
    </Box>
  );
};
