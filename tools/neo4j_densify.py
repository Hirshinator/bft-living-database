#!/usr/bin/env python3
"""Rebuild the Neo4j graph with TYPED, densified edges from the DB.
Scans all descriptive fields + types each edge by the relationship language around
the mention (LEADS/SPONSORS/HOST_GUEST/INVESTED_IN/CO_FOUNDED/etc.). Run after data
changes: python3 tools/neo4j_densify.py  (wipes + rebuilds the graph). Live app untouched.
"""
import os, re, json, subprocess
from neo4j import GraphDatabase
from collections import Counter
def sec(k): return next(l.split("=",1)[1].strip() for l in open(os.path.expanduser("~/.bft_secrets")) if l.startswith(k+"="))
JSC="/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
s=re.search(r'<script>\n(.*?)\n</script>',open('/Users/andy/Downloads/BFT_Living_Database_6.html').read(),re.S).group(1)
a=s.find('const SEED_DATA'); b=s.find('\n  };',a)+4
open('/tmp/_dz.js','w').write(s[a:b].replace('const SEED_DATA','var SEED_DATA',1)+'\nprint(JSON.stringify(SEED_DATA));')
d=json.loads(subprocess.run([JSC,'/tmp/_dz.js'],capture_output=True,text=True).stdout)
LABELS={"influencer":["Person","Influencer"],"rising_stars":["Person","RisingStar"],"swing":["Person","Swing"],
 "nurture":["Person","Nurture"],"business_leader":["Person","BusinessLeader"],"political":["Person","Politician"],
 "grassroots_business":["Person","Grassroots"],"grassroots_politics":["Person","Grassroots"],
 "organization":["Organization"],"media":["MediaCompany"],"business":["Company"],"israeli_tech":["Company","IsraeliTech"],
 "sponsor":["Sponsor"],"ecosystem":["Region"]}
ENTITY=set(LABELS)
raws={}
for c,rows in d.items():
    if c in ENTITY:
        for r in rows:
            nm=r.get("name","").strip()
            if nm: raws[nm]=(c,r)
names=list(raws); low={n.lower():n for n in names}
TEXTF=["evidence","researchNotes","talentEvidence","costPaid","platform","related","leader","yieldNotes","audience","description","rationale","relationship","show","related"]
# relationship-verb -> edge type (checked in the ~60 chars BEFORE a mention)
VERBS=[(r'co-?found',"CO_FOUNDED"),(r'\bfound(ed|er)\b|\bceo\b|president|chairman|\bleads\b|\bruns\b|head of|founder of',"LEADS"),
 (r'work(s|ed)? (for|at|with)|employ|on the team|staff',"WORKS_WITH"),(r'co-?host',"CO_HOST"),
 (r'host(s|ed)?|guest|interview|appeared on|featured|sat down|clip',"HOST_GUEST"),
 (r'invest(ed|or|s|ing)?|backer|fund(ed|s)?|portfolio|venture|a16z',"INVESTED_IN"),
 (r'sponsor|advertis|paid partner',"SPONSORS"),(r'board|advisor|advises|counsel to|chief of staff',"ADVISOR_TO"),
 (r'friend|close (to|ally)|allied with|befriend',"FRIEND"),(r'rival|feud|beef|clash',"RIVAL"),
 (r'attack|hostile|slam|blast|criticiz|denounc|accus|against',"ADVERSARY"),
 (r'endorse|amplif|boost|praise|repost|shared|support(ed|s)?',"ENDORSED"),
 (r'donat|gave to|contribut',"DONATED_TO"),(r'mentor|protege|trained|student of',"MENTORED")]
RANK={"CO_FOUNDED":9,"LEADS":8,"SAME_ORG":8,"SPONSORS":7,"INVESTED_IN":7,"WORKS_WITH":6,"ADVISOR_TO":6,
 "CO_HOST":6,"HOST_GUEST":5,"MENTORED":5,"DONATED_TO":5,"FRIEND":4,"RIVAL":4,"ENDORSED":3,
 "ADVERSARY":3,"ENEMY":2,"ALLY":2,"ASSOCIATE":0}
edges={}
def put(x,y,ty):
    if x==y or not x or not y: return
    k=tuple(sorted((x,y)))
    if k not in edges or RANK.get(ty,0)>RANK.get(edges[k],0): edges[k]=ty
def is_pro(x): return x=="pro"
def is_hos(x): return x in("hostile","redflag")
# 1. org leader -> LEADS/SAME_ORG
for nm,(c,r) in raws.items():
    if c in("organization","media","business","israeli_tech"):
        for frag in re.split(r",|&|\band\b",re.sub(r"\(.*?\)","",str(r.get("leader","")))):
            frag=frag.strip()
            if len(frag)>=4 and frag.lower() in low: put(nm,low[frag.lower()],"LEADS")
# 2. related -> stance-typed
for nm,(c,r) in raws.items():
    for frag in re.split(r"[;,]",str(r.get("related",""))):
        f=frag.strip().lower()
        if f in low and low[f]!=nm:
            sa,sb=r.get("stance"),raws[low[f]][1].get("stance")
            ty="ALLY" if is_pro(sa) and is_pro(sb) else "ENEMY" if is_hos(sa) and is_hos(sb) else "ADVERSARY" if (is_pro(sa) and is_hos(sb)) or (is_hos(sa) and is_pro(sb)) else "ASSOCIATE"
            put(nm,low[f],ty)
# 3. context-typed mention scan across ALL text fields
patterns=[(nm,re.compile(r"(^|[^a-z0-9])"+re.escape(nm.lower())+r"([^a-z0-9]|$)")) for nm in names if len(nm)>=5]
for src_nm,(c,r) in raws.items():
    blob=" ".join(str(r.get(f,"")) for f in TEXTF).lower()
    if not blob.strip(): continue
    for tgt,pat in patterns:
        if tgt==src_nm: continue
        m=pat.search(blob)
        if not m: continue
        win=blob[max(0,m.start()-60):m.start()]
        ty="ASSOCIATE"
        for rx,t in VERBS:
            if re.search(rx,win): ty=t; break
        put(src_nm,tgt,ty)
# 4. sponsor edges
for nm,(c,r) in raws.items():
    if c=="sponsor":
        for f in ["relationship","show","related","evidence"]:
            for cand in re.split(r"[;,]|\band\b",str(r.get(f,""))):
                cc=re.sub(r"\(.*?\)","",cand).strip().lower()
                if cc in low and low[cc]!=nm: put(nm,low[cc],"SPONSORS")

drv=GraphDatabase.driver(sec("NEO4J_URI"),auth=(sec("NEO4J_USER"),sec("NEO4J_PASSWORD")))
with drv.session() as ses:
    ses.run("MATCH (n) DETACH DELETE n")
    ses.run("CREATE INDEX bft_name IF NOT EXISTS FOR (n:Entity) ON (n.name)")
    for c,rows in d.items():
        if c not in ENTITY: continue
        lbl=":".join(["Entity"]+LABELS[c])
        for r in rows:
            nm=r.get("name","").strip()
            if nm: ses.run(f"MERGE (n:{lbl} {{name:$n}}) SET n.category=$c,n.stance=$s,n.allianceScore=$a",n=nm,c=c,s=r.get("stance",""),a=r.get("allianceScore",""))
    byt={}
    for (x,y),ty in edges.items(): byt.setdefault(ty,[]).append({"a":x,"b":y})
    for ty,ps in byt.items():
        ses.run(f"UNWIND $ps AS p MATCH (a:Entity{{name:p.a}}),(b:Entity{{name:p.b}}) MERGE (a)-[:{ty}]->(b)",ps=ps)
    print(f"TOTAL EDGES: {len(edges)} (was ~420)")
    for ty,n in Counter(edges.values()).most_common(): print(f"   {ty:<14s} {n}")
    conn=ses.run("MATCH (n:Entity) WITH count(n) AS t MATCH (m:Entity)-[]-() RETURN t, count(DISTINCT m) AS c").single()
    print(f"\nconnected: {conn['c']}/{conn['t']} nodes (was 395/899)")
drv.close()
