#!/usr/bin/env python3
"""Standing ally-org roster mine.

Given an org and a list of its contributor/staff/host names, diff against the
whole BFT database and report who is MISSING (i.e., an ally-org roster member we
don't yet track). Turns "Andy names an org" into a repeatable sweep of the
rosters of ally orgs we already know about (the Chelsea-Jacobson gap fix).

Usage:
  python3 tools/roster_mine.py "The Free Press" "Douglas Murray" "Matti Friedman" ...
  python3 tools/roster_mine.py "Org" --file names.txt   (one name per line)

Prints: already-curated | backend-only (promote) | MISSING (add). Read-only.
"""
import sys, re, json, subprocess, unicodedata
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
HTML = "/Users/andy/Downloads/BFT_Living_Database_6.html"
CURATED = {"influencer","business_leader","political","nurture","rising_stars","swing",
           "grassroots_politics","grassroots_business","organization","media","business",
           "israeli_tech","sponsor"}

def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]","",s).strip()

def load():
    s = re.search(r"<script>\n(.*?)\n</script>", open(HTML,encoding="utf-8").read(), re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };",a)+4
    open("/tmp/_rm.js","w").write(s[a:b].replace("const SEED_DATA","var SEED_DATA",1)+"\nprint(JSON.stringify(SEED_DATA));")
    return json.loads(subprocess.run([JSC,"/tmp/_rm.js"],capture_output=True,text=True).stdout)

def main():
    org = sys.argv[1]
    if "--file" in sys.argv:
        names = [l.strip() for l in open(sys.argv[sys.argv.index("--file")+1]) if l.strip()]
    else:
        names = [a for a in sys.argv[2:] if not a.startswith("--")]
    d = load()
    curated, backend = {}, {}
    for cat, rows in d.items():
        for r in rows:
            nm = r.get("name")
            if not nm: continue
            (curated if cat in CURATED else backend)[norm(nm)] = (nm, cat)
    print(f"=== roster mine: {org} ({len(names)} candidates) ===")
    add, promote, have = [], [], []
    for n in names:
        k = norm(n)
        if k in curated: have.append((n, curated[k][1]))
        elif k in backend: promote.append((n, backend[k][1]))
        else: add.append(n)
    print(f"\nAlready tracked ({len(have)}): " + ", ".join(f"{n} [{c}]" for n,c in have))
    print(f"\nBackend-only -> PROMOTE ({len(promote)}): " + ", ".join(f"{n}" for n,c in promote))
    print(f"\nMISSING -> ADD ({len(add)}):")
    for n in add: print(f"   - {n}")

if __name__ == "__main__":
    main()
