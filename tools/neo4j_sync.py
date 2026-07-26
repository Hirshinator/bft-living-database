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

        # 2. relationships from the `related` field (comma/&/;-separated names)
        edges = 0
        for cat, rows in d.items():
            if cat not in ENTITY:
                continue
            for r in rows:
                src = r.get("name", "").strip()
                rel = str(r.get("related", ""))
                if not src or not rel:
                    continue
                for frag in re.split(r"[;,]| and | & ", rel):
                    frag = re.sub(r"\(.*?\)", "", frag).strip()
                    if len(frag) < 3:
                        continue
                    tgt = name_index.get(frag.lower())
                    if tgt and tgt != src:
                        ses.run(
                            "MATCH (a:Entity {name:$a}), (b:Entity {name:$b}) "
                            "MERGE (a)-[:CONNECTED_TO]->(b)", a=src, b=tgt)
                        edges += 1
        print(f"relationship edges (from `related`): {edges}")

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
