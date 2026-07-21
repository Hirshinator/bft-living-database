#!/usr/bin/env python3
"""Create the BFT project in Notion via the API.

STATUS: ready to run, blocked ONLY on a token. The Notion API is reachable from
here (it answers 401 without auth), so this is a credential gap, not a
capability gap.

SETUP (Andy, ~2 minutes):
  1. Create an internal integration: https://www.notion.so/my-integrations
     -> "New integration" -> name it (e.g. "BFT Database") -> copy the token
     (starts with `ntn_` or `secret_`).
  2. In Notion, make an empty page to hold everything (e.g. "BFT").
     Open it -> "..." menu -> Connections -> add your integration.
     WITHOUT this step the API cannot see the page and every call 404s.
  3. Put the token in a file Claude reads but git ignores -- DO NOT paste it
     into chat:
         echo 'NOTION_TOKEN=ntn_xxxxx' >> ~/.bft_secrets
         chmod 600 ~/.bft_secrets
  4. Give Claude the parent page URL (the page ID inside it is NOT a secret).

  Then:  python3 tools/notion_import.py <parent_page_id>

WHAT IT CREATES
  - One child page per notion/*.md file (the narrative layer).
  - Markdown headings/bullets/paragraphs -> real Notion blocks.
  - Long pages are chunked: Notion caps rich_text at 2000 chars per block and
    100 blocks per request.

WHAT IT DELIBERATELY DOES NOT DO
  - It does not create the record DATABASES from the CSVs. Notion's own
    "Import -> CSV" types the columns far better than the API does, and at 847
    records the API would be ~5 minutes of paced calls for a worse result.
    Drag `export/*.csv` into Notion after this runs, then set `bftId` as the
    unique key on each.
"""
import os, re, sys, json, time, glob, urllib.request

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
NOTION_DIR = os.path.join(os.path.dirname(__file__), "..", "notion")


def token():
    t = os.environ.get("NOTION_TOKEN")
    if t:
        return t.strip()
    path = os.path.expanduser("~/.bft_secrets")
    if os.path.exists(path):
        for line in open(path):
            if line.strip().startswith("NOTION_TOKEN="):
                return line.split("=", 1)[1].strip()
    sys.exit("No NOTION_TOKEN found. See the setup steps at the top of this file.")


def call(method, path, payload=None):
    req = urllib.request.Request(
        f"{API}/{path}", method=method,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"Bearer {token()}",
                 "Notion-Version": VERSION,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        raise SystemExit(f"Notion API {e.code} on {method} {path}\n  {body}\n"
                         "  (404 usually means the integration wasn't added to the parent page -- step 2.)")


_INLINE = re.compile(r'\*\*(.+?)\*\*|`(.+?)`|\[([^\]]+)\]\(([^)]+)\)|(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)')


def _emit(content, out, ann=None, link=None):
    if not content:
        return
    for i in range(0, len(content), 1900):
        seg = content[i:i + 1900]
        item = {"type": "text", "text": {"content": seg}}
        if link:
            item["text"]["link"] = {"url": link}
        if ann:
            item["annotations"] = ann
        out.append(item)


def rich(text):
    """Parse inline markdown (**bold**, `code`, [text](url), *italic*) into
    Notion rich_text so it renders as formatting, not literal ** / ` characters.
    Notion caps a single rich_text item at 2000 chars, so long spans are chunked."""
    out, pos = [], 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            _emit(text[pos:m.start()], out)
        if m.group(1) is not None:
            _emit(m.group(1), out, {"bold": True})
        elif m.group(2) is not None:
            _emit(m.group(2), out, {"code": True})
        elif m.group(3) is not None:
            _emit(m.group(3), out, link=m.group(4))
        elif m.group(5) is not None:
            _emit(m.group(5), out, {"italic": True})
        pos = m.end()
    if pos < len(text):
        _emit(text[pos:], out)
    return out or [{"type": "text", "text": {"content": ""}}]


def md_to_blocks(md):
    blocks = []
    for raw in md.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3",
                           "heading_3": {"rich_text": rich(line[4:])}})
        elif line.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2",
                           "heading_2": {"rich_text": rich(line[3:])}})
        elif line.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1",
                           "heading_1": {"rich_text": rich(line[2:])}})
        elif line.lstrip().startswith(("- ", "* ")):
            blocks.append({"object": "block", "type": "bulleted_list_item",
                           "bulleted_list_item": {"rich_text": rich(line.lstrip()[2:])}})
        elif line.startswith("> "):
            blocks.append({"object": "block", "type": "quote",
                           "quote": {"rich_text": rich(line[2:])}})
        elif set(line.strip()) <= {"-", "|", " ", ":"} and "|" in line:
            continue                                   # markdown table rule -- skip
        else:
            blocks.append({"object": "block", "type": "paragraph",
                           "paragraph": {"rich_text": rich(line)}})
    return blocks


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 tools/notion_import.py <parent_page_id>")
    # Accept a full URL. Strip any ?query first (its chars pollute the hex
    # window), then take the LAST 32-hex run -- the page id is the trailing
    # -xxxxxxxx... on the path, not whatever hex the query string contains.
    arg = sys.argv[1].split("?", 1)[0]
    hexruns = re.findall(r"[0-9a-fA-F]{32}", arg.replace("-", ""))
    parent = hexruns[-1] if hexruns else re.sub(r"[^0-9a-fA-F]", "", arg)[-32:]
    files = sorted(glob.glob(os.path.join(NOTION_DIR, "*.md")))
    if not files:
        sys.exit(f"no .md files in {NOTION_DIR}")

    print(f"parent page: {parent}\ncreating {len(files)} pages...\n")
    for f in files:
        md = open(f, encoding="utf-8").read()
        title = re.sub(r"^#\s*", "", md.split("\n")[0]).strip() or os.path.basename(f)
        blocks = md_to_blocks(md)
        page = call("POST", "pages", {
            "parent": {"page_id": parent},
            "properties": {"title": [{"type": "text", "text": {"content": title[:200]}}]},
            "children": blocks[:100],                  # first 100 inline
        })
        pid = page["id"]
        rest = blocks[100:]
        while rest:                                    # append the remainder in chunks
            call("PATCH", f"blocks/{pid}/children", {"children": rest[:100]})
            rest = rest[100:]
            time.sleep(0.4)                            # Notion ~3 req/s
        print(f"  created: {title[:60]:<62s} ({len(blocks)} blocks)")
        time.sleep(0.4)

    print("\nPages done. Now import the record databases:")
    print("  In Notion: Import -> CSV, and drag in export/*.csv (11 files, 847 records).")
    print("  Then set `bftId` as the unique key on each database -- it is the join key")
    print("  back to the live app and must never be edited.")


if __name__ == "__main__":
    main()
