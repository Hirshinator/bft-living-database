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
        return 0

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

if __name__ == "__main__":
    sys.exit(main())
