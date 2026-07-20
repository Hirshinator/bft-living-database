#!/usr/bin/env python3
"""Harvest handles that already exist in an entity's OWN descriptive text and
consolidate them into its `links` field. Zero network calls, high precision.

Precision rules (why this won't mis-assign a handle):
  * Only scans SELF-describing fields (audience, platform, handleSource,
    sourceUrl, website). It deliberately SKIPS evidence/researchNotes/related,
    which routinely mention OTHER people's handles ("she reposted @SamBrown").
  * Accepts two shapes: (a) a full profile URL, (b) a "(@handle)" that is
    immediately preceded by a platform word (e.g. "X (@EricLDaugh)").
  * Appends only handles not already present in `links`. Never overwrites.

Emits /tmp/harvest_report.json and, with --write, edits the HTML in place
(then run validate.py -- the caller does).

Usage: python3 tools/harvest_handles.py [--write]
"""
import re, sys, json, subprocess

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
P = "/Users/andy/Downloads/BFT_Living_Database_6.html"
ENTITY = {"influencer", "business_leader", "organization", "business",
          "political", "sponsor", "israeli_tech", "nurture"}
SELF_FIELDS = ("audience", "platform", "handleSource", "sourceUrl", "website")

DOMAIN = {"x": "x.com", "twitter": "x.com", "instagram": "instagram.com", "ig": "instagram.com",
          "youtube": "youtube.com", "yt": "youtube.com", "tiktok": "tiktok.com",
          "rumble": "rumble.com", "facebook": "facebook.com", "fb": "facebook.com",
          "linkedin": "linkedin.com", "truth social": "truthsocial.com",
          "truthsocial": "truthsocial.com", "threads": "threads.net"}
URL_RE = re.compile(
    r'\b((?:x|twitter|instagram|youtube|tiktok|rumble|facebook|linkedin|truthsocial|threads)\.(?:com|net)/'
    r'@?[A-Za-z0-9_./-]+)', re.I)
# platform word then (@handle):  "X (@EricLDaugh)"  /  "YouTube (@johnnyharris, 7.84M)"
PAREN_RE = re.compile(
    r'\b(x|twitter|instagram|ig|youtube|yt|tiktok|rumble|facebook|fb|linkedin|truth\s?social|threads)\b'
    r'[^()]{0,12}\(@([A-Za-z0-9_.]+)', re.I)


def load():
    s = re.search(r"<script>\n(.*?)\n</script>", open(P, encoding="utf-8").read(), re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    open("/tmp/_hv.js", "w").write(
        s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1) + "\nprint(JSON.stringify(SEED_DATA));")
    return json.loads(subprocess.run([JSC, "/tmp/_hv.js"], capture_output=True, text=True).stdout)


# Platforms whose modern profile URL requires an @ before the handle.
AT_PLATFORMS = ("youtube.com", "tiktok.com", "threads.net", "truthsocial.com")


def norm(u):
    u = u.strip().strip(".,;)").lower()
    u = re.sub(r'^https?://', '', u)
    u = re.sub(r'^www\.', '', u)
    if u.startswith("twitter.com/"):
        u = "x.com/" + u.split("/", 1)[1]
    u = u.rstrip("/")
    # ensure the @ for platforms that need it, but not for /channel//c//user/ paths
    dom, _, path = u.partition("/")
    if dom in AT_PLATFORMS and path and not path.startswith(("@", "channel/", "c/", "user/", "watch", "shorts/")):
        u = f"{dom}/@{path}"
    return u


def harvest_from(r):
    text = "  ".join(str(r.get(k, "")) for k in SELF_FIELDS)
    found = []
    for m in URL_RE.finditer(text):
        found.append(norm(m.group(1)))
    for m in PAREN_RE.finditer(text):
        plat = re.sub(r'\s+', ' ', m.group(1).lower())
        dom = DOMAIN.get(plat)
        if dom:
            found.append(norm(f"{dom}/{m.group(2)}"))
    # dedupe, drop bare-domain noise + non-profile YouTube paths (watch/shorts/etc.)
    BAD = ("youtube.com/watch", "youtube.com/shorts", "youtube.com/embed",
           "youtube.com/playlist")
    out = []
    for h in found:
        if not ("/" in h and not h.endswith((".com", ".net"))):
            continue
        if any(h.startswith(b) for b in BAD):
            continue
        if h not in out:
            out.append(h)
    return out


def main():
    write = "--write" in sys.argv
    data = load()
    report = []
    for cat, rows in data.items():
        if cat not in ENTITY:
            continue
        for r in rows:
            harvested = harvest_from(r)
            if not harvested:
                continue
            existing = norm_all(r.get("links", ""))
            new = [h for h in harvested if h not in existing]
            if new:
                report.append({"cat": cat, "name": r.get("name", ""),
                               "bftId": r.get("bftId", ""), "new": new,
                               "had": bool(r.get("links", "").strip())})
    json.dump(report, open("/tmp/harvest_report.json", "w"), indent=1)
    total = sum(len(x["new"]) for x in report)
    print(f"{len(report)} entities gain {total} handles not already in their links.")
    from collections import Counter
    c = Counter(h.split("/")[0] for x in report for h in x["new"])
    for dom, n in c.most_common():
        print(f"  {dom:<16s} {n}")
    print("\nsamples:")
    for x in report[:12]:
        print(f"  {x['name'][:26]:<28s} + {', '.join(x['new'])}")

    if write:
        apply_writes(report)


def norm_all(links):
    return [norm(x) for x in re.split(r'[;\s]+', links or "") if "/" in x]


def apply_writes(report):
    src = open(P, encoding="utf-8").read()
    done = 0
    for x in report:
        add = "; ".join(x["new"])
        m = re.search(r'\{name:"%s"' % re.escape(x["name"]), src)
        if not m:
            continue
        start = m.start(); end = src.find("},", start)
        obj = src[start:end]
        lm = re.search(r'links:"([^"\\]*)"', obj)
        if lm:
            cur = lm.group(1)
            newval = cur + ("; " if cur.strip() else "") + add
            src = src[:start + lm.start(1)] + newval + src[start + lm.end(1):]
        else:
            bm = re.search(r'(bftId:"[^"]*",? ?)', obj)
            if not bm:
                continue
            ins = start + bm.end()
            src = src[:ins] + f'links:"{add}", ' + src[ins:]
        done += 1
    open(P, "w", encoding="utf-8").write(src)
    print(f"\nwrote handles into {done} entities.")


if __name__ == "__main__":
    main()
