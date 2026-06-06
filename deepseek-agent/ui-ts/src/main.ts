/**
 * main.ts — Entry point.
 * 1. Initialize the 3D rotating header mask
 * 2. Boot the terminal UI (which will show login first)
 */
import { initHeaderMask } from "./mask-init.js";
import "./ui.js";

// Mount the mask animation on the header canvas
// (ui.ts / login.ts handle their own canvas for the login screen mask)
document.addEventListener("DOMContentLoaded", () => {
  initHeaderMask();
});
