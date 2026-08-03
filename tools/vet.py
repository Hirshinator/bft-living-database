#!/usr/bin/env python3
"""Infiltrator vetting — public-content sentiment + hostile-cluster screen.

Complements the in-app "Vetting" view (which scores connection-overlap). This
pulls an applicant's PUBLIC IG bio + recent posts via Apify and screens the text
for (a) anti-Israel / antisemitic language and (b) mentions of names already on
our HOSTILE list. Public data only — no invasive access needed.

Usage:  python3 tools/vet.py <instagram_handle>
Reads APIFY_TOKEN from ~/.bft_secrets. Read-only (prints a risk report).
"""
import sys, os, re, json, subprocess, urllib.request

TOK = next(l.split("=", 1)[1].strip() for l in open(os.path.expanduser("~/.bft_secrets")) if l.startswith("APIFY_TOKEN="))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
HTML = "/Users/andy/Downloads/BFT_Living_Database_6.html"
HOSTILE_KW = re.compile(r"\b(free palestine|from the river|apartheid|genocide|zionis[tm]|talmud|groyper|great replacement|khazar|christ-?killer|synagogue of satan|globalist|blood libel|IDF (terroris|murder)|settler colonial|occupied palestine)\b", re.I)

def run_actor(slug, body):
    url = f"https://api.apify.com/v2/acts/{slug}/run-sync-get-dataset-items?token={TOK}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))

def hostile_names():
    s = re.search(r"<script>\n(.*?)\n</script>", open(HTML, encoding="utf-8").read(), re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    open("/tmp/_vt.js", "w").write(s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1) + "\nprint(JSON.stringify(SEED_DATA));")
    d = json.loads(subprocess.run([JSC, "/tmp/_vt.js"], capture_output=True, text=True).stdout)
    out = []
    for cat, rows in d.items():
        if cat.startswith("network"): continue
        for r in rows:
            if r.get("stance") in ("hostile", "redflag") and r.get("name") and len(r["name"]) >= 5:
                out.append(r["name"])
    return out

def main():
    h = sys.argv[1].lstrip("@") if len(sys.argv) > 1 else None
    if not h: print(__doc__); return
    items = run_actor("apify~instagram-scraper", {"directUrls": [f"https://www.instagram.com/{h}/"], "resultsType": "posts", "resultsLimit": 20})
    prof = next((x for x in items if x.get("username")), None) if items else None
    bio = (prof or {}).get("biography", "")
    texts = [bio] + [it.get("caption", "") or "" for it in items if it.get("caption")]
    blob = " ".join(texts)
    kw = sorted(set(m.group(0) for m in HOSTILE_KW.finditer(blob)))
    hostiles = hostile_names()
    mentioned = sorted({nm for nm in hostiles if re.search(r"(^|[^a-z])" + re.escape(nm.lower()) + r"([^a-z]|$)", blob.lower())})
    risk = "HIGH RISK" if (kw or mentioned) else ("UNKNOWN — no public red flags found" if not texts else "LIKELY OK — clean public content")
    print(f"=== VET: @{h} ===")
    print(f"posts/bio screened: {len(texts)}")
    print(f"RISK: {risk}")
    if kw: print(f"  anti-Israel/antisemitic language: {kw}")
    if mentioned: print(f"  favorably engages hostile-list figures: {mentioned}")
    if not (kw or mentioned): print("  (no hostile-cluster language or hostile-list name mentions in public content)")
    print("  NOTE: combine with the in-app connection-overlap score for a full picture.")

if __name__ == "__main__":
    main()
