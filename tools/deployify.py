#!/usr/bin/env python3
"""Sync the local BFT database file into this repo's deployable index.html.

Copies the standalone file (localStorage version) and re-applies the
deployment-only changes: passcode gate UI, shared /api/data storage,
gate bootstrap, and shared-collaboration copy.

Usage: python3 tools/deployify.py [path-to-local-html]
"""
import sys, os, re

SRC = sys.argv[1] if len(sys.argv) > 1 else "/Users/andy/Downloads/BFT_Living_Database_6.html"
DST = os.path.join(os.path.dirname(__file__), "..", "index.html")

text = open(SRC, encoding="utf-8").read()
applied = []

def rep(old, new, label):
    global text
    n = text.count(old)
    assert n == 1, f"FAIL [{label}]: expected 1 occurrence, found {n}"
    text = text.replace(old, new)
    applied.append(label)

# 1. Gate CSS + overlay markup + hidden app
rep('''    .stance-map-wrap, .network-wrap { flex-direction: column; }
    .view-controls { width: 100%; flex: none; }
  }
</style>

<div class="app" id="app">''',
'''    .stance-map-wrap, .network-wrap { flex-direction: column; }
    .view-controls { width: 100%; flex: none; }
  }

  .gate-overlay {
    position: fixed; inset: 0; background: var(--navy-dark); display: flex;
    align-items: center; justify-content: center; z-index: 2000;
  }
  .gate-box { background: white; border-radius: 12px; padding: 32px; width: 100%; max-width: 340px; text-align: center; }
  .gate-box .eyebrow { font-size: 10px; letter-spacing: 0.12em; color: var(--gold); font-weight: 700; text-transform: uppercase; margin-bottom: 6px; }
  .gate-box h2 { font-family: Georgia, serif; color: var(--navy); margin: 0 0 16px; font-size: 18px; }
  .gate-box input { width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 7px; font-size: 14px; text-align: center; letter-spacing: 0.1em; }
  .gate-box button { width: 100%; margin-top: 12px; padding: 10px; }
  .gate-error { color: var(--red); font-size: 12px; margin-top: 10px; min-height: 14px; }
  .gate-hidden { display: none !important; }
</style>

<div class="gate-overlay" id="gateOverlay">
  <div class="gate-box">
    <div class="eyebrow">Builders for Tomorrow</div>
    <h2>Living Intelligence Database</h2>
    <input type="password" id="gatePasscode" placeholder="Enter access passcode" autocomplete="off">
    <button class="btn btn-primary" id="gateSubmit">Unlock</button>
    <div class="gate-error" id="gateError"></div>
  </div>
</div>

<div class="app" id="app" style="display:none">''', "gate CSS + markup")

# 2. Storage adapter -> shared API + gate logic (incl. server-error/wrong-passcode distinction)
rep('''  const storage = (window.storage && typeof window.storage.get === "function")
    ? window.storage
    : {
        async get(key) { const v = localStorage.getItem(key); return v ? { value: v } : null; },
        async set(key, value) { localStorage.setItem(key, value); },
      };''',
'''  // Shared backend storage: everyone with the passcode reads/writes the same
  // data via /api/data (see api/data.js). No offline/local fallback here --
  // this deployment is meant to be shared, so a failed request should surface
  // as a visible error rather than silently diverging into a local-only copy.
  let PASSCODE = null;

  const storage = {
    async get(key) {
      const res = await fetch("/api/data", { headers: { "x-passcode": PASSCODE } });
      if (res.status === 401) throw new Error("UNAUTHORIZED");
      if (!res.ok) throw new Error("Failed to load data (" + res.status + ")");
      const json = await res.json();
      return json.value ? { value: json.value } : null;
    },
    async set(key, value) {
      const res = await fetch("/api/data", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-passcode": PASSCODE },
        body: JSON.stringify({ value }),
      });
      if (!res.ok) throw new Error("Failed to save data (" + res.status + ")");
    },
  };

  async function checkPasscode(code) {
    const res = await fetch("/api/data", { headers: { "x-passcode": code } });
    if (res.status === 500) {
      const body = await res.json().catch(() => ({}));
      return { ok: false, serverError: body.error || "Server is not configured yet." };
    }
    return { ok: res.status !== 401 };
  }

  function showGate(errorMsg) {
    document.getElementById("gateOverlay").classList.remove("gate-hidden");
    document.getElementById("gateError").textContent = errorMsg || "";
    const input = document.getElementById("gatePasscode");
    input.value = "";
    input.focus();
  }

  function hideGate() {
    document.getElementById("gateOverlay").classList.add("gate-hidden");
    document.getElementById("app").style.display = "";
  }

  async function attemptUnlock(code) {
    if (!code) { showGate("Enter a passcode."); return; }
    document.getElementById("gateSubmit").disabled = true;
    document.getElementById("gateError").textContent = "Checking...";
    const result = await checkPasscode(code).catch((e) => ({ ok: false, serverError: "Could not reach the server: " + e.message }));
    document.getElementById("gateSubmit").disabled = false;
    if (result.ok) {
      PASSCODE = code;
      localStorage.setItem("bft_passcode", code);
      hideGate();
      loadData().then(renderAll);
    } else if (result.serverError) {
      showGate("Setup issue, not a wrong passcode: " + result.serverError);
    } else {
      showGate("Incorrect passcode.");
    }
  }

  function initGate() {
    document.getElementById("gateSubmit").addEventListener("click", () => attemptUnlock(document.getElementById("gatePasscode").value.trim()));
    document.getElementById("gatePasscode").addEventListener("keydown", (e) => { if (e.key === "Enter") attemptUnlock(e.target.value.trim()); });
    const remembered = localStorage.getItem("bft_passcode");
    if (remembered) attemptUnlock(remembered);
    else showGate();
  }''', "storage adapter + gate logic")

# 3. Bootstrap via gate
rep('''  document.getElementById("exportBtn").addEventListener("click", exportCSV);

  loadData().then(renderAll);
})();''',
'''  document.getElementById("exportBtn").addEventListener("click", exportCSV);

  initGate();
})();''', "initGate bootstrap")

# 4. Shared-collaboration copy
rep('&#9998; Auto-saves in this browser. If opened in an environment with shared storage, changes may be visible to others who open it there.',
    '&#9998; Shared/collaborative: anyone with the passcode can view and edit. All changes are visible to everyone who opens it.',
    "header copy")
rep('Data auto-saves in this browser &middot;', 'Data persists automatically across sessions &middot;', "footer copy")

# sanity: script braces balance
m = re.search(r'<script>\n(.*?)\n</script>', text, re.S)
s = m.group(1)
assert s.count("{") == s.count("}"), "brace mismatch after deployify"
assert s.count("`") % 2 == 0, "backtick mismatch after deployify"

open(DST, "w", encoding="utf-8").write(text)
print(f"deployify OK ({len(applied)} transforms): " + ", ".join(applied))
