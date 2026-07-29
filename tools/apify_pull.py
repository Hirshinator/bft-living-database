#!/usr/bin/env python3
"""Apify-powered public-data harvester (no live login needed).

  --ig <handle> [handle2 ...]                     -> IG profile: verified handle, followers,
                                                     profile image, bio, external links (RELIABLE)
  --replies <tweetURL|conversationId> [--max N]   -> X reply authors (UNRELIABLE on free tier:
                                                     X actors return noResults/demo -> use the
                                                     logged-in browser for X instead)

IG uses apify/instagram-scraper (official, works on free credit). X uses Tweet Scraper V2.
Outputs /tmp/apify_out.json. Reads APIFY_TOKEN from ~/.bft_secrets. Writes only to /tmp.
"""
import sys, os, re, json, urllib.request

TOK = next(l.split("=", 1)[1].strip() for l in open(os.path.expanduser("~/.bft_secrets")) if l.startswith("APIFY_TOKEN="))
ACTOR = "apidojo~tweet-scraper"

HOSTILE = re.compile(r"\b(talmud|skin suit|khazar|synagogue of satan|christ-?killer|not our older brother|worshipping jews|fake jews|giving the game away|embarrassing yourself|reject(ed)? (the )?(messiah|christ)|zionis[tm].*(control|lobby|coloni)|genocid|apartheid|from the river)\b", re.I)
PRO = re.compile(r"\b(older brother|stand with|support (israel|them|the jew)|share a (moral|community)|romans 11|god bless|our (jewish )?neighbou?rs|judeo-?christian (values|worldview)|salvation (is|comes) (of|from) the jews|combat antisemit|defend)\b", re.I)

def run(payload):
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={TOK}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))

def author(it):
    a = it.get("author") or {}
    return {"handle": a.get("userName") or a.get("screen_name") or "", "name": a.get("name") or "",
            "followers": a.get("followers") or a.get("followersCount") or 0, "verified": a.get("isVerified") or a.get("isBlueVerified") or False}

def sentiment(text):
    if HOSTILE.search(text or ""): return "hostile"
    if PRO.search(text or ""): return "pro"
    return "neutral"

def ig_profiles(handles):
    urls = [f"https://www.instagram.com/{h.lstrip('@')}/" for h in handles]
    items = run_actor("apify~instagram-scraper", {"directUrls": urls, "resultsType": "details", "resultsLimit": 1})
    out = []
    for it in items:
        if not it or it.get("error") or "username" not in it: continue
        out.append({"handle": it.get("username"), "name": it.get("fullName"),
                    "followers": it.get("followersCount"), "verified": it.get("verified"),
                    "bio": it.get("biography", ""), "website": it.get("externalUrl") or "",
                    "otherLinks": [u.get("url") for u in (it.get("externalUrls") or []) if u.get("url")],
                    "photoUrl": it.get("profilePicUrlHD") or it.get("profilePicUrl") or "",
                    "private": it.get("private")})
    return out

def run_actor(slug, body):
    url = f"https://api.apify.com/v2/acts/{slug}/run-sync-get-dataset-items?token={TOK}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))

def main():
    if "--ig" in sys.argv:
        handles = [h for h in sys.argv[sys.argv.index("--ig") + 1:] if not h.startswith("--")]
        rows = ig_profiles(handles)
        json.dump(rows, open("/tmp/apify_out.json", "w"), indent=1)
        for r in rows:
            print(f"  @{r['handle']}: {r['followers']:,} foll{' ✓' if r['verified'] else ''} | site: {r['website'] or '-'} | pic: {'yes' if r['photoUrl'] else 'no'}")
            print(f"      bio: {r['bio'][:80]!r}" + (f" | links: {r['otherLinks']}" if r['otherLinks'] else ""))
        return
    if "--replies" in sys.argv:
        arg = sys.argv[sys.argv.index("--replies") + 1]
        cid = re.search(r"status/(\d+)", arg).group(1) if "status/" in arg else arg
        mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 40
        items = run({"conversationIds": [cid], "maxItems": mx, "sort": "Top"})
        rows = []
        for it in items:
            if str(it.get("id")) == cid: continue          # skip the root tweet
            au = author(it); txt = it.get("text") or it.get("fullText") or ""
            rows.append({**au, "text": txt[:240], "sentiment": sentiment(txt),
                         "url": it.get("url") or it.get("twitterUrl") or ""})
        json.dump(rows, open("/tmp/apify_out.json", "w"), indent=1)
        pro = [r for r in rows if r["sentiment"] == "pro"]
        hos = [r for r in rows if r["sentiment"] == "hostile"]
        print(f"replies fetched: {len(rows)}  |  pro: {len(pro)}  hostile: {len(hos)}  neutral: {len(rows)-len(pro)-len(hos)}")
        print("\n-- PRO (grassroots candidates) --")
        for r in sorted(pro, key=lambda x: -int(x['followers'] or 0)):
            print(f"  @{r['handle']:20s} {int(r['followers'] or 0):>7} foll  {r['text'][:90]}")
        print("\n-- HOSTILE (skip unless high-influence) --")
        for r in sorted(hos, key=lambda x: -int(x['followers'] or 0))[:8]:
            flag = "  <-- HIGH-INFLUENCE, map it" if int(r['followers'] or 0) >= 50000 else ""
            print(f"  @{r['handle']:20s} {int(r['followers'] or 0):>7} foll  {r['text'][:70]}{flag}")
    elif "--profile" in sys.argv:
        handles = [h for h in sys.argv[sys.argv.index("--profile") + 1:] if not h.startswith("--")]
        items = run({"twitterHandles": handles, "maxItems": len(handles) * 2})
        seen = {}
        for it in items:
            a = author(it)
            if a["handle"] and a["handle"] not in seen:
                seen[a["handle"]] = {**a, "bio": (it.get("author") or {}).get("description", "")}
        json.dump(list(seen.values()), open("/tmp/apify_out.json", "w"), indent=1)
        for h, v in seen.items():
            print(f"  @{h}: {int(v['followers'] or 0)} foll | {v['bio'][:120]}")
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
