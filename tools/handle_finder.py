#!/usr/bin/env python3
"""Find + VERIFY X and YouTube handles for entities that have none.

Method (safe, no false positives): generate candidate handles from the display
name, fetch the public profile, and accept only if the returned page <title>
contains BOTH the first and last name as whole words. A wrong guess 404s or
fails the name match, so we never write a squatter. Writes NOTHING back to the
HTML -- it emits /tmp/handles_found.json for a reviewed, validated merge.

(Instagram/LinkedIn are login-walled and not guess-verifiable here; those come
from WebSearch, driven separately.)

Usage: python3 tools/handle_finder.py [--limit N]
"""
import re, sys, json, subprocess, urllib.request, urllib.error
import concurrent.futures as cf

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
HTML = "/Users/andy/Downloads/BFT_Living_Database_6.html"
UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                     "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")}
ENTITY = {"influencer", "business_leader", "organization", "business",
          "political", "sponsor", "israeli_tech", "nurture"}
HANDLE_RE = {
    "x": r'(?:x|twitter)\.com/[A-Za-z0-9_]+',
    "youtube": r'youtube\.com/@?[A-Za-z0-9_./-]+',
    "instagram": r'instagram\.com/', "linkedin": r'linkedin\.com/',
}


def load():
    s = re.search(r"<script>\n(.*?)\n</script>", open(HTML, encoding="utf-8").read(), re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    open("/tmp/_hf.js", "w").write(
        s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1) + "\nprint(JSON.stringify(SEED_DATA));")
    return json.loads(subprocess.run([JSC, "/tmp/_hf.js"], capture_output=True, text=True).stdout)


def get_title(url):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=10)
        if r.status != 200:
            return None
        html = r.read(30000).decode("utf-8", "ignore")
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        return " ".join(m.group(1).split()) if m else ""
    except Exception:
        return None


def clean_name(name):
    n = re.sub(r"&[a-z]+;", "", name)                       # strip html entities
    n = re.sub(r"[\"'].*?[\"']", "", n)                     # strip nicknames in quotes
    n = re.sub(r"\(.*?\)", "", n)                           # strip parentheticals
    n = re.sub(r"\b(Dr|Rabbi|Pastor|Rev|Sen|Rep|Gov|Mr|Ms|Mrs)\b\.?", "", n, flags=re.I)
    return " ".join(n.split())


def name_words(name):
    return [w for w in re.findall(r"[A-Za-z]+", clean_name(name)) if len(w) > 1]


def x_candidates(name):
    w = [x.lower() for x in name_words(name)]
    if len(w) < 2:
        return []
    f, l = w[0], w[-1]
    c = [f + l, f + "_" + l, f + "." + l, "real" + f + l, "the" + f + l,
         f + l + "official", "official" + f + l, f[0] + l, f + l[0],
         "mr" + f + l, f + "_" + l + "_"]
    seen, out = set(), []
    for h in c:
        if h not in seen and 2 <= len(h) <= 15:
            seen.add(h); out.append(h)
    return out[:8]


def matches(title, name):
    if not title:
        return False
    t = title.lower()
    ws = [w.lower() for w in name_words(name)]
    if len(ws) < 2:
        return False
    return all(re.search(r"\b" + re.escape(w) + r"\b", t) for w in (ws[0], ws[-1]))


def find_x(name):
    for h in x_candidates(name):
        t = get_title(f"https://x.com/{h}")
        if t and matches(t, name) and "@" in t:
            return h, t
    return None, None


def find_youtube(name):
    w = name_words(name)
    if len(w) < 2:
        return None, None
    for h in ["".join(w), w[0] + w[-1], w[0] + w[-1] + "official"]:
        t = get_title(f"https://www.youtube.com/@{h}")
        if t and matches(t, name):
            return h, t
    return None, None


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    data = load()
    todo = []
    for cat, rows in data.items():
        if cat not in ENTITY:
            continue
        for r in rows:
            blob = " ".join(str(r.get(k, "")) for k in ("links", "platform", "sourceUrl", "website"))
            if not re.search(HANDLE_RE["x"], blob, re.I):     # focus: those missing X
                todo.append((cat, r.get("bftId", ""), r.get("name", "")))
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} entities missing an X handle; verifying candidates...", flush=True)

    found = []

    def work(item):
        cat, bid, name = item
        xh, xt = find_x(name)
        yh, yt = find_youtube(name) if len(name_words(name)) >= 2 else (None, None)
        got = {}
        if xh:
            got["x"] = {"handle": xh, "title": xt}
        if yh:
            got["youtube"] = {"handle": yh, "title": yt}
        return (cat, bid, name, got) if got else None

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for i, res in enumerate(ex.map(work, todo), 1):
            if res:
                cat, bid, name, got = res
                found.append({"cat": cat, "bftId": bid, "name": name, "handles": got})
                tag = ", ".join(f"{k}:@{v['handle']}" for k, v in got.items())
                print(f"  [{i}] {name[:28]:<30s} {tag}", flush=True)
            if i % 40 == 0:
                print(f"  ...{i}/{len(todo)} scanned, {len(found)} found", flush=True)

    json.dump(found, open("/tmp/handles_found.json", "w"), indent=1)
    print(f"\nDONE: verified handles for {len(found)}/{len(todo)} -> /tmp/handles_found.json", flush=True)


if __name__ == "__main__":
    main()
