#!/usr/bin/env python3
"""Multi-platform follower-count fetcher for BFT influencers.

TESTED capability map (17 Jul 2026) -- what actually works from here:
  YouTube  : plain fetch, reliable            (subscriberCountText)
  Rumble   : plain fetch, reliable            (/c/Name channel pages)
  TikTok   : plain fetch, INTERMITTENT        (fall back to browser)
  X/Twitter: BROWSER ONLY -- JS-rendered      (this script flags them; fetch
             won't get counts. Confirmed working via the in-app browser:
             Dana Loesch = 1.3M read off the rendered Followers link.)
  Facebook : partial login wall, unreliable
  Instagram: BLOCKED -- login wall even in browser. Not fetchable here.

Why this rewrite matters: the previous version used `audience:"[^"]*"` to patch
the HTML source. `[^"]*` is blind to escaped quotes (\") and on 15 Jul 2026 it
matched PAST a field boundary and corrupted the MilkBarTV entry, which broke the
whole app in production. This version NEVER regex-patches JS source. It reads the
data by executing SEED_DATA with JavaScriptCore and reports; any write-back must
go through the same safe evaluate-mutate path, never a source-text substitution.

Usage:
    python3 tools/refresh_audience.py [path-to-html]     # report only
"""
import re, sys, json, time, subprocess, urllib.request

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
PATH = next((a for a in sys.argv[1:] if not a.startswith("--")),
            "/Users/andy/Downloads/BFT_Living_Database_6.html")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")

def fetch(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
    except Exception:
        return ""

def youtube(handle):
    # CRITICAL: use metadataParts (the MAIN channel's count). The older
    # "subscriberCountText"/simpleText pattern matches a RECOMMENDED channel in
    # the sidebar -- it reported Tovia Singer as 6.37K when he is 132K. Auto-
    # writing that would have overwritten correct data with a sidebar number.
    body = fetch(f"https://www.youtube.com/@{handle}/about")
    m = re.search(r'"metadataParts":\[\{"text":\{"content":"([\d.]+[KMB]? subscribers)"', body)
    return f"YouTube {m.group(1)}" if m else None

def tiktok(handle):
    m = re.search(r'"followerCount":(\d+)', fetch(f"https://www.tiktok.com/@{handle}"))
    return f"TikTok {int(m.group(1)):,} followers" if m else None

def rumble(channel):
    m = re.search(r'([\d,.]+[KMB]?)\s*[Ff]ollowers', fetch(f"https://rumble.com/c/{channel}"))
    return f"Rumble {m.group(1)} followers" if m else None

# Extractors keyed by the handle pattern found in an entry's links/platform text.
SOURCES = [
    (re.compile(r'youtube\.com/@([A-Za-z0-9_.-]+)'), youtube),
    (re.compile(r'rumble\.com/c/([A-Za-z0-9_-]+)'), rumble),
    (re.compile(r'tiktok\.com/@([A-Za-z0-9_.-]+)'), tiktok),
]
# X handles are recorded but must be fetched via the BROWSER, not here.
X_RE = re.compile(r'(?:x|twitter)\.com/([A-Za-z0-9_]+)')

def load_influencers():
    s = re.search(r"<script>\n(.*?)\n</script>", open(PATH, encoding="utf-8").read(), re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    open("/tmp/_aud.js", "w", encoding="utf-8").write(
        s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1) + "\nprint(JSON.stringify(SEED_DATA.influencer));")
    return json.loads(subprocess.run([JSC, "/tmp/_aud.js"], capture_output=True, text=True).stdout)

def main():
    rows = load_influencers()
    live, needs_browser, no_handle = [], [], 0
    for r in rows:
        blob = " ".join(str(r.get(k, "")) for k in ("links", "platform"))
        got = []
        for rx, fn in SOURCES:
            m = rx.search(blob)
            if m:
                v = fn(m.group(1))
                if v: got.append(v)
                time.sleep(0.4)
        if got:
            live.append((r["name"], r.get("audience", ""), "; ".join(got)))
            print(f"  {r['name'][:30]:<32s} DB:{(r.get('audience') or '')[:24]:<26s} LIVE: {'; '.join(got)}")
        elif X_RE.search(blob):
            needs_browser.append((r["name"], X_RE.search(blob).group(1)))
        else:
            no_handle += 1
    print(f"\nfetched live counts for {len(live)} entries (curl-able platforms)")
    print(f"{len(needs_browser)} have an X handle -> fetch via the in-app browser (JS-rendered):")
    for n, h in needs_browser[:40]:
        print(f"   @{h:<20s} {n}")
    print(f"{no_handle} have no fetchable handle at all -> handle backfill needed first")

if __name__ == "__main__":
    main()
