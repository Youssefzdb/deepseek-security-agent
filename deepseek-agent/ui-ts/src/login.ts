/**
 * login.ts — Multi-provider login screen.
 * Supports: OpenRouter, OpenCode Zen, DeepSeek API, Groq, DeepSeek Chat (PoW)
 */

type Provider = {
  id:          string;
  label:       string;
  keyLabel:    string;
  keyHint:     string;
  keyLink:     string;
  needsEmail:  boolean;
  freeModels?: string[];
  paidModels?: string[];
};

const PROVIDERS: Provider[] = [
  {
    id:        "openrouter",
    label:     "OpenRouter",
    keyLabel:  "API KEY",
    keyHint:   "sk-or-...",
    keyLink:   "https://openrouter.ai/keys",
    needsEmail: false,
    freeModels: [
      "qwen/qwen3-coder:free",
      "openai/gpt-oss-120b:free",
      "moonshotai/kimi-k2.6:free",
      "nvidia/nemotron-3-ultra-550b-a55b:free",
      "meta-llama/llama-3.3-70b-instruct:free",
      "google/gemma-4-31b-it:free",
      "openrouter/free",
    ],
  },
  {
    id:        "opencode",
    label:     "OpenCode Zen",
    keyLabel:  "API KEY",
    keyHint:   "sk-...",
    keyLink:   "https://opencode.ai",
    needsEmail: false,
    freeModels: [
      "deepseek-v4-flash-free",
      "mimo-v2.5-free",
      "qwen3.6-plus-free",
      "minimax-m3-free",
      "nemotron-3-super-free",
    ],
    paidModels: ["big-pickle", "deepseek-v4-flash", "gemini-3-flash"],
  },
  {
    id:        "deepseek_api",
    label:     "DeepSeek API",
    keyLabel:  "API KEY",
    keyHint:   "sk-...",
    keyLink:   "https://platform.deepseek.com/api_keys",
    needsEmail: false,
    paidModels: ["deepseek-coder", "deepseek-chat", "deepseek-reasoner"],
  },
  {
    id:        "groq",
    label:     "Groq (Free Tier)",
    keyLabel:  "API KEY",
    keyHint:   "gsk_...",
    keyLink:   "https://console.groq.com/keys",
    needsEmail: false,
    freeModels: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen-qwq-32b"],
  },
  {
    id:        "deepseek_chat",
    label:     "DeepSeek Chat (Free PoW)",
    keyLabel:  "PASSWORD",
    keyHint:   "your deepseek.com password",
    keyLink:   "https://chat.deepseek.com",
    needsEmail: true,
    freeModels: ["deepseek-coder", "deepseek-chat"],
  },
];

// ── Tiny CSS-only 3D mask animation ──────────────────────────────────────────
const MASK_FRAMES = [
  `   .----.
  /      \\
 |  O  O  |
 |   __   |
  \\______/`,
  `  .------.
 /        \\
|  @    @  |
|   ____   |
 \\________/`,
  ` .---------,
/           \\
|  ◉     ◉  |
|    ____    |
 \\__________/`,
  `  .--------.
 /    3D     \\
|  ●       ●  |
|    (__)    |
 \\__________/`,
  ` .---------,
/           \\
|  ◉     ◉  |
|   ____    |
 \\__________/`,
];

export function showLogin(
  onSuccess: (creds: Record<string, string>) => void
): void {
  let selectedProvider = PROVIDERS[0];
  let frameIdx = 0;

  // ── Overlay ───────────────────────────────────────────────────────────────
  const overlay = document.createElement("div");
  overlay.id = "login-overlay";
  overlay.style.cssText = `
    position:fixed; inset:0; z-index:9999;
    background:#000;
    display:flex; align-items:center; justify-content:center;
    font-family:'Cascadia Code','Fira Code','JetBrains Mono',monospace;
  `;

  overlay.innerHTML = `
    <div id="lbox" style="
      width:420px;
      border:1px solid #1e1e1e;
      border-radius:10px;
      background:#0a0a0a;
      padding:36px 32px 28px;
      display:flex; flex-direction:column; gap:0;
    ">
      <!-- Mask canvas placeholder (Three.js mounts here) -->
      <div id="login-mask-wrap" style="
        width:100%; display:flex; align-items:center; justify-content:center;
        margin-bottom:20px; min-height:100px;
      ">
        <canvas id="login-mask-canvas" width="180" height="100"
          style="border-radius:8px;"></canvas>
      </div>

      <!-- Title -->
      <div style="text-align:center; margin-bottom:20px;">
        <div style="font-size:15px; color:#c8aa50; letter-spacing:3px; text-transform:uppercase; font-weight:600;">
          DeepSeek Agent
        </div>
        <div style="font-size:10px; color:#444; margin-top:5px; letter-spacing:1px;">
          SECURITY TERMINAL v2.0
        </div>
      </div>

      <!-- Provider selector -->
      <div style="margin-bottom:16px;">
        <label style="font-size:10px; color:#585858; display:block; margin-bottom:6px; letter-spacing:1px;">
          PROVIDER
        </label>
        <select id="l-provider" style="
          width:100%; background:#060606; border:1px solid #222;
          border-radius:5px; padding:9px 10px; color:#c8c8b8;
          font-family:inherit; font-size:12px; outline:none;
          box-sizing:border-box; cursor:pointer; appearance:none;
        ">
          ${PROVIDERS.map(p => `<option value="${p.id}">${p.label}</option>`).join("")}
        </select>
      </div>

      <!-- Model selector -->
      <div style="margin-bottom:16px;">
        <label style="font-size:10px; color:#585858; display:block; margin-bottom:6px; letter-spacing:1px;">
          MODEL
        </label>
        <select id="l-model" style="
          width:100%; background:#060606; border:1px solid #222;
          border-radius:5px; padding:9px 10px; color:#c8c8b8;
          font-family:inherit; font-size:12px; outline:none;
          box-sizing:border-box; cursor:pointer; appearance:none;
        "></select>
        <div id="l-model-hint" style="font-size:10px; color:#2a6; margin-top:4px;">
          ✓ Free tier available
        </div>
      </div>

      <!-- Email (shown only for deepseek_chat) -->
      <div id="l-email-row" style="margin-bottom:14px; display:none;">
        <label style="font-size:10px; color:#585858; display:block; margin-bottom:6px; letter-spacing:1px;">
          EMAIL
        </label>
        <input id="l-email" type="email" autocomplete="username"
          style="
            width:100%; background:#060606; border:1px solid #222;
            border-radius:5px; padding:9px 12px; color:#c8c8b8;
            font-family:inherit; font-size:12px; outline:none;
            box-sizing:border-box; caret-color:#c8aa50;
          "
          placeholder="user@example.com"
        />
      </div>

      <!-- API Key / Password -->
      <div id="l-key-row" style="margin-bottom:20px;">
        <label id="l-key-label" style="font-size:10px; color:#585858; display:block; margin-bottom:6px; letter-spacing:1px;">
          API KEY
        </label>
        <div style="position:relative;">
          <input id="l-key" type="password" autocomplete="current-password"
            style="
              width:100%; background:#060606; border:1px solid #222;
              border-radius:5px; padding:9px 36px 9px 12px; color:#c8c8b8;
              font-family:inherit; font-size:12px; outline:none;
              box-sizing:border-box; caret-color:#c8aa50;
            "
            placeholder="sk-..."
          />
          <button id="l-eye" style="
            position:absolute; right:10px; top:50%; transform:translateY(-50%);
            background:none; border:none; color:#444; cursor:pointer; font-size:13px;
            padding:0; line-height:1;
          ">👁</button>
        </div>
        <div id="l-key-link" style="font-size:10px; color:#444; margin-top:4px; text-align:right;">
          <a id="l-get-key" href="#" style="color:#555; text-decoration:none;">
            Get API key →
          </a>
        </div>
      </div>

      <!-- Skip key (for providers with optional key) -->
      <div id="l-skip-row" style="margin-bottom:16px; display:none; text-align:center;">
        <button id="l-skip" style="
          background:none; border:1px solid #1e1e1e; border-radius:5px;
          color:#555; font-family:inherit; font-size:11px; padding:6px 14px;
          cursor:pointer;
        ">Continue without API key (limited)</button>
      </div>

      <!-- Submit -->
      <button id="l-submit" style="
        width:100%; background:#c8aa50; border:none; border-radius:6px;
        color:#000; font-family:inherit; font-size:13px; font-weight:700;
        padding:11px; cursor:pointer; letter-spacing:1px; text-transform:uppercase;
        transition:opacity 0.15s;
      ">
        Connect
      </button>

      <!-- Error -->
      <div id="l-err" style="
        margin-top:12px; font-size:11px; color:#c0392b; text-align:center;
        min-height:16px; display:none;
      "></div>

      <!-- Version -->
      <div style="text-align:center; margin-top:18px; font-size:10px; color:#2a2a2a;">
        deepseek-security-agent · github.com/Youssefzdb
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const provSel   = document.getElementById("l-provider") as HTMLSelectElement;
  const modelSel  = document.getElementById("l-model")    as HTMLSelectElement;
  const modelHint = document.getElementById("l-model-hint")!;
  const emailRow  = document.getElementById("l-email-row")!;
  const emailInp  = document.getElementById("l-email")    as HTMLInputElement;
  const keyRow    = document.getElementById("l-key-row")!;
  const keyLabel  = document.getElementById("l-key-label")!;
  const keyInp    = document.getElementById("l-key")      as HTMLInputElement;
  const eyeBtn    = document.getElementById("l-eye")!;
  const getKeyA   = document.getElementById("l-get-key")  as HTMLAnchorElement;
  const skipRow   = document.getElementById("l-skip-row")!;
  const submitBtn = document.getElementById("l-submit")   as HTMLButtonElement;
  const errDiv    = document.getElementById("l-err")!;

  // ── Mini 3D mask renderer (WebGL via Three.js if available, else CSS fallback)
  initLoginMask();

  // ── Provider change ────────────────────────────────────────────────────────
  function updateProviderUI() {
    const pid = provSel.value;
    const p   = PROVIDERS.find(x => x.id === pid)!;
    selectedProvider = p;

    // Email row
    emailRow.style.display = p.needsEmail ? "block" : "none";

    // Key label + hint
    keyLabel.textContent = p.keyLabel;
    keyInp.placeholder   = p.keyHint;

    // Get-key link
    getKeyA.href = p.keyLink;
    getKeyA.textContent = `Get ${p.keyLabel.toLowerCase()} →`;

    // Models
    const allModels = [...(p.freeModels || []), ...(p.paidModels || [])];
    modelSel.innerHTML = allModels.map(m =>
      `<option value="${m}">${m}${(p.freeModels||[]).includes(m) ? " ✓ free" : ""}</option>`
    ).join("");

    // Hint
    if ((p.freeModels || []).length > 0) {
      modelHint.textContent = `✓ Free tier available (${p.freeModels!.length} models)`;
      modelHint.style.color = "#2a6";
    } else {
      modelHint.textContent = "Paid provider — API key required";
      modelHint.style.color = "#888";
    }

    // Skip button
    skipRow.style.display = "none";

    errDiv.style.display = "none";
    errDiv.textContent   = "";
  }

  provSel.addEventListener("change", updateProviderUI);
  updateProviderUI();

  // ── Eye toggle ─────────────────────────────────────────────────────────────
  eyeBtn.addEventListener("click", () => {
    const show = keyInp.type === "password";
    keyInp.type    = show ? "text" : "password";
    eyeBtn.textContent = show ? "🙈" : "👁";
  });

  // ── Input focus styling ────────────────────────────────────────────────────
  [emailInp, keyInp].forEach(inp => {
    inp.addEventListener("focus", () => inp.style.borderColor = "#c8aa50");
    inp.addEventListener("blur",  () => inp.style.borderColor = "#222");
  });

  // ── Submit ─────────────────────────────────────────────────────────────────
  function doSubmit() {
    const provider = provSel.value;
    const model    = modelSel.value;
    const key      = keyInp.value.trim();
    const email    = emailInp.value.trim();

    errDiv.style.display = "none";

    // Validate
    if (selectedProvider.needsEmail && !email) {
      showErr("Email required for this provider.");
      return;
    }
    // Key optional for some
    if (!key && !selectedProvider.freeModels?.length) {
      showErr("API key is required for this provider.");
      return;
    }

    // Loading state
    submitBtn.textContent = "Connecting…";
    submitBtn.style.opacity = "0.6";
    submitBtn.disabled = true;

    // Pass creds
    const creds: Record<string, string> = { provider, model };
    if (key)   creds.api_key  = key;
    if (email) creds.email    = email;

    // Try to verify (if agent bridge available)
    if ((window as any).agent) {
      const checkId = "__login_check__";
      const payload = JSON.stringify({ id: checkId, message: "__AUTH_CHECK__", ...creds });

      const handler = (e: { id: string; action: string; detail: string }) => {
        if (e.id !== checkId) return;
        (window as any).agent.off?.(handler);

        if (e.action === "auth_ok") {
          success(creds);
        } else {
          submitBtn.textContent = "Connect";
          submitBtn.style.opacity = "1";
          submitBtn.disabled = false;
          showErr(e.detail || "Connection failed.");
        }
      };

      (window as any).agent.on(handler);
      (window as any).agent.send(payload);

      // Timeout after 12s
      setTimeout(() => {
        (window as any).agent.off?.(handler);
        if (submitBtn.disabled) success(creds); // proceed anyway
      }, 12000);

    } else {
      // Browser dev-mode — skip auth check
      setTimeout(() => success(creds), 600);
    }
  }

  function success(creds: Record<string, string>) {
    overlay.style.transition = "opacity 0.4s";
    overlay.style.opacity    = "0";
    setTimeout(() => {
      overlay.remove();
      onSuccess(creds);
    }, 420);
  }

  function showErr(msg: string) {
    errDiv.textContent   = msg;
    errDiv.style.display = "block";
  }

  submitBtn.addEventListener("click", doSubmit);
  [emailInp, keyInp].forEach(i => i.addEventListener("keydown", e => { if (e.key === "Enter") doSubmit(); }));

  // ── Focus ──────────────────────────────────────────────────────────────────
  setTimeout(() => (selectedProvider.needsEmail ? emailInp : keyInp).focus(), 100);
}


// ── Login mask — CSS 3D spinning using canvas ─────────────────────────────────
function initLoginMask() {
  const canvas = document.getElementById("login-mask-canvas") as HTMLCanvasElement;
  if (!canvas) return;

  const ctx = canvas.getContext("2d")!;
  const W = canvas.width;
  const H = canvas.height;
  let angle = 0;

  // Guy Fawkes mask path (simplified 2D with 3D perspective skew)
  function drawMask(a: number) {
    ctx.clearRect(0, 0, W, H);

    // Perspective scale based on angle
    const scaleX = Math.abs(Math.cos(a));
    const flip   = Math.cos(a) < 0 ? -1 : 1;

    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.scale(scaleX, 1);

    // Glow
    ctx.shadowColor = "#c8aa50";
    ctx.shadowBlur  = 18;

    // Face oval
    ctx.beginPath();
    ctx.ellipse(0, 0, 52, 42, 0, 0, Math.PI * 2);
    ctx.strokeStyle = "#c8aa50";
    ctx.lineWidth   = 1.8;
    ctx.stroke();
    ctx.fillStyle   = "#0a0905";
    ctx.fill();

    // Eyes
    const eyeOffX = flip * 16;
    [-1, 1].forEach(side => {
      ctx.beginPath();
      ctx.ellipse(side * eyeOffX, -6, 10, 7, 0, 0, Math.PI * 2);
      ctx.strokeStyle = "#c8aa50";
      ctx.lineWidth   = 1.2;
      ctx.stroke();
      ctx.fillStyle   = "#000";
      ctx.fill();

      // Pupil
      ctx.beginPath();
      ctx.arc(side * eyeOffX, -6, 3, 0, Math.PI * 2);
      ctx.fillStyle = "#c8aa50";
      ctx.fill();
    });

    // Nose
    ctx.beginPath();
    ctx.moveTo(0, -2);
    ctx.lineTo(-5 * flip, 8);
    ctx.lineTo(5 * flip, 8);
    ctx.strokeStyle = "#8a6a30";
    ctx.lineWidth   = 1.2;
    ctx.stroke();

    // Mouth smile
    ctx.beginPath();
    ctx.arc(0, 20, 22, 0.15, Math.PI - 0.15);
    ctx.strokeStyle = "#c8aa50";
    ctx.lineWidth   = 1.5;
    ctx.stroke();

    // Cheek scrolls (decorative)
    [-1, 1].forEach(side => {
      ctx.beginPath();
      ctx.arc(side * 38, 10, 6, 0, Math.PI, side > 0);
      ctx.strokeStyle = "#6a4a20";
      ctx.lineWidth   = 1;
      ctx.stroke();
    });

    // Moustache
    [-1, 1].forEach(side => {
      ctx.beginPath();
      ctx.arc(side * 12 * flip, 15, 9, Math.PI + 0.3, Math.PI * 2 - 0.3);
      ctx.strokeStyle = "#c8aa50";
      ctx.lineWidth   = 1.5;
      ctx.stroke();
    });

    // Forehead accent
    ctx.beginPath();
    ctx.arc(0, -28, 12, Math.PI + 0.4, Math.PI * 2 - 0.4);
    ctx.strokeStyle = "#8a6a30";
    ctx.lineWidth   = 1;
    ctx.stroke();

    ctx.restore();
  }

  function animate() {
    angle += 0.025;
    drawMask(angle);
    requestAnimationFrame(animate);
  }

  animate();
}
