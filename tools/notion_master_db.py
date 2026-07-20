#!/usr/bin/env python3
"""Create ONE master Notion database of all BFT entities (people/orgs/companies)
and load every record into it, fully via the API.

Why a single master table (not 9 per-category tables): collaborators need to
answer "is this person already on the list?" in one search box, sort the whole
field by follower count, and work an outreach column across categories. Notion
"views" (filtered by Category) give the per-category slices on top of it.

Outreach-ready by structure: Email / Phone / Handle / Outreach Status columns
are created empty so the team can start working the list immediately.

Excludes the `criteria` and `backlog` categories -- those are meta (rules /
to-do) and already live as narrative pages, not outreach entities.

Usage:
    python3 tools/notion_master_db.py <parent_page_id> [--limit N]
Reads NOTION_TOKEN from ~/.bft_secrets or env (see notion_import.py).
"""
import os, re, sys, json, time, subprocess, importlib.util

HERE = os.path.dirname(__file__)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
HTML = "/Users/andy/Downloads/BFT_Living_Database_6.html"
spec = importlib.util.spec_from_file_location("ni", os.path.join(HERE, "notion_import.py"))
ni = importlib.util.module_from_spec(spec); spec.loader.exec_module(ni)

SKIP_CATS = {"criteria", "backlog"}
CAT_LABEL = {"influencer": "Influencer", "business_leader": "Business Leader",
             "organization": "Organization", "business": "Business",
             "ecosystem": "Regional Ecosystem", "political": "Political",
             "sponsor": "Sponsor", "israeli_tech": "Israeli Tech", "nurture": "Nurture"}


def load_data():
    s = re.search(r"<script>\n(.*?)\n</script>", open(HTML, encoding="utf-8").read(), re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    open("/tmp/_master.js", "w").write(
        s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1) + "\nprint(JSON.stringify(SEED_DATA));")
    return json.loads(subprocess.run([JSC, "/tmp/_master.js"], capture_output=True, text=True).stdout)


def txt(v, cap=2000):
    v = "" if v is None else str(v)
    return [{"type": "text", "text": {"content": v[:cap]}}] if v.strip() else []


def as_url(v):
    v = (v or "").strip().split()[0] if v else ""      # first token if several
    if not v:
        return None
    if not v.startswith(("http://", "https://")):
        if "." in v and " " not in v:
            v = "https://" + v
        else:
            return None
    return v


def sel(v):
    v = (v or "").strip().replace(",", ";")            # Notion select can't contain commas
    return {"name": v[:100]} if v else None


# property name -> (notion type, builder from raw string)
SCHEMA = {
    "Name":              ("title",),
    "Category":          ("select",),
    "Stance":            ("select",),
    "Alliance Score":    ("number",),
    "Network":           ("rich_text",),
    "Platform":          ("rich_text",),
    "Audience":          ("rich_text",),
    "Nationality":       ("rich_text",),
    "Religion":          ("rich_text",),
    "Ideology":          ("rich_text",),
    "Party":             ("select",),
    "Office":            ("rich_text",),
    "Voting Record":     ("rich_text",),
    "Sector":            ("rich_text",),
    "Website":           ("url",),
    "Links":             ("rich_text",),
    "Source URL":        ("url",),
    "Needs Verification":("select",),
    "Evidence":          ("rich_text",),
    "Research Notes":    ("rich_text",),
    "Related":           ("rich_text",),
    "Added By":          ("select",),
    "bftId":             ("rich_text",),
    "Email":             ("email",),
    "Phone":             ("phone_number",),
    "Handle":            ("rich_text",),
    "Outreach Status":   ("select",),
}
# raw record key -> property name
FIELD_MAP = {
    "network": "Network", "platform": "Platform", "audience": "Audience",
    "nationality": "Nationality", "religion": "Religion", "ideology": "Ideology",
    "party": "Party", "office": "Office", "votingRecord": "Voting Record",
    "sector": "Sector", "website": "Website", "links": "Links",
    "sourceUrl": "Source URL", "needsVerification": "Needs Verification",
    "evidence": "Evidence", "researchNotes": "Research Notes", "related": "Related",
    "addedBy": "Added By", "bftId": "bftId", "allianceScore": "Alliance Score",
}


def build_schema_props():
    props = {}
    for name, spec_ in SCHEMA.items():
        t = spec_[0]
        if t == "title": props[name] = {"title": {}}
        elif t == "select": props[name] = {"select": {}}
        elif t == "number": props[name] = {"number": {}}
        elif t == "url": props[name] = {"url": {}}
        elif t == "email": props[name] = {"email": {}}
        elif t == "phone_number": props[name] = {"phone_number": {}}
        else: props[name] = {"rich_text": {}}
    return props


def build_row_props(cat, r):
    p = {"Name": {"title": txt(r.get("name", "(unnamed)"))},
         "Category": {"select": sel(CAT_LABEL.get(cat, cat))}}
    st = sel(r.get("stance"))
    if st: p["Stance"] = {"select": st}
    for key, pname in FIELD_MAP.items():
        raw = r.get(key)
        if raw in (None, ""):
            continue
        t = SCHEMA[pname][0]
        if t == "number":
            try: p[pname] = {"number": float(str(raw))}
            except ValueError: pass
        elif t == "select":
            s = sel(raw)
            if s: p[pname] = {"select": s}
        elif t == "url":
            u = as_url(raw)
            if u: p[pname] = {"url": u}
        else:
            tv = txt(raw)
            if tv: p[pname] = {"rich_text": tv}
    return p


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 tools/notion_master_db.py <parent_page_id> [--limit N]")
    parent = re.sub(r"[^0-9a-fA-F]", "", sys.argv[1].split("?")[0])[-32:]
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    data = load_data()
    rows = [(c, r) for c, rowlist in data.items()
            if c not in SKIP_CATS and not c.startswith("network_")
            for r in rowlist]
    if limit:
        rows = rows[:limit]

    db = ni.call("POST", "databases", {
        "parent": {"type": "page_id", "page_id": parent},
        "title": [{"type": "text", "text": {"content": "BFT Master Database — Entities"}}],
        "description": [{"type": "text", "text": {"content":
            "Every tracked person, org, and company in one searchable table. "
            "Filter by Category for per-network views. bftId is the join key to the live app — never edit it. "
            "Email/Phone/Handle/Outreach Status are for the team to work."}}],
        "properties": build_schema_props(),
    })
    dbid = db["id"]
    print(f"created database: {dbid}\n  url: {db.get('url')}\nloading {len(rows)} rows...", flush=True)

    ok = err = 0
    for i, (cat, r) in enumerate(rows, 1):
        try:
            ni.call("POST", "pages", {"parent": {"database_id": dbid},
                                      "properties": build_row_props(cat, r)})
            ok += 1
        except SystemExit as e:
            err += 1
            print(f"  ROW ERR [{r.get('name')}]: {str(e)[:160]}", flush=True)
        if i % 50 == 0:
            print(f"  ...{i}/{len(rows)} ({ok} ok, {err} err)", flush=True)
        time.sleep(0.34)
    print(f"\nDONE: {ok} rows loaded, {err} errors.\n  open: {db.get('url')}", flush=True)


if __name__ == "__main__":
    main()
