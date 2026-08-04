#!/usr/bin/env python3
"""Additive relationship layer: push the BFT database into Neo4j Aura as a graph.

Keeps the live app + Airtable untouched. This mirrors the current data into a
graph so we get degrees-of-separation, bridge-node, cluster, and centrality
queries that CSV/Airtable can't do.

Reads NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD from ~/.bft_secrets:
    NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=xxxxxxxx
Usage: python3 tools/neo4j_sync.py [--wipe]
"""
import os, re, sys, json, subprocess
from neo4j import GraphDatabase

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
HTML = "/Users/andy/Downloads/BFT_Living_Database_6.html"

def secret(k):
    for l in open(os.path.expanduser("~/.bft_secrets")):
        if l.startswith(k + "="):
            return l.split("=", 1)[1].strip()
    sys.exit(f"{k} not in ~/.bft_secrets")

# category -> node labels
LABELS = {
    "influencer": ["Person", "Influencer"], "rising_stars": ["Person", "RisingStar"],
    "swing": ["Person", "Swing"], "nurture": ["Person", "Nurture"],
    "business_leader": ["Person", "BusinessLeader"], "political": ["Person", "Politician"],
    "grassroots_business": ["Person", "Grassroots"], "grassroots_politics": ["Person", "Grassroots"],
    "organization": ["Organization"], "media": ["MediaCompany"],
    "business": ["Company"], "israeli_tech": ["Company", "IsraeliTech"],
    "sponsor": ["Sponsor"], "ecosystem": ["Region"],
}
ENTITY = set(LABELS)

def load():
    s = re.search(r"<script>\n(.*?)\n</script>", open(HTML, encoding="utf-8").read(), re.S).group(1)
    a = s.find("const SEED_DATA"); b = s.find("\n  };", a) + 4
    open("/tmp/_n4j.js", "w").write(
        s[a:b].replace("const SEED_DATA", "var SEED_DATA", 1) + "\nprint(JSON.stringify(SEED_DATA));")
    return json.loads(subprocess.run([JSC, "/tmp/_n4j.js"], capture_output=True, text=True).stdout)

def main():
    d = load()
    drv = GraphDatabase.driver(secret("NEO4J_URI"), auth=(secret("NEO4J_USER"), secret("NEO4J_PASSWORD")))
    with drv.session() as ses:
        ses.run("RETURN 1").single()  # connectivity check
        if "--wipe" in sys.argv:
            ses.run("MATCH (n) DETACH DELETE n"); print("wiped existing graph")
        ses.run("CREATE INDEX bft_name IF NOT EXISTS FOR (n:Entity) ON (n.name)")

        # 1. nodes -- every entity is also :Entity for a shared name index
        name_index = {}
        nodes = 0
        for cat, rows in d.items():
            if cat not in ENTITY:
                continue
            labels = ":".join(["Entity"] + LABELS[cat])
            for r in rows:
                nm = r.get("name", "").strip()
                if not nm:
                    continue
                name_index[nm.lower()] = nm
                ses.run(
                    f"MERGE (n:{labels} {{name:$name}}) "
                    "SET n.category=$cat, n.stance=$stance, n.allianceScore=$score, "
                    "n.platform=$platform, n.bftId=$bftId",
                    name=nm, cat=cat, stance=r.get("stance", ""),
                    score=r.get("allianceScore", ""), platform=str(r.get("platform", ""))[:200],
                    bftId=r.get("bftId", ""))
                nodes += 1
        print(f"nodes: {nodes}")

        # 2. TYPED relationships -- ported from the app's edge derivation so the
        #    graph brain matches the in-app map: org-leader, `related`, and an
        #    evidence-mention scan, each typed by keyword + stance.
        raws = {}  # name -> raw record
        for cat, rows in d.items():
            if cat not in ENTITY:
                continue
            for r in rows:
                nm = r.get("name", "").strip()
                if nm:
                    raws[nm] = (cat, r)

        def is_pro(s): return s == "pro"
        def is_hos(s): return s in ("hostile", "redflag")

        def pair_type(src, a_raw, b_raw):
            t = ((src.get("evidence", "") or "") + " " + (src.get("researchNotes", "") or "")).lower()
            if re.search(r"co-?host", t): return "CO_HOST"
            # partnership/leadership/investment first (stable ties); avoids stray "interview" mislabeling
            if re.search(r"\b(co-?found|founded by|founder|leads?\b|leading|heads?\b|director of|principal|chair(man)?|president of|business partner|partner(ed| with| at)|board (member|of|seat)|initiative|colleague|works (at|for)|invested|invests|backer|portfolio|co-invest|donor|philanthrop)\b", t): return "BUSINESS_PARTNER"
            if re.search(r"\b(guest on|guest of|appeared on|featured on|hosted (him|her|them)|interviewed (him|her|them)|joined .{0,20}on (his|her|the) (show|podcast))\b", t): return "HOST_GUEST"
            if re.search(r"\b(friend|close ally|allied with|befriend)\b", t): return "FRIEND"
            if re.search(r"\b(rival|feud|beef|clash)\b", t): return "RIVAL"
            if re.search(r"\b(client|customer|vendor|retainer|contracted|does work for|hired by)\b", t): return "CLIENT"
            if re.search(r"\b(praised|endorsed|defended|championed|applauded|paid tribute|thanked|shouted out|celebrated|posted positively)\b", t): return "MENTION_POS"
            if re.search(r"\b(attacked|slammed|condemned|denounced|blasted|ripped|called out|smeared|targeted|accused|criticized)\b", t): return "MENTION_NEG"
            sa, sb = a_raw.get("stance"), b_raw.get("stance")
            if is_pro(sa) and is_pro(sb): return "ALLY"
            if is_hos(sa) and is_hos(sb): return "ENEMY"
            if (is_pro(sa) and is_hos(sb)) or (is_hos(sa) and is_pro(sb)): return "ADVERSARY"
            return "ASSOCIATE"

        edges = {}  # (a,b) -> type  (dedup, keep most-specific)
        RANK = {"SAME_ORG": 5, "BUSINESS_PARTNER": 4, "CLIENT": 4, "CO_HOST": 4, "HOST_GUEST": 3,
                "FRIEND": 3, "RIVAL": 3, "ADVERSARY": 2, "ENEMY": 2, "MENTION_NEG": 2,
                "MENTION_POS": 1, "ALLY": 1, "ASSOCIATE": 0}

        def put(a, b, ty):
            if a == b or not a or not b:
                return
            key = tuple(sorted((a, b)))
            if key not in edges or RANK.get(ty, 0) > RANK.get(edges[key], 0):
                edges[key] = ty

        names = list(raws)
        low = {n.lower(): n for n in names}
        # 2a. org/media/business leader -> person works there
        for nm, (cat, r) in raws.items():
            if cat in ("organization", "media", "business"):
                leader = re.sub(r"\(.*?\)", "", str(r.get("leader", "")))
                for frag in re.split(r",|&|\band\b", leader):
                    frag = frag.strip()
                    if len(frag) >= 4 and frag.lower() in low:
                        put(nm, low[frag.lower()], "SAME_ORG")
        # 2b. explicit related -> typed
        for nm, (cat, r) in raws.items():
            for frag in re.split(r"[;,]", str(r.get("related", ""))):
                frag = frag.strip().lower()
                if frag and frag in low and low[frag] != nm:
                    put(nm, low[frag], pair_type(r, r, raws[low[frag]][1]))
        # 2c. evidence-mention scan -> associate (densifies)
        blobs = {nm: (str(r.get("evidence", "")) + " " + str(r.get("researchNotes", "")) + " " + str(r.get("platform", ""))).lower()
                 for nm, (cat, r) in raws.items()}
        pats = [(nm, re.compile(r"(^|[^a-z0-9])" + re.escape(nm.lower()) + r"([^a-z0-9]|$)"))
                for nm in names if len(nm) >= 5]
        for src, blob in blobs.items():
            for tgt, pat in pats:
                if tgt != src and pat.search(blob):
                    put(src, tgt, "ASSOCIATE")

        # write typed edges (batched by type for APOC-free dynamic rel via per-type MERGE)
        by_type = {}
        for (a, b), ty in edges.items():
            by_type.setdefault(ty, []).append({"a": a, "b": b})
        for ty, pairs in by_type.items():
            ses.run(
                f"UNWIND $pairs AS p MATCH (a:Entity {{name:p.a}}), (b:Entity {{name:p.b}}) "
                f"MERGE (a)-[:{ty}]->(b)", pairs=pairs)
        from collections import Counter
        tc = Counter(edges.values())
        print(f"typed relationship edges: {len(edges)}")
        for ty, n in tc.most_common():
            print(f"   {ty:<18s} {n}")

        # 3. demo queries -- prove the graph brain works
        print("\n=== GRAPH BRAIN DEMO ===")
        top = ses.run("MATCH (n:Entity)-[r]-() RETURN n.name AS name, n.category AS cat, count(r) AS deg "
                      "ORDER BY deg DESC LIMIT 10").data()
        print("most-connected nodes (hubs/bridges):")
        for t in top:
            print(f"   {t['deg']:>3} connections  {t['name']} ({t['cat']})")
        comp = ses.run("MATCH (n:Entity) WITH count(n) AS total "
                       "MATCH (m:Entity)-[]-() WITH total, count(DISTINCT m) AS connected "
                       "RETURN total, connected").single()
        print(f"\ngraph: {comp['total']} nodes, {comp['connected']} connected by at least one edge")
    drv.close()
    print("\nNeo4j Aura relationship layer synced.")

if __name__ == "__main__":
    main()
