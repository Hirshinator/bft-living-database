#!/usr/bin/env python3
"""Export SEED_DATA to Airtable/Notion-importable CSVs.

Uses JavaScriptCore to EVALUATE the real data (not regex-scrape it), so what
gets exported is exactly what the app loads. Writes one CSV per category.

Usage: python3 tools/export_airtable.py [path-to-html] [outdir]
"""
import re, sys, os, json, csv, subprocess

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
SRC = sys.argv[1] if len(sys.argv) > 1 else "/Users/andy/Downloads/BFT_Living_Database_6.html"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/Users/andy/Desktop/Claude_Workspace/bft-living-database/export"
# LinkedIn network_* stays backend-only per the standing instruction -- never export it.
SKIP = {"network_person", "network_company", "network_connection"}

def main():
    src = open(SRC, encoding="utf-8").read()
    s = re.search(r"<script>\n(.*?)\n</script>", src, re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    open("/tmp/_seed_export.js", "w", encoding="utf-8").write(
        s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1)
        + '\nprint(JSON.stringify(SEED_DATA));\n')
    r = subprocess.run([JSC, "/tmp/_seed_export.js"], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        print("FAILED to evaluate SEED_DATA:", r.stderr[:400]); return 1
    data = json.loads(r.stdout)

    os.makedirs(OUT, exist_ok=True)
    total = 0
    for cat, rows in data.items():
        if cat in SKIP or not rows:
            continue
        cols = []
        for row in rows:
            for k in row:
                if k not in cols: cols.append(k)
        path = os.path.join(OUT, f"{cat}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for row in rows: w.writerow(row)
        total += len(rows)
        print(f"  {cat:<14s} {len(rows):>4d} rows x {len(cols):>2d} cols -> {path}")
    print(f"\n{total} records exported to {OUT}")
    print("LinkedIn network_* intentionally excluded (backend-only per instruction).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
