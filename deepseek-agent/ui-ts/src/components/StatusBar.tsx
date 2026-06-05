import React from "react";
import { Box, Text } from "ink";
import Spinner from "ink-spinner";

interface StatusBarProps {
  model: string;
  thinking: boolean;
  thinkingMsg?: string;
  msgCount: number;
}

export const StatusBar: React.FC<StatusBarProps> = ({
  model,
  thinking,
  thinkingMsg = "Thinking…",
  msgCount,
}) => {
  return (
    <Box
      borderStyle="single"
      borderColor="#282828"
      paddingX={2}
      justifyContent="space-between"
    >
      {/* Left — model */}
      <Box>
        <Text color="#585858">model: </Text>
        <Text color="#c8aa50" bold>{model}</Text>
      </Box>

      {/* Center — thinking spinner */}
      {thinking ? (
        <Box>
          <Text color="#d4a72c">
            <Spinner type="dots" />
          </Text>
          <Text color="#d4a72c" italic>  {thinkingMsg}</Text>
        </Box>
      ) : (
        <Text color="#383838">──</Text>
      )}

      {/* Right — message counter */}
      <Box>
        <Text color="#585858">msgs: </Text>
        <Text color="#888878">{msgCount}</Text>
      </Box>
    </Box>
  );
};
