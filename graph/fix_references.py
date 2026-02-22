#!/usr/bin/env python3
"""Fix REFERENCES edges between Insights and NatalPlacements."""
from neo4j import GraphDatabase

d = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "selene_gnosis"))

ALL_NAMES = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
             "Uranus", "Neptune", "Pluto", "ASC", "MC", "Node"]

with d.session() as s:
    insights = list(s.run("MATCH (i:Insight) RETURN i.id AS id, i.chart AS chart, i.text AS text"))
    ref_count = 0
    for ins in insights:
        text_lower = (ins["text"] or "").lower()
        chart = ins["chart"]
        for pname in ALL_NAMES:
            if pname.lower() in text_lower:
                pid = f"{chart}_{pname.lower()}"
                exists = s.run("MATCH (np:NatalPlacement {id: $pid}) RETURN count(np) as c", pid=pid).single()["c"]
                if exists:
                    s.run("""
                        MATCH (i:Insight {id: $iid}), (np:NatalPlacement {id: $pid})
                        MERGE (i)-[:REFERENCES]->(np)
                    """, iid=ins["id"], pid=pid)
                    ref_count += 1
                    print(f"  {ins['id']} -> {pid}")
    
    total = s.run("MATCH ()-[r:REFERENCES]->() RETURN count(r) as c").single()["c"]
    print(f"\nCreated {ref_count} REFERENCES edges (total: {total})")

d.close()
