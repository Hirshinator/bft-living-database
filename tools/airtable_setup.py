#!/usr/bin/env python3
"""Stand up the Airtable base schema the live app writes through to.

api/data.js is already built for Airtable: when AIRTABLE_TOKEN + AIRTABLE_BASE_ID
are set in Vercel, the app reads/writes Airtable directly (Redis becomes a short
cache). It round-trips every record field by key, so each table must already
contain every field the app might send for that category, or Airtable 422s on an
unknown field. This script creates those tables with the right columns.

It deliberately creates SCHEMA ONLY (no rows). The app populates the rows on its
first save after the env vars are set — that path is how records acquire the
Airtable record-id (_id) the sync keys on. Pre-loading rows here would collide
with that and create duplicates.

SETUP (Andy, ~3 min):
  1. Create an Airtable personal access token: https://airtable.com/create/tokens
     Scopes: data.records:read, data.records:write, schema.bases:read,
     schema.bases:write. Add access to the base you make in step 2.
  2. Create a new EMPTY base in Airtable (any workspace). Open it; the URL is
     https://airtable.com/appXXXXXXXX/... -- the appXXXXXXXX is the base id.
  3. Put the token in the secrets file (NOT in chat):
       echo 'AIRTABLE_TOKEN=patXXXX.XXXX' >> ~/.bft_secrets && chmod 600 ~/.bft_secrets
  4. Run:  python3 tools/airtable_setup.py appXXXXXXXX
  5. In Vercel -> Project -> Settings -> Environment Variables, add:
       AIRTABLE_TOKEN = (the pat)     AIRTABLE_BASE_ID = appXXXXXXXX
     Redeploy. The next time the app loads, it fills Airtable automatically.
"""
import os, re, sys, json, time, subprocess, urllib.request, urllib.error

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
HTML = "/Users/andy/Downloads/BFT_Living_Database_6.html"
API = "https://api.airtable.com/v0"

# Must match TABLES in api/data.js exactly.
TABLES = ["influencer", "organization", "business", "ecosystem", "political",
          "sponsor", "israeli_tech", "nurture", "criteria", "backlog"]
ENTITY_TABLES = {"influencer", "organization", "business", "political",
                 "sponsor", "israeli_tech", "nurture"}

LONG = {"evidence", "researchNotes", "votingRecord", "talentEvidence",
        "description", "yieldNotes", "rationale", "rule", "costPaid", "sourceNote"}
URLISH = {"sourceUrl", "website"}
NUMISH = {"allianceScore"}
# Outreach columns added to entity tables (the app ignores unknown-to-it fields
# on read as extra data; contact info entered in Airtable flows back into it).
OUTREACH = ["Email", "Phone", "Handle", "Outreach Status"]


def token():
    t = os.environ.get("AIRTABLE_TOKEN")
    if t:
        return t.strip()
    p = os.path.expanduser("~/.bft_secrets")
    if os.path.exists(p):
        for line in open(p):
            if line.strip().startswith("AIRTABLE_TOKEN="):
                return line.split("=", 1)[1].strip()
    sys.exit("No AIRTABLE_TOKEN found. See setup steps at the top of this file.")


def call(method, path, payload=None):
    req = urllib.request.Request(
        f"{API}/{path}", method=method,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:400]
        raise SystemExit(f"Airtable {e.code} on {method} {path}\n  {body}")


def load_data():
    s = re.search(r"<script>\n(.*?)\n</script>", open(HTML, encoding="utf-8").read(), re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    open("/tmp/_at.js", "w").write(
        s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1) + "\nprint(JSON.stringify(SEED_DATA));")
    return json.loads(subprocess.run([JSC, "/tmp/_at.js"], capture_output=True, text=True).stdout)


def field_def(key):
    if key in NUMISH:
        return {"name": key, "type": "number", "options": {"precision": 0}}
    if key in URLISH:
        return {"name": key, "type": "url"}
    if key in LONG:
        return {"name": key, "type": "multilineText"}
    return {"name": key, "type": "singleLineText"}


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 tools/airtable_setup.py <baseId>   (baseId looks like appXXXXXXXX)")
    base = sys.argv[1].strip()
    data = load_data()

    # existing tables (so re-runs are safe)
    schema = call("GET", f"meta/bases/{base}/tables")
    have = {t["name"] for t in schema.get("tables", [])}

    for cat in TABLES:
        if cat in have:
            print(f"  exists, skipping: {cat}")
            continue
        rows = data.get(cat, [])
        keys = []
        for r in rows:
            for k in r.keys():
                if k not in keys:
                    keys.append(k)
        if "name" in keys:
            keys.remove("name")
        # primary field first (name), then the rest, then outreach cols
        fields = [{"name": "name", "type": "singleLineText"}]
        fields += [field_def(k) for k in keys]
        if cat in ENTITY_TABLES:
            fields += [{"name": "Email", "type": "email"},
                       {"name": "Phone", "type": "phoneNumber"},
                       {"name": "Handle", "type": "singleLineText"},
                       {"name": "Outreach Status", "type": "singleLineText"}]
        call("POST", f"meta/bases/{base}/tables",
             {"name": cat, "fields": fields})
        print(f"  created table: {cat:<16s} ({len(fields)} fields)")
        time.sleep(0.3)

    print("\nSchema ready. Now set AIRTABLE_TOKEN + AIRTABLE_BASE_ID in Vercel and redeploy;")
    print("the app fills the rows on its next load. (See setup step 5.)")


if __name__ == "__main__":
    main()
