/**
 * mask-init.ts
 * Initializes the Three.js Anonymous mask on the left canvas.
 * Imports from mask.ts (your supplied file).
 */
import { init } from "./mask.js";

const canvas = document.getElementById("mask-canvas") as HTMLCanvasElement;
if (canvas) {
  // Resize canvas to match element size
  const resize = () => {
    const rect = canvas.getBoundingClientRect();
    canvas.width  = rect.width  * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
  };
  resize();
  window.addEventListener("resize", resize);

  init(canvas);
}
