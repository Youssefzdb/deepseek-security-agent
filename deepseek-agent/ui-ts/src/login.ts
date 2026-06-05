/**
 * login.ts — Login screen shown before the main terminal.
 * Reads credentials, validates them via the Python bridge, then shows the main UI.
 */

export function showLogin(onSuccess: (email: string, password: string) => void): void {
  const body = document.body;

  const overlay = document.createElement("div");
  overlay.id = "login-overlay";
  overlay.style.cssText = `
    position:fixed; inset:0; z-index:9999;
    background:#000; display:flex; align-items:center; justify-content:center;
    font-family:'Cascadia Code','Fira Code','JetBrains Mono',monospace;
  `;

  overlay.innerHTML = `
    <div style="
      width:380px; border:1px solid #1e1e1e; border-radius:10px;
      background:#0a0a0a; padding:40px 36px; display:flex; flex-direction:column; gap:0;
    ">
      <!-- Tiny rotating mask placeholder (CSS only) -->
      <div style="text-align:center; margin-bottom:28px;">
        <pre id="login-art" style="
          color:#c8aa50; font-size:11px; line-height:1.3;
          margin:0 auto; display:inline-block; text-align:left;
        "></pre>
      </div>

      <div style="text-align:center; margin-bottom:28px;">
        <div style="font-size:16px; color:#c8aa50; letter-spacing:2px; text-transform:uppercase;">
          DeepSeek Agent
        </div>
        <div style="font-size:11px; color:#585858; margin-top:4px;">
          Enter your credentials to continue
        </div>
      </div>

      <!-- Email field -->
      <div style="margin-bottom:16px;">
        <label style="font-size:11px; color:#585858; display:block; margin-bottom:6px;">
          EMAIL
        </label>
        <input id="l-email" type="email" autocomplete="username"
          style="
            width:100%; background:#060606; border:1px solid #222;
            border-radius:5px; padding:10px 12px; color:#c8c8b8;
            font-family:inherit; font-size:13px; outline:none;
            box-sizing:border-box; caret-color:#c8aa50;
          "
          placeholder="user@example.com"
        />
      </div>

      <!-- Password field -->
      <div style="margin-bottom:24px;">
        <label style="font-size:11px; color:#585858; display:block; margin-bottom:6px;">
          PASSWORD
        </label>
        <div style="position:relative;">
          <input id="l-pass" type="password" autocomplete="current-password"
            style="
              width:100%; background:#060606; border:1px solid #222;
              border-radius:5px; padding:10px 38px 10px 12px; color:#c8c8b8;
              font-family:inherit; font-size:13px; outline:none;
              box-sizing:border-box; caret-color:#c8aa50;
            "
            placeholder="••••••••"
          />
          <span id="l-eye" style="
            position:absolute; right:10px; top:50%; transform:translateY(-50%);
            cursor:pointer; color:#585858; font-size:14px; user-select:none;
          ">👁</span>
        </div>
      </div>

      <!-- Error message -->
      <div id="l-err" style="
        display:none; color:#e06c75; font-size:11px;
        margin-bottom:14px; text-align:center;
      "></div>

      <!-- Login button -->
      <button id="l-btn" style="
        background:#0d1a0d; border:1px solid #1a3a1a; border-radius:5px;
        color:#38a860; font-family:inherit; font-size:13px; font-weight:bold;
        padding:11px; cursor:pointer; letter-spacing:1px;
        transition: background .15s, border-color .15s;
      ">
        LOGIN
      </button>

      <div style="margin-top:16px; text-align:center; font-size:10px; color:#2a2a2a;">
        Credentials are used only for DeepSeek API authentication.
      </div>
    </div>
  `;

  body.appendChild(overlay);

  // ── Mini ASCII mask animation (8 frames, CSS only) ──────────────────────────
  const MINI_FRAMES = [
    `  ..........\n ,.        .,\n .:  ()  (). \n  ., /\\ ,,`,
    `  ......... \n,.         ,\n .: ()  ()..\n  ,, /\\ ,,`,
    `  ........  \n .         .\n  : ()  ()..\n  ,, /\\  ,`,
    `  ......... \n,.         ,\n .: ()  ()..\n  ,, /\\ ,,`,
    `  ..........\n ,.        .,\n .:  ()  (). \n  ., /\\ ,,`,
    `  ......... \n ,         .\n .:  () (). \n  ,, /\\ ,`,
    `  ........  \n  .        .\n  :  () ()..\n  , /\\  ,`,
    `  ......... \n ,         .\n .:  () (). \n  ,, /\\ ,`,
  ];

  const art = document.getElementById("login-art")!;
  let fi = 0;
  const anim = setInterval(() => {
    art.textContent = MINI_FRAMES[fi % MINI_FRAMES.length];
    fi++;
  }, 200);

  // ── Toggle password visibility ──────────────────────────────────────────────
  const eye  = document.getElementById("l-eye")!;
  const pass = document.getElementById("l-pass") as HTMLInputElement;
  eye.addEventListener("click", () => {
    pass.type = pass.type === "password" ? "text" : "password";
  });

  // ── Focus email on load ─────────────────────────────────────────────────────
  setTimeout(() => (document.getElementById("l-email") as HTMLInputElement).focus(), 50);

  // ── Handle submit ───────────────────────────────────────────────────────────
  const btn     = document.getElementById("l-btn")    as HTMLButtonElement;
  const email   = document.getElementById("l-email")  as HTMLInputElement;
  const errDiv  = document.getElementById("l-err")!;

  function showErr(msg: string) {
    errDiv.textContent = msg;
    errDiv.style.display = "block";
    btn.textContent = "LOGIN";
    btn.disabled = false;
    btn.style.opacity = "1";
  }

  function submit() {
    const e = email.value.trim();
    const p = pass.value;

    if (!e || !p) { showErr("Please fill in both fields."); return; }
    if (!e.includes("@")) { showErr("Enter a valid email address."); return; }

    btn.textContent  = "Connecting…";
    btn.disabled     = true;
    btn.style.opacity = "0.6";
    errDiv.style.display = "none";

    // Send a test ping to the agent bridge — if it responds, credentials are valid.
    // We pass a special "AUTH_CHECK" message; bridge.py validates and responds.
    const id = "__auth__";
    const payload = JSON.stringify({ id, message: "__AUTH_CHECK__", model: "deepseek-coder", email: e, password: p });

    if (window.agent) {
      // One-shot listener for auth response
      const handler = (ev: { id: string; action: string; detail: string }) => {
        if (ev.id !== id) return;
        if (ev.action === "auth_ok") {
          clearInterval(anim);
          overlay.style.transition = "opacity .3s";
          overlay.style.opacity = "0";
          setTimeout(() => { overlay.remove(); onSuccess(e, p); }, 300);
        } else {
          showErr(ev.detail || "Authentication failed.");
        }
      };
      window.agent.on(handler);
      window.agent.send(payload);
    } else {
      // Dev mode — skip auth
      clearInterval(anim);
      overlay.remove();
      onSuccess(e, p);
    }
  }

  btn.addEventListener("click", submit);
  [email, pass].forEach(el => {
    el.addEventListener("keydown", (ev) => { if (ev.key === "Enter") submit(); });
  });

  // Hover effect on button
  btn.addEventListener("mouseenter", () => { btn.style.background = "#112211"; btn.style.borderColor = "#2a5a2a"; });
  btn.addEventListener("mouseleave", () => { btn.style.background = "#0d1a0d"; btn.style.borderColor = "#1a3a1a"; });
}
