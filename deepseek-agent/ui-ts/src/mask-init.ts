/**
 * mask-init.ts
 * Draws a 3D-style rotating Anonymous / Guy Fawkes mask on #mask-canvas.
 * Uses Canvas 2D + perspective math — no Three.js dependency needed.
 * Pure, lightweight, works in any context (Electron or browser).
 */

export function initHeaderMask(): void {
  const canvas = document.getElementById("mask-canvas") as HTMLCanvasElement | null;
  if (!canvas) return;

  const ctx = canvas.getContext("2d")!;
  const W   = canvas.width;
  const H   = canvas.height;

  let angle   = 0;
  let stopped = false;

  /** Draw one frame of the rotating mask */
  function drawFrame(a: number): void {
    ctx.clearRect(0, 0, W, H);

    // cos(a) gives the "perspective" scale: 1 = front, -1 = back (same as front due to symmetry)
    const scaleX = Math.cos(a);           // −1 … +1
    const absX   = Math.abs(scaleX);      // 0 … 1

    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.scale(absX || 0.01, 1);           // perspective squish

    // ── Background disc (face silhouette) ──────────────────────────────────
    const grd = ctx.createRadialGradient(0, 0, 2, 0, 4, 22);
    grd.addColorStop(0, "#181410");
    grd.addColorStop(1, "#060503");
    ctx.beginPath();
    ctx.ellipse(0, 0, 22, 24, 0, 0, Math.PI * 2);
    ctx.fillStyle = grd;
    ctx.fill();

    // Outer glow
    ctx.shadowColor = "#c8aa50";
    ctx.shadowBlur  = 8 * absX;

    // ── Face oval ──────────────────────────────────────────────────────────
    ctx.beginPath();
    ctx.ellipse(0, 0, 22, 24, 0, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(200,170,80,${0.7 + 0.3 * absX})`;
    ctx.lineWidth   = 1.2;
    ctx.stroke();

    ctx.shadowBlur = 0;

    // ── Eyes ───────────────────────────────────────────────────────────────
    const eyeY = -7;
    [-1, 1].forEach(side => {
      const ex = side * 9;

      // Eye socket shadow
      ctx.beginPath();
      ctx.ellipse(ex, eyeY, 6, 4, 0, 0, Math.PI * 2);
      ctx.fillStyle = "#000";
      ctx.fill();

      // Eye rim
      ctx.beginPath();
      ctx.ellipse(ex, eyeY, 6, 4, 0, 0, Math.PI * 2);
      ctx.strokeStyle = "#c8aa50";
      ctx.lineWidth   = 0.8;
      ctx.stroke();

      // Pupil — shifts with perspective to give depth illusion
      const pupilX = ex + side * 2 * (1 - absX);
      ctx.beginPath();
      ctx.arc(pupilX, eyeY, 2.2, 0, Math.PI * 2);
      ctx.fillStyle = "#c8aa50";
      ctx.shadowColor = "#c8aa50";
      ctx.shadowBlur  = 6 * absX;
      ctx.fill();
      ctx.shadowBlur  = 0;
    });

    // ── Nose ───────────────────────────────────────────────────────────────
    ctx.beginPath();
    ctx.moveTo(0, -2);
    ctx.lineTo(-4 * Math.sign(scaleX || 1), 5);
    ctx.lineTo( 4 * Math.sign(scaleX || 1), 5);
    ctx.strokeStyle = "#8a6a30";
    ctx.lineWidth   = 0.9;
    ctx.stroke();

    // ── Mouth (curved smile) ───────────────────────────────────────────────
    ctx.beginPath();
    ctx.arc(0, 12, 12, 0.2, Math.PI - 0.2);
    ctx.strokeStyle = `rgba(200,170,80,${0.6 + 0.4 * absX})`;
    ctx.lineWidth   = 1.1;
    ctx.stroke();

    // ── Moustache (two curls) ──────────────────────────────────────────────
    [-1, 1].forEach(side => {
      ctx.beginPath();
      ctx.arc(side * 7, 9, 5, Math.PI + 0.4, Math.PI * 2 - 0.4);
      ctx.strokeStyle = "#c8aa50";
      ctx.lineWidth   = 1;
      ctx.stroke();
    });

    // ── Forehead detail ────────────────────────────────────────────────────
    ctx.beginPath();
    ctx.arc(0, -18, 7, Math.PI + 0.6, Math.PI * 2 - 0.6);
    ctx.strokeStyle = "#6a4a18";
    ctx.lineWidth   = 0.8;
    ctx.stroke();

    // ── Cheek swirls ───────────────────────────────────────────────────────
    [-1, 1].forEach(side => {
      ctx.beginPath();
      ctx.arc(side * 18, 4, 3.5, 0, Math.PI, side < 0);
      ctx.strokeStyle = "#6a4a18";
      ctx.lineWidth   = 0.7;
      ctx.stroke();
    });

    ctx.restore();
  }

  // ── Reflection / shine overlay (static, drawn once over everything) ────────
  function drawShine(a: number): void {
    const absX = Math.abs(Math.cos(a));
    if (absX < 0.15) return;           // skip when facing edge
    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.scale(Math.abs(Math.cos(a)) || 0.01, 1);

    const shine = ctx.createLinearGradient(-22, -30, 10, 10);
    shine.addColorStop(0, `rgba(255,240,180,${0.08 * absX})`);
    shine.addColorStop(0.5, `rgba(255,240,180,0)`);
    ctx.beginPath();
    ctx.ellipse(0, 0, 22, 24, 0, 0, Math.PI * 2);
    ctx.fillStyle = shine;
    ctx.fill();

    ctx.restore();
  }

  function animate(): void {
    if (stopped) return;
    drawFrame(angle);
    drawShine(angle);
    angle += 0.018;          // ~1 full rotation per ~350 frames ≈ 6s at 60fps
    requestAnimationFrame(animate);
  }

  animate();

  // Stop animation when tab hidden (battery-friendly)
  document.addEventListener("visibilitychange", () => {
    stopped = document.hidden;
    if (!stopped) animate();
  });
}
