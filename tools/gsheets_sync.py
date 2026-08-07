#!/usr/bin/env python3
"""Live sync: push the complete SEED_DATA into a Google Sheet (Airtable replacement).

One worksheet (tab) per category, full-replace each run so the Sheet stays in
lockstep with the master file. Lossless + self-verifying.

Setup (reads from ~/.bft_secrets):
    GOOGLE_SA_KEY_PATH=/Users/andy/Downloads/bft-service-account.json   # the JSON key file
    GOOGLE_SHEET_ID=<the Sheet ID or full URL>
The service-account email (client_email in the JSON) must be shared as Editor on the Sheet.

Usage: python3 tools/gsheets_sync.py
"""
import re, os, json, subprocess, sys
import gspread
from google.oauth2.service_account import Credentials

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
# Data source: local master by default; in CI set BFT_HTML_PATH=index.html (the deployed build).
HTML = os.environ.get("BFT_HTML_PATH", "/Users/andy/Downloads/BFT_Living_Database_6.html")
CELL_MAX = 45000
PREF = ["name", "bftId", "stance", "allianceScore", "needsVerification", "verifiedBy", "addedBy", "affiliation",
        "audience", "audienceSize", "industry", "profession", "expertise", "platform", "links", "sourceUrl", "website",
        "related", "leader", "office", "party", "level", "type", "sector", "nurtureType", "religion", "nationality", "ideology", "network",
        "date", "status", "venue", "organizer", "attendees", "persons", "sentiment", "verified",
        "evidence", "researchNotes", "audienceDemographics", "source", "photo", "logo"]

def secret(k, required=True):
    v = os.environ.get(k)                       # env first (CI / GitHub Actions secrets)
    if v: return v.strip()
    path = os.path.expanduser("~/.bft_secrets")  # then the local secrets file
    if os.path.exists(path):
        for l in open(path):
            if l.startswith(k + "="):
                return l.split("=", 1)[1].strip()
    if required: sys.exit(f"{k} not set (env var or ~/.bft_secrets).")
    return None

def load():
    s = re.search(r"<script>\n(.*?)\n</script>", open(HTML, encoding="utf-8").read(), re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    js = s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1)
    if os.path.exists(JSC):                       # macOS: JavaScriptCore
        open("/tmp/_gs.js", "w").write(js + "\nprint(JSON.stringify(SEED_DATA));")
        out = subprocess.run([JSC, "/tmp/_gs.js"], capture_output=True, text=True).stdout
    else:                                          # Linux/CI: Node (preinstalled on GitHub runners)
        open("/tmp/_gs.js", "w").write(js + "\nprocess.stdout.write(JSON.stringify(SEED_DATA));")
        out = subprocess.run(["node", "/tmp/_gs.js"], capture_output=True, text=True).stdout
    return json.loads(out)

def cellval(v):
    if v is None: return ""
    if isinstance(v, list): v = "; ".join(str(x) for x in v)
    v = str(v)
    return v[:CELL_MAX - 20] + "…[TRUNCATED]" if len(v) > CELL_MAX else v

def main():
    sid = secret("GOOGLE_SHEET_ID")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    key_json = secret("GOOGLE_SA_KEY_JSON", required=False)   # CI: raw JSON in a secret
    if key_json:
        creds = Credentials.from_service_account_info(json.loads(key_json), scopes=scopes)
    else:                                                       # local: path to the key file
        creds = Credentials.from_service_account_file(secret("GOOGLE_SA_KEY_PATH"), scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(sid) if sid.startswith("http") else gc.open_by_key(sid)
    d = load()
    total = sum(len(v) for v in d.values())
    if total < 100:   # safety: never overwrite the Sheet with an empty/broken parse
        sys.exit(f"Refusing to sync: only {total} records parsed — looks empty/broken. Sheet left untouched.")
    print(f"Loaded {total} records from {HTML}")
    ok = True
    for cat, rows in d.items():
        keys = ([k for k in PREF if any(k in r for r in rows)] + sorted({k for r in rows for k in r} - set(PREF))) if rows else ["(empty)"]
        values = [keys] + [[cellval(r.get(k, "")) for k in keys] for r in rows]
        try: ws = sh.worksheet(cat[:31])
        except gspread.WorksheetNotFound: ws = sh.add_worksheet(title=cat[:31], rows=len(values) + 5, cols=len(keys) + 2)
        ws.clear()
        ws.resize(rows=max(len(values), 1), cols=max(len(keys), 1))
        ws.update(values, "A1", value_input_option="RAW")
        wrote = ws.row_count - 1
        mark = "OK" if wrote >= len(rows) else "CHECK"
        if wrote < len(rows): ok = False
        print(f"  {cat:22} {len(rows):5} rows -> {mark}")
    print("SYNC COMPLETE." if ok else "SYNC finished with row-count warnings — re-check.")
    print("Sheet:", sh.url)

if __name__ == "__main__":
    main()
