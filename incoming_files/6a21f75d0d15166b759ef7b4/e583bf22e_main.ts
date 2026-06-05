/**
 * Entry point — attaches the mask to the page canvas
 */
import { init } from "./mask.js";

const canvas = document.getElementById("canvas") as HTMLCanvasElement;
if (!canvas) throw new Error("Canvas element not found");

const cleanup = init(canvas);

// Hot-reload support (Vite / webpack HMR)
if (import.meta.hot) {
  import.meta.hot.dispose(cleanup);
}
