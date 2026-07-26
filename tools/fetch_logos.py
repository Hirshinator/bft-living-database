#!/usr/bin/env python3
"""Fetch + embed small base64 logos/avatars into records that lack one.
  --orgs      : org/media/business/sponsor -> website og:image / apple-touch-icon / favicon
  --youtube   : people with a youtube handle -> channel avatar (og:image)
  --limit N   : cap the batch
Writes into the HTML `logo`/`photo` field (64px, JPEG/PNG base64). Idempotent
(skips records that already have a logo). Run validate.py after (caller does).
"""
import re, sys, json, base64, io, subprocess, urllib.request
from PIL import Image
JSC="/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
P="/Users/andy/Downloads/BFT_Living_Database_6.html"
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"}
ORG={"organization","media","business","israeli_tech","sponsor"}

def get(u,to=12):
    return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=to).read()

def to_b64(raw):
    try:
        im=Image.open(io.BytesIO(raw)).convert("RGB")
        im.thumbnail((64,64))
        buf=io.BytesIO(); im.save(buf,"JPEG",quality=78)
        return "data:image/jpeg;base64,"+base64.b64encode(buf.getvalue()).decode()
    except Exception: return None

def og_image(html):
    for pat in [r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                r'<link[^>]+rel=["\']apple-touch-icon[^>]*["\'][^>]+href=["\']([^"\']+)',
                r'<link[^>]+rel=["\'](?:shortcut )?icon["\'][^>]+href=["\']([^"\']+)']:
        m=re.search(pat, html, re.I)
        if m: return m.group(1)
    return None

def absolutize(base, u):
    if u.startswith("http"): return u
    if u.startswith("//"): return "https:"+u
    from urllib.parse import urljoin; return urljoin(base, u)

def load():
    s=re.search(r"<script>\n(.*?)\n</script>",open(P,encoding="utf-8").read(),re.S).group(1)
    a=s.find("const SEED_DATA"); b=s.find("\n  };",a)+4
    open("/tmp/_lg.js","w").write(s[a:b].replace("const SEED_DATA","var SEED_DATA",1)+"\nprint(JSON.stringify(SEED_DATA));")
    return json.loads(subprocess.run([JSC,"/tmp/_lg.js"],capture_output=True,text=True).stdout)

def yt_handle(r):
    m=re.search(r'youtube\.com/(@[\w.-]+|channel/[\w-]+|c/[\w-]+)', (r.get("links","") or "")+" "+(r.get("sourceUrl","") or "")+" "+(r.get("platform","") or ""))
    return m.group(0) if m else None

def main():
    d=load(); limit=int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else 9999
    targets=[]
    if "--orgs" in sys.argv:
        from urllib.parse import urlparse
        for c in ORG:
            for r in d.get(c,[]):
                if r.get("logo") or r.get("photo"): continue
                site=(r.get("website") or "").strip() or (r.get("sourceUrl") or "").strip()
                if not site.startswith("http"): continue
                p=urlparse(site); root=f"{p.scheme}://{p.netloc}"   # site root -> favicon/og = the logo, not an article image
                targets.append((r["name"], root, "site"))
    if "--youtube" in sys.argv:
        for c in ["influencer","business_leader","nurture","rising_stars","swing","political"]:
            for r in d.get(c,[]):
                if not (r.get("logo") or r.get("photo")):
                    h=yt_handle(r)
                    if h: targets.append((r["name"], "https://www.youtube.com/"+h, "yt"))
    targets=targets[:limit]
    def yt_avatar(url):
        from yt_dlp import YoutubeDL
        with YoutubeDL({"quiet":True,"no_warnings":True,"skip_download":True,"playlist_items":"0","extract_flat":True}) as y:
            info=y.extract_info(url, download=False)
        thumbs=info.get("thumbnails") or []
        av=[t for t in thumbs if "avatar" in (t.get("id","")+t.get("url","")).lower()] or thumbs
        return av[-1]["url"] if av else None

    src=open(P,encoding="utf-8").read(); done=0; report=[]
    for name, url, kind in targets:
        try:
            if kind=="yt":
                img=yt_avatar(url)
                if not img: report.append((name,"no avatar")); continue
                b64=to_b64(get(img))
            else:
                from urllib.parse import urlparse
                b64=None
                try:
                    html=get(url).decode("utf-8","ignore")
                    img=og_image(html)
                    if img: b64=to_b64(get(absolutize(url,img)))
                except Exception: pass
                if not b64:   # universal fallback: Google's favicon service (never bot-blocks)
                    dom=urlparse(url).netloc
                    b64=to_b64(get(f"https://www.google.com/s2/favicons?domain={dom}&sz=128"))
            if not b64: report.append((name,"decode fail")); continue
        except Exception as e:
            report.append((name, type(e).__name__)); continue
        # inject logo into the record (after bftId, or after name)
        m=re.search(r'\{name:"%s"'%re.escape(name), src)
        if not m: report.append((name,"not found in src")); continue
        obj_end=src.find("},",m.start())
        obj=src[m.start():obj_end]
        if 'logo:"' in obj or 'photo:"' in obj: continue
        anchor=re.search(r'(bftId:"[^"]*",? ?)', obj) or re.search(r'(name:"[^"]*",? ?)', obj)
        ins=m.start()+anchor.end()
        src=src[:ins]+f'logo:"{b64}", '+src[ins:]
        done+=1; report.append((name,f"OK {len(b64)//1024}KB"))
    open(P,"w",encoding="utf-8").write(src)
    print(f"embedded {done}/{len(targets)} logos")
    for nm,st in report: print(f"   {nm[:34]:<36s} {st}")

if __name__=="__main__": main()
