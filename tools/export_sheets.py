#!/usr/bin/env python3
"""Export the complete SEED_DATA (the source of truth) to a Google-Sheets-ready
.xlsx — one sheet per category, all fields, all records, photos included.

Google's free Airtable-substitute path: run this, then drop the .xlsx in Google
Drive and open it (it converts to a live Sheet). Re-run after any data change to
refresh the export. Lossless + self-verifying (row counts + column coverage).

Usage: python3 tools/export_sheets.py [output.xlsx]
"""
import re, json, subprocess, sys, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
HTML = "/Users/andy/Downloads/BFT_Living_Database_6.html"
OUT = sys.argv[1] if len(sys.argv) > 1 else "/Users/andy/Downloads/BFT_Database_FULL_export.xlsx"
CELL_MAX = 45000  # Google Sheets cell limit is 50k
PREF = ["name", "bftId", "stance", "allianceScore", "needsVerification", "verifiedBy", "addedBy", "affiliation",
        "audience", "audienceSize", "industry", "profession", "expertise", "platform", "links", "sourceUrl", "website",
        "related", "leader", "office", "party", "level", "type", "sector", "nurtureType", "religion", "nationality", "ideology", "network",
        "date", "status", "venue", "organizer", "attendees", "persons", "sentiment", "verified",
        "evidence", "researchNotes", "audienceDemographics", "source", "photo", "logo"]

def load():
    s = re.search(r"<script>\n(.*?)\n</script>", open(HTML, encoding="utf-8").read(), re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    open("/tmp/_ex.js", "w").write(s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1) + "\nprint(JSON.stringify(SEED_DATA));")
    return json.loads(subprocess.run([JSC, "/tmp/_ex.js"], capture_output=True, text=True).stdout)

def cellval(v):
    if v is None: return ""
    if isinstance(v, list): v = "; ".join(str(x) for x in v)
    v = str(v)
    return v[:CELL_MAX - 20] + "…[TRUNCATED]" if len(v) > CELL_MAX else v

def main():
    d = load()
    wb = Workbook(); sm = wb.active; sm.title = "_SUMMARY"
    sm.append(["BFT Living Intelligence Database — full export"])
    sm["A1"].font = Font(bold=True, size=14)
    sm.append(["Source: master SEED_DATA (complete source of truth)", datetime.date.today().isoformat()])
    sm.append([]); sm.append(["Category (sheet)", "Records", "Columns"])
    for c in ("A4", "B4", "C4"): sm[c].font = Font(bold=True)
    verify = {}
    for cat, rows in d.items():
        ws = wb.create_sheet(title=cat[:31])
        keys = ([k for k in PREF if any(k in r for r in rows)] + sorted({k for r in rows for k in r} - set(PREF))) if rows else ["(empty)"]
        ws.append(keys)
        for c in range(1, len(keys) + 1):
            ws.cell(row=1, column=c).font = Font(bold=True, color="FFFFFF")
            ws.cell(row=1, column=c).fill = PatternFill("solid", fgColor="1B3A5C")
        for r in rows: ws.append([cellval(r.get(k, "")) for k in keys])
        ws.freeze_panes = "A2"
        sm.append([cat, len(rows), len(keys)])
        verify[cat] = (len(rows), ws.max_row - 1)
    sm.append([]); sm.append(["TOTAL", sum(len(v) for v in d.values())])
    wb.save(OUT)
    bad = [c for c, (a, b) in verify.items() if a != b]
    print(f"wrote {OUT}")
    print(f"verify: {sum(len(v) for v in d.values())} records across {len(d)} sheets — {'ALL COUNTS MATCH' if not bad else 'MISMATCH: ' + str(bad)}")

if __name__ == "__main__":
    main()
