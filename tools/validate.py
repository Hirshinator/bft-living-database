#!/usr/bin/env python3
"""REAL syntax validation for the BFT database -- replaces brace-counting.

macOS ships a JavaScriptCore binary. It can parse the app's <script> block for
real, which brace/bracket counting cannot: on 15 Jul 2026 the balance check
passed while the deployed app was actually broken by TWO syntax errors that had
shipped to production (a mangled escaped quote, and `related=` for `related:`).

Usage: python3 tools/validate.py [path-to-html]
Exit 0 = parses. Non-zero = does not.
"""
import re, sys, json, subprocess, os

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
PATH = sys.argv[1] if len(sys.argv) > 1 else "/Users/andy/Downloads/BFT_Living_Database_6.html"
TMP = "/tmp/_bft_validate"
os.makedirs(TMP, exist_ok=True)

def scan_rows(s, start, end):
    """Yield top-level {...} object spans inside SEED_DATA, honouring strings,
    escapes and comments -- the things a naive regex/counter gets wrong."""
    i, depth, obj_start, state = start, 0, None, None
    while i < end:
        c = s[i]
        if state is None:
            if c in '"\'`': state = c
            elif c == '/' and s[i+1:i+2] == '/': state = '//'
            elif c == '/' and s[i+1:i+2] == '*': state = '/*'
            elif c == '{':
                if depth == 0: obj_start = i
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0 and obj_start is not None:
                    yield (obj_start, i+1); obj_start = None
        elif state in '"\'`':
            if c == '\\': i += 2; continue
            if c == state: state = None
        elif state == '//':
            if c == '\n': state = None
        elif state == '/*':
            if c == '*' and s[i+1:i+2] == '/': state = None; i += 2; continue
        i += 1

def main():
    src = open(PATH, encoding="utf-8").read()
    s = re.search(r'<script>\n(.*?)\n</script>', src, re.S).group(1)
    open(f"{TMP}/app.js", "w", encoding="utf-8").write(s)

    r = subprocess.run([JSC, "-e",
        f'try {{ new Function(read("{TMP}/app.js")); print("OK"); }} catch (e) {{ print("ERR: " + e); }}'],
        capture_output=True, text=True)
    verdict = r.stdout.strip()
    if verdict == "OK":
        print(f"SYNTAX OK -- {len(s):,} chars parsed by JavaScriptCore")
        return check_data(s)

    print(f"{verdict}\n\nLocating the offending row(s)...")
    a = s.index("{", s.find("const SEED_DATA")) + 1   # step INSIDE the outer object
    b = s.find("\n  };", a) + 4                        # and past its closing brace
    rows = [(st, en, s[st:en]) for st, en in scan_rows(s, a, b)]
    json.dump([r[2] for r in rows], open(f"{TMP}/rows.json", "w"))
    check = f'''
var rows = JSON.parse(read("{TMP}/rows.json"));
var bad = [];
for (var i = 0; i < rows.length; i++) {{
  try {{ new Function("return " + rows[i]); }}
  catch (e) {{ bad.push(i + "\\t" + String(e) + "\\t" + rows[i].slice(0, 90)); }}
}}
print(bad.length ? bad.join("\\n") : "ALL_ROWS_OK");
print("---checked " + rows.length);
'''
    open(f"{TMP}/check.js", "w").write(check)
    out = subprocess.run([JSC, f"{TMP}/check.js"], capture_output=True, text=True).stdout
    print(out.strip())
    if "ALL_ROWS_OK" in out:
        print("\n(rows are individually fine -- the error is in app logic, not data)")
    return 1


def check_data(script):
    """Data-integrity checks a syntax parse cannot catch.

    Added after real bugs that PARSED FINE but were wrong: the Nurture category
    rendered empty for weeks (its data sat in FIELD_DEFS, not SEED_DATA), and
    duplicate records silently split the network graph's edges across two nodes
    so an edit to one missed the other.
    """
    import json as _json
    a = script.find("const SEED_DATA"); b = script.find("\n  };", a) + 4
    open(f"{TMP}/seed.js", "w", encoding="utf-8").write(
        script[a:b].replace("const SEED_DATA", "var SEED_DATA", 1) + "\nprint(JSON.stringify(SEED_DATA));")
    out = subprocess.run([JSC, f"{TMP}/seed.js"], capture_output=True, text=True).stdout
    if not out.strip():
        print("  WARN: could not evaluate SEED_DATA for data checks"); return 0
    data = _json.loads(out)
    problems = []

    # 1. every visible category must actually have data (the Nurture bug)
    m = re.search(r"const VISIBLE_CATEGORIES = \[(.*?)\];", script, re.S)
    if m:
        for cat in [x.strip().strip('"') for x in m.group(1).split(",") if x.strip()]:
            if cat not in data:
                problems.append(f"VISIBLE_CATEGORIES lists '{cat}' but SEED_DATA has no such array -> its tab renders EMPTY")

    # 2. duplicate names within a category
    for cat, rows in data.items():
        if cat.startswith("network_") or not isinstance(rows, list): continue
        seen = {}
        for r in rows:
            n = (r or {}).get("name")
            if not n: continue
            seen[n] = seen.get(n, 0) + 1
        for n, c in seen.items():
            if c > 1:
                problems.append(f"duplicate name in {cat}: '{n}' x{c}")

    # 3. duplicate bftIds anywhere (the join key must be unique)
    ids = {}
    for cat, rows in data.items():
        if cat.startswith("network_") or not isinstance(rows, list): continue
        for r in rows:
            i = (r or {}).get("bftId")
            if i: ids[i] = ids.get(i, 0) + 1
    for i, c in ids.items():
        if c > 1:
            problems.append(f"duplicate bftId '{i}' x{c} -- breaks the Sheets/Airtable join key")

    if problems:
        print(f"  DATA WARNINGS ({len(problems)}):")
        for p in problems[:20]: print("   -", p)
    else:
        print("  data checks OK (no empty visible tabs, no duplicate names or bftIds)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
