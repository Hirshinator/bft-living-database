#!/usr/bin/env python3
"""One-time direct populate of the Airtable base from SEED_DATA.

Why direct (not via the app): writing ~839 records through Vercel's /api/data
would exceed the serverless function timeout (Airtable's 5 req/s cap means
~20s of paced writes). Calling Airtable straight from here has no such limit.

Mirrors exactly what the app's writeAll sends: each record's non-empty fields
stringified, plus the runtime `id`. Idempotent-ish: skips a table that already
has rows so re-runs don't duplicate.

Usage: python3 tools/airtable_populate.py <baseId>
"""
import os, re, sys, json, time, uuid, subprocess, urllib.request, urllib.error

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
HTML = "/Users/andy/Downloads/BFT_Living_Database_6.html"
TABLES = ["influencer", "business_leader", "grassroots_business", "grassroots_politics", "organization", "business", "ecosystem",
          "political", "sponsor", "israeli_tech", "nurture", "rising_stars", "swing", "criteria", "backlog"]


def tok():
    return next(l.split("=", 1)[1].strip() for l in open(os.path.expanduser("~/.bft_secrets"))
               if l.startswith("AIRTABLE_TOKEN="))


def call(method, path, payload=None):
    req = urllib.request.Request(f"https://api.airtable.com/v0/{path}", method=method,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"Bearer {tok()}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(30); continue
            raise SystemExit(f"Airtable {e.code} {method} {path}: {e.read().decode()[:300]}")


def load_seed():
    s = re.search(r"<script>\n(.*?)\n</script>", open(HTML, encoding="utf-8").read(), re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    open("/tmp/_pop.js", "w").write(
        s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1) + "\nprint(JSON.stringify(SEED_DATA));")
    return json.loads(subprocess.run([JSC, "/tmp/_pop.js"], capture_output=True, text=True).stdout)


def clean(rec):
    out = {}
    for k, v in rec.items():
        if v in (None, "", "undefined"):
            continue
        out[k] = v if isinstance(v, str) else str(v)
    out["id"] = "u" + uuid.uuid4().hex[:12]
    return out


def main():
    base = sys.argv[1].strip()
    data = load_seed()
    grand = 0
    for t in TABLES:
        # skip if already populated
        existing = call("GET", f"{base}/{t}?maxRecords=1")
        if existing.get("records"):
            print(f"  {t:<16s} already has rows, skipping")
            continue
        rows = data.get(t, [])
        made = 0
        for i in range(0, len(rows), 10):
            batch = [{"fields": clean(r)} for r in rows[i:i+10]]
            res = call("POST", f"{base}/{t}", {"records": batch, "typecast": True})
            made += len(res["records"])
            time.sleep(0.22)   # ~4.5 req/s, under Airtable's 5/s
        print(f"  {t:<16s} +{made}")
        grand += made
    print(f"\nDONE: {grand} records created in base {base}")


if __name__ == "__main__":
    main()
