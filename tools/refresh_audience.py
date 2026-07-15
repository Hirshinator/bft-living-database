#!/usr/bin/env python3
"""Live-verify audience numbers for BFT Living Database influencers.

WHAT WORKS (verified 14 Jul 2026):
  - YouTube: subscriber count, view count, join date  -> fetchable
  - TikTok:  followerCount                            -> fetchable
WHAT DOESN'T:
  - X/Twitter: JS-rendered, no counts in HTML
  - Instagram: page loads, counts not trivially parseable
  - Social Blade: 403

Usage:
    python3 tools/refresh_audience.py [path-to-html]        # report only
    python3 tools/refresh_audience.py [path] --write        # write updates back

Why this exists: a 14 Jul 2026 audit found DB audience figures were stale or
wrong -- one entry (Lance Johnston) was overstated ~50x by an unreliable
source. Audience size drives the seed-100 "back the winners" strategy, so it
must be measured, not asserted.
"""
import re, sys, time, urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
PATH = next((a for a in sys.argv[1:] if not a.startswith("--")),
            "/Users/andy/Downloads/BFT_Living_Database_6.html")
WRITE = "--write" in sys.argv

def get(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
    except Exception:
        return ""

def youtube_subs(handle):
    m = re.search(r'"subscriberCountText":"([^"]*)"', get(f"https://www.youtube.com/@{handle}/about"))
    return m.group(1) if m else None

def tiktok_followers(handle):
    m = re.search(r'"followerCount":(\d+)', get(f"https://www.tiktok.com/@{handle}"))
    return f"{int(m.group(1)):,} followers" if m else None

def main():
    src = open(PATH, encoding="utf-8").read()
    block = re.search(r'\n    influencer: \[\n(.*?)\n    \],', src, re.S).group(1)
    rows, checked = [], 0
    for ln in block.split("\n"):
        g = re.search(r'\{name:"([^"]+)"', ln)
        if not g:
            continue
        blob = " ".join(re.findall(r'(?:links|platform):"([^"]*)"', ln))
        yt = re.search(r'youtube\.com/@([A-Za-z0-9_.-]+)', blob)
        tk = re.search(r'tiktok\.com/@([A-Za-z0-9_.-]+)', blob)
        if not (yt or tk):
            continue
        aud = re.search(r'audience:"([^"]*)"', ln)
        live = []
        if yt:
            v = youtube_subs(yt.group(1))
            if v: live.append(f"YouTube {v}")
        if tk:
            v = tiktok_followers(tk.group(1))
            if v: live.append(f"TikTok {v}")
        checked += 1
        if live:
            rows.append((g.group(1), aud.group(1) if aud else "", "; ".join(live)))
            print(f"{g.group(1)[:34]:36s} DB: {(aud.group(1) if aud else '')[:34]:36s} LIVE: {'; '.join(live)}")
        time.sleep(1)  # be polite
    print(f"\nchecked {checked} entries with handles; {len(rows)} returned live data")
    if not WRITE:
        print("(report only -- pass --write to apply)")
        return
    stamp = time.strftime("live-verified %d %b %Y")
    out = src
    for name, _old, live in rows:
        pat = re.compile(r'(\{name:"%s".*?)(\},)' % re.escape(name), re.S)
        m = pat.search(out)
        if not m:
            continue
        seg = re.sub(r'audience:"[^"]*"', 'audience:"%s (%s)"' % (live, stamp), m.group(1), count=1)
        if "audienceVerified" not in seg:
            seg = re.sub(r'(, evidence:")', ', audienceVerified:"%s"\\1' % stamp, seg, count=1)
        out = out[:m.start()] + seg + m.group(2) + out[m.end():]
    open(PATH, "w", encoding="utf-8").write(out)
    print(f"wrote {len(rows)} updates to {PATH}")

if __name__ == "__main__":
    main()
