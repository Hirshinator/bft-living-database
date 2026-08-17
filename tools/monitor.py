#!/usr/bin/env python3
"""Entity-mention monitor: watch ALL tracked entities across the open web via Google News.

For each tracked person/org, query Google News RSS by exact name and collect recent
mentions. 1,137 names can't all run every minute (Google throttles), so this ROTATES:
each run processes a batch starting from a saved cursor, cycling through everyone over
several days. Writes flywheel/mentions.json (newest first) for the app's feed.

Honest scope: this monitors the WEB/NEWS layer — it catches an entity whenever they are
written about anywhere. It does NOT read their X/IG/TikTok/FB/LinkedIn posts directly
(no third-party API for that). Stdlib only; runs in GitHub Actions.
"""
import os, re, json, html, time, datetime, urllib.request, urllib.parse

HTML = os.environ.get("BFT_HTML_PATH", os.path.join(os.path.dirname(__file__), "..", "index.html"))
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "flywheel")
STATE = os.path.join(OUT_DIR, "monitor_state.json")
MENTIONS = os.path.join(OUT_DIR, "mentions.json")
BATCH = int(os.environ.get("MONITOR_BATCH", "150"))   # names per run
KEEP_DAYS = 12
MAX_MENTIONS = 120
# curated categories only (skip backlog/criteria + backend LinkedIn tables)
CATS = ["influencer", "business_leader", "organization", "media", "business", "ecosystem",
        "political", "sponsor", "events", "israeli_tech", "nurture", "rising_stars", "swing",
        "grassroots_business", "grassroots_politics"]


def load_entities():
    """Return [(name, stance, score)] for CURATED records only (excludes the backend LinkedIn
    network_* tables), prioritized (allies + high score first)."""
    txt = open(HTML, encoding="utf-8").read()
    ents, seen = [], set()
    for cat in CATS:
        m = re.search(r"\n    " + re.escape(cat) + r": \[", txt)
        if not m:
            continue
        start = m.end()
        end = txt.find("\n    ],", start)          # array closer at 4-space indent
        block = txt[start:end] if end > 0 else txt[start:start + 4000000]
        for nm in re.finditer(r'name:"([^"]+)"', block):
            name = nm.group(1).strip()
            if name in seen or len(name) < 4 or name.isupper():
                continue
            seen.add(name)
            window = block[nm.start():nm.start() + 600]
            st = re.search(r'stance:"([^"]+)"', window)
            sc = re.search(r'allianceScore:(\d+)', window)
            ents.append((name, st.group(1) if st else "", int(sc.group(1)) if sc else 0))
    ents.sort(key=lambda e: (0 if e[1] == "pro" else 1, -e[2], e[0].lower()))
    return ents


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (BFT-Monitor/1.0)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def news_for(name):
    q = urllib.parse.quote('"%s"' % name)
    try:
        xml = fetch("https://news.google.com/rss/search?q=%s&hl=en-US&gl=US&ceid=US:en" % q)
    except Exception:
        return []
    out = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        b = m.group(1)
        title = clean((re.search(r"<title>(.*?)</title>", b, re.S) or [None, ""])[1])
        link = clean((re.search(r"<link>(.*?)</link>", b, re.S) or [None, ""])[1])
        date = clean((re.search(r"<pubDate>(.*?)</pubDate>", b, re.S) or [None, ""])[1])
        source = clean((re.search(r"<source[^>]*>(.*?)</source>", b, re.S) or [None, ""])[1])
        if not source and " - " in title:
            p = title.rsplit(" - ", 1); source = p[1].strip(); title = p[0].strip()
        out.append({"title": title, "link": link, "date": date, "source": source or "Google News"})
    return out[:3]


def recent(date_str):
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S GMT"):
        try:
            d = datetime.datetime.strptime(date_str, fmt)
            return (datetime.datetime.utcnow() - d).days <= KEEP_DAYS
        except Exception:
            pass
    return True  # keep if unparseable


def main():
    ents = load_entities()
    total = len(ents)
    state = {}
    if os.path.exists(STATE):
        try: state = json.load(open(STATE))
        except Exception: state = {}
    cursor = state.get("cursor", 0) % max(total, 1)

    batch = [ents[(cursor + i) % total] for i in range(min(BATCH, total))]
    existing = []
    if os.path.exists(MENTIONS):
        try: existing = json.load(open(MENTIONS)).get("mentions", [])
        except Exception: existing = []

    new = []
    for name, stance, score in batch:
        for it in news_for(name):
            if it["title"] and recent(it["date"]):
                new.append({"entity": name, "stance": stance, **it})
        time.sleep(0.4)  # be polite to Google

    # merge: new + existing, dedupe by (entity,title), keep recent, cap
    merged, seen = [], set()
    for it in new + existing:
        k = (it.get("entity", ""), it.get("title", "").lower())
        if it.get("title") and k not in seen:
            seen.add(k); merged.append(it)
    merged.sort(key=lambda i: i.get("date", ""), reverse=True)
    merged = merged[:MAX_MENTIONS]

    os.makedirs(OUT_DIR, exist_ok=True)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    json.dump({"generated": now, "monitored_total": total, "swept_this_run": len(batch),
               "cursor": (cursor + len(batch)) % total, "count": len(merged), "mentions": merged},
              open(MENTIONS, "w"), indent=2, ensure_ascii=False)
    json.dump({"cursor": (cursor + len(batch)) % total, "total": total, "updated": now}, open(STATE, "w"), indent=2)
    print(f"swept {len(batch)}/{total} entities (cursor {cursor} -> {(cursor+len(batch)) % total}); {len(new)} fresh mentions; {len(merged)} total in queue")


if __name__ == "__main__":
    main()
