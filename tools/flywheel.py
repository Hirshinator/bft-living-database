#!/usr/bin/env python3
"""Autonomous discovery flywheel (YouTube layer).

Sweeps monitored channels' recent uploads, extracts the people they platform
(guest-attribution in titles), diffs against who we already track in the master
data, and writes a candidate review queue:
  - ally channels    -> people they platform = candidate ALLIES
  - hostile channels -> people they boost     = candidate HOSTILES (needs orient check)

Runs in GitHub Actions on a schedule; stdlib only (no pip installs). Reads the
deployed data from index.html (or BFT_HTML_PATH). Writes flywheel/candidates.json
and a human-readable flywheel/candidates.md. Once a candidate is added to the DB
they become "tracked" and drop off the queue automatically.
"""
import os, re, json, html, datetime, urllib.request

HTML = os.environ.get("BFT_HTML_PATH", os.path.join(os.path.dirname(__file__), "..", "index.html"))
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "flywheel")

# Monitored channels. orientation: "ally" (guests = candidate allies) or "hostile"
# (boosted subjects = candidate hostiles). Extend as more channels are resolved.
CHANNELS = [
    {"id": "UCaGCg20T6NcBs0NMU1D4-Rg", "name": "Stand Tall Israel", "orientation": "ally"},
    {"id": "UCF9LFWX5cdGHBg_FDm6tFrQ", "name": "Breezy Politics", "orientation": "hostile"},
    {"id": "UC3M7l8ved_rYQ45AVzS0RGA", "name": "The Jimmy Dore Show", "orientation": "hostile"},
]

NAME_RE = re.compile(r"^[A-Z][a-zA-Z'.-]+(?:\s+[A-Z][a-zA-Z'.-]+){1,2}$")
# noise phrases that pass the capitalization test but aren't people
STOP = {"October", "Word for Word", "New York", "United Nations", "Gaza Must", "The West",
        "The Regime", "The Tide", "The GOP", "Middle East", "October 7"}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (BFT-Flywheel/1.0)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def entries(xml):
    out = []
    for m in re.finditer(r"<entry>(.*?)</entry>", xml, re.S):
        b = m.group(1)
        t = re.search(r"<title>(.*?)</title>", b, re.S)
        p = re.search(r"<published>(.*?)</published>", b)
        l = re.search(r'<link[^>]*href="([^"]+)"', b)
        out.append({
            "title": html.unescape(re.sub(r"<[^>]+>", "", t.group(1))).strip() if t else "",
            "date": (p.group(1)[:10] if p else ""),
            "link": (l.group(1) if l else ""),
        })
    return out


def candidate_names(title):
    """Pull likely person-names from an interview/clip title."""
    names = set()
    # guest attribution: text after the last | or em/en dash
    for sep in ("|", "—", "–"):
        if sep in title:
            tail = title.rsplit(sep, 1)[1].strip()
            tail = re.sub(r"\s*(?:\||#).*$", "", tail).strip()
            if NAME_RE.match(tail) and tail not in STOP:
                names.add(tail)
    return names


def tracked_names():
    txt = open(HTML, encoding="utf-8").read()
    return {re.sub(r"\s+", " ", n).strip().lower() for n in re.findall(r'name:"([^"]+)"', txt)}


def is_new(cand, tracked):
    c = cand.lower()
    for t in tracked:
        if c == t or c in t or t in c:
            return False
    return True


def main():
    tracked = tracked_names()
    found = {}  # name -> {orientation, sources:[{channel,title,date,link}]}
    for ch in CHANNELS:
        try:
            xml = fetch("https://www.youtube.com/feeds/videos.xml?channel_id=" + ch["id"])
        except Exception as e:
            print(f"skip {ch['name']}: {e}")
            continue
        for e in entries(xml)[:15]:
            for name in candidate_names(e["title"]):
                if not is_new(name, tracked):
                    continue
                rec = found.setdefault(name, {"orientation": ch["orientation"], "sources": []})
                rec["sources"].append({"channel": ch["name"], "title": e["title"], "date": e["date"], "link": e["link"]})

    candidates = []
    for name, rec in sorted(found.items()):
        signal = ("candidate ALLY (platformed by an ally channel)" if rec["orientation"] == "ally"
                  else "candidate HOSTILE / check orientation (boosted by a hostile channel)")
        candidates.append({"name": name, "orientation": rec["orientation"], "signal": signal, "sources": rec["sources"]})

    os.makedirs(OUT_DIR, exist_ok=True)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    json.dump({"generated": now, "count": len(candidates), "candidates": candidates},
              open(os.path.join(OUT_DIR, "candidates.json"), "w"), indent=2, ensure_ascii=False)

    md = [f"# Flywheel candidates — {now}",
          f"\n{len(candidates)} new candidate(s) surfaced from monitored channels, not yet in the database.",
          "Review, verify each on the record, then add. (Once added they drop off automatically.)\n"]
    for c in candidates:
        md.append(f"### {c['name']} — {c['signal']}")
        for s in c["sources"][:4]:
            md.append(f"- [{s['channel']}] *{s['title']}* ({s['date']}) — {s['link']}")
        md.append("")
    open(os.path.join(OUT_DIR, "candidates.md"), "w", encoding="utf-8").write("\n".join(md))

    print(f"{len(candidates)} candidates written to flywheel/candidates.json + .md")
    for c in candidates:
        print(f"  [{c['orientation']:7}] {c['name']}")


if __name__ == "__main__":
    main()
