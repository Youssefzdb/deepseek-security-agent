import React, { useState, useEffect } from "react";
import { Text, Box } from "ink";

// 3D rotating Anonymous mask — 8 frames
const FRAMES = [
  [
    "   .==.",
    "  (o  o)",
    "  | __ |",
    "   \\__/ ",
  ],
  [
    "  .====.",
    " (o    o)",
    " | ____ |",
    "  \\____/ ",
  ],
  [
    " .======.",
    "(o      o)",
    "|  ____  |",
    " \\______/ ",
  ],
  [
    "  .====.",
    " (  oo  )",
    " | ____ |",
    "  \\____/ ",
  ],
  [
    "   .==.",
    "  (  o)",
    "  | _ |",
    "   \\_/ ",
  ],
  [
    "  .====.",
    " (o    )",
    " | __  |",
    "  \\__/ ",
  ],
  [
    " .======.",
    "(        )",
    "|  ____  |",
    " \\______/ ",
  ],
  [
    "  .====.",
    " (o    o)",
    " | ____ |",
    "  \\____/ ",
  ],
];

interface MaskProps {
  animate?: boolean;
  fps?: number;
}

export const Mask: React.FC<MaskProps> = ({ animate = true, fps = 8 }) => {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    if (!animate) return;
    const id = setInterval(() => {
      setFrame(f => (f + 1) % FRAMES.length);
    }, 1000 / fps);
    return () => clearInterval(id);
  }, [animate, fps]);

  const lines = FRAMES[frame];

  return (
    <Box flexDirection="column" alignItems="center">
      {lines.map((line, i) => (
        <Text key={i} color={i === 0 || i === 3 ? "yellow" : "white"} bold={i === 1}>
          {line}
        </Text>
      ))}
    </Box>
  );
};
