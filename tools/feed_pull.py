#!/usr/bin/env python3
"""Layer B: populate the Live Feed from PUBLIC, key-free sources.

  * YouTube channel RSS  (https://www.youtube.com/feeds/videos.xml?channel_id=UC..)
  * Google News RSS      (news.google.com/rss/search?q="Name" (Israel OR ..))

Generates *candidate* events (verified:"no", addedBy:"Layer B auto") and appends
them to SEED_DATA.feed in the master HTML, de-duping against existing sources.
These are LEADS for a human (or the trusted circle) to confirm -- sentiment is
left "neutral" because a headline alone doesn't establish stance.

RUN FOREGROUND ONLY (never background) -- it read-modify-writes the master file;
a concurrent foreground edit would be clobbered. See the no-concurrent-writes rule.

Usage:
  python3 tools/feed_pull.py --yt --limit 60          # youtube uploads
  python3 tools/feed_pull.py --news --top 25          # google-news per top names
  python3 tools/feed_pull.py --yt --news --apply      # both, and write to SEED
Without --apply it only writes /tmp/feed_candidates.json for review.
"""
import re, sys, json, subprocess, urllib.request, urllib.parse, time, html, hashlib
from datetime import datetime, timezone

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
P = "/Users/andy/Downloads/BFT_Living_Database_6.html"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"}
PEOPLE = ["influencer", "business_leader", "political", "nurture", "rising_stars", "swing", "grassroots_politics"]

def get(u, to=15):
    for att in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=to).read().decode("utf-8", "ignore")
        except Exception:
            if att < 3: time.sleep(2 + att * 2); continue
            return ""
    return ""

def load():
    s = re.search(r"<script>\n(.*?)\n</script>", open(P, encoding="utf-8").read(), re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    open("/tmp/_fp.js", "w").write(s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1) + "\nprint(JSON.stringify(SEED_DATA));")
    return json.loads(subprocess.run([JSC, "/tmp/_fp.js"], capture_output=True, text=True).stdout)

def yt_channel_id(blob):
    m = re.search(r"youtube\.com/channel/(UC[\w-]{20,})", blob)
    if m: return m.group(1)
    m = re.search(r"youtube\.com/(@[\w.-]+)", blob)
    if not m: return None
    page = get("https://www.youtube.com/" + m.group(1))
    mm = re.search(r'"(?:channelId|externalId)":"(UC[\w-]{20,})"', page) or re.search(r"/channel/(UC[\w-]{20,})", page)
    return mm.group(1) if mm else None

def yt_latest(cid, n=1):
    xml = get("https://www.youtube.com/feeds/videos.xml?channel_id=" + cid)
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", xml, re.S)[:n]:
        t = re.search(r"<title>(.*?)</title>", e, re.S)
        d = re.search(r"<published>(.*?)</published>", e)
        l = re.search(r'<link rel="alternate" href="(.*?)"', e)
        if t and d:
            out.append((html.unescape(t.group(1)).strip(), d.group(1)[:10], l.group(1) if l else ""))
    return out

def news_latest(name, n=1):
    q = urllib.parse.quote(f'"{name}" (Israel OR Zionist OR antisemitism OR Gaza)')
    xml = get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en")
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S)[:n]:
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", it)
        l = re.search(r"<link>(.*?)</link>", it)
        if t and d:
            try: dt = datetime.strptime(d.group(1)[:16].strip(), "%a, %d %b %Y").strftime("%Y-%m-%d")
            except Exception: dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            out.append((html.unescape(re.sub(r"<.*?>", "", t.group(1))).strip(), dt, l.group(1) if l else ""))
    return out

def main():
    d = load()
    do_yt, do_news, apply = "--yt" in sys.argv, "--news" in sys.argv, "--apply" in sys.argv
    if not (do_yt or do_news): do_yt = do_news = True
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 60
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 25
    existing_src = {e.get("source", "") for e in d.get("feed", []) if e.get("source")}
    existing_head = {e.get("headline", "").lower() for e in d.get("feed", [])}
    cands = []

    # relevance filter for raw YouTube uploads (Google News is already topic-scoped)
    TOPIC = re.compile(r"\b(israel|zionis|jewish|\bjew\b|antisemit|judeo|gaza|hamas|hezbollah|\biran\b|netanyahu|palestin|\bidf\b|kotel|tefillin|evangelical|christian nationalis|hostage|west bank|settler|bds)\b", re.I)
    # names of other tracked entities -> catch cross-appearances ("... with Tucker Carlson")
    tracked = set()
    for cat in list(d):
        for r in d.get(cat, []):
            nm = (r.get("name") or "").strip()
            if len(nm) >= 5 and not nm.startswith("@"): tracked.add(nm)
    def relevant(title, self_name):
        if TOPIC.search(title): return True
        low = title.lower()
        for t in tracked:
            if t != self_name and t.lower() in low: return True
        return False

    if do_yt:
        n = 0
        for cat in PEOPLE:
            for r in d.get(cat, []):
                if n >= limit: break
                blob = (r.get("links", "") or "") + " " + (r.get("sourceUrl", "") or "") + " " + str(r.get("platform", "") or "")
                if "youtube.com" not in blob: continue
                n += 1; time.sleep(0.4)
                cid = yt_channel_id(blob)
                if not cid: continue
                for title, date, link in yt_latest(cid, 3):
                    if link in existing_src or title.lower() in existing_head: continue
                    if not relevant(title, r["name"]): continue   # drop off-topic uploads
                    cands.append({"id": "ev-yt-" + hashlib.md5(link.encode()).hexdigest()[:8], "date": date,
                                  "persons": [r["name"]], "type": "broadcast", "sentiment": "neutral",
                                  "headline": f"{r['name']}: “{title}”", "detail": "[Layer B auto-pull — YouTube upload (topic/name match), unverified]",
                                  "source": link, "addedBy": "Layer B auto", "verified": "no"})
                    break   # one relevant upload per person per run
        print(f"youtube: scanned {n} channels -> {len(cands)} on-topic candidates so far")

    if do_news:
        ranked = sorted([r for cat in PEOPLE for r in d.get(cat, [])],
                        key=lambda r: int(re.sub(r"\D", "", str(r.get("allianceScore", "0"))) or 0), reverse=True)[:top]
        before = len(cands)
        for r in ranked:
            time.sleep(0.5)
            for title, date, link in news_latest(r["name"], 1):
                if link in existing_src or title.lower() in existing_head: continue
                cands.append({"id": "ev-nw-" + hashlib.md5((link or title).encode()).hexdigest()[:8], "date": date,
                              "persons": [r["name"]], "type": "post", "sentiment": "neutral",
                              "headline": title, "detail": "[Layer B auto-pull — Google News, unverified]",
                              "source": link, "addedBy": "Layer B auto", "verified": "no"})
        print(f"news: scanned {len(ranked)} names -> {len(cands)-before} candidates")

    json.dump(cands, open("/tmp/feed_candidates.json", "w"), indent=1)
    print(f"TOTAL candidates: {len(cands)} (written to /tmp/feed_candidates.json)")

    if apply and cands:
        src = open(P, encoding="utf-8").read()
        m = re.search(r"\n    feed:\s*\[", src)
        ins = m.end()
        def ser(r): return "{" + ", ".join(f"{k}:{json.dumps(v, ensure_ascii=False)}" for k, v in r.items()) + "}"
        block = "".join("\n      " + ser(c) + "," for c in cands)
        src = src[:ins] + block + src[ins:]
        open(P, "w", encoding="utf-8").write(src)
        print(f"APPLIED {len(cands)} candidate events to SEED_DATA.feed")

if __name__ == "__main__":
    main()
