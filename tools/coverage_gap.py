#!/usr/bin/env python3
"""Coverage-gap finder: enumerate RANKED external rosters, diff against the DB.

WHY THIS EXISTS
Until now this database grew by ACCRETION -- Andy names someone, it gets added;
occasional sweeps fill gaps. There was never a completeness BASELINE. So coverage
was a function of (a) what Andy remembered to name and (b) what Claude happened to
encounter. That structurally guarantees obvious figures go missing -- which is
exactly what happened with Dan Crenshaw, Mark Levin, Jordan Peterson and
Commentary Magazine. No amount of "being smarter" fixes a recall-based process.

THE FIX: stop relying on recall. Enumerate bounded, externally-ranked rosters and
DIFF them against the database. A gap list produced this way is mechanical --
it does not depend on anyone remembering anybody.

Apple Podcasts is the first source because its search API is free, needs no key,
and ranks by relevance across the exact categories this project cares about.
Other enumerable rosters to add: outlet mastheads, think-tank fellow lists,
award lists (IAF Top 50), radio syndication rosters, caucus membership.

Usage: python3 tools/coverage_gap.py
"""
import json, re, subprocess, urllib.request, urllib.parse, time, unicodedata

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
SRC = "/Users/andy/Downloads/BFT_Living_Database_6.html"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

QUERIES = [
    "conservative politics", "Israel", "Jewish", "Christian conservative",
    "evangelical", "antisemitism", "Middle East policy", "Zionism",
]

def deaccent(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def norm(s):
    s = deaccent(s or "").lower()
    s = re.sub(r"\b(the|show|podcast|with|and|program|radio)\b", " ", s)
    return " ".join(re.sub(r"[^a-z0-9\s]", " ", s).split())

def db_names():
    src = open(SRC, encoding="utf-8").read()
    s = re.search(r"<script>\n(.*?)\n</script>", src, re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    open("/tmp/_cov.js", "w").write(
        s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1) + "\nprint(JSON.stringify(SEED_DATA));")
    d = json.loads(subprocess.run([JSC, "/tmp/_cov.js"], capture_output=True, text=True).stdout)
    out = set()
    for cat, rows in d.items():
        if cat.startswith("network_"):
            continue
        for r in rows:
            n = norm(r.get("name", ""))
            if n:
                out.add(n)
                for tok in n.split():
                    if len(tok) > 3:
                        out.add(tok)   # surname tokens, so "levin" matches "mark levin show"
    return out

def itunes(q):
    u = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"media": "podcast", "term": q, "limit": 40, "country": "US"})
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20)).get("results", [])
    except Exception:
        return []

def main():
    known = db_names()
    seen, gaps = set(), []
    for q in QUERIES:
        for r in itunes(q):
            show = (r.get("collectionName") or "").strip()
            artist = (r.get("artistName") or "").strip()
            key = norm(show)
            if not key or key in seen:
                continue
            seen.add(key)
            hay = norm(show + " " + artist)
            toks = [t for t in hay.split() if len(t) > 3]
            if any(t in known for t in toks):
                continue                      # someone in this show's name is already tracked
            gaps.append((show, artist, r.get("trackCount") or 0, (r.get("releaseDate") or "")[:10]))
        time.sleep(0.3)
    gaps.sort(key=lambda x: -x[2])
    print(f"scanned {len(seen)} distinct shows across {len(QUERIES)} queries")
    print(f"NOT represented in the database: {len(gaps)}\n")
    for show, artist, eps, last in gaps[:45]:
        print(f"  {show[:44]:<46s} {artist[:26]:<28s} eps:{eps:<5d} {last}")
    json.dump([{"show": s, "artist": a, "episodes": e, "latest": l} for s, a, e, l in gaps],
              open("/tmp/coverage_gaps.json", "w"), indent=1)
    print(f"\n-> full list written to /tmp/coverage_gaps.json")

if __name__ == "__main__":
    main()
