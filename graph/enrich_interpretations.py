#!/usr/bin/env python3
"""
Enrich the knowledge graph by creating structured edges between
Interpretation nodes and the ontology (Planet, Sign, House nodes).

The DESCRIBES edges already exist but they're flat — an interpretation
"describes" Mars AND Capricorn, but there's no edge saying it specifically
discusses Mars IN Capricorn vs Mars ASPECTING something in Capricorn.

This script:
1. Creates INTERPRETS_PLACEMENT edges (interpretation about planet-in-sign)
2. Creates INTERPRETS_ASPECT edges (interpretation about aspect between planets)
3. Creates INTERPRETS_HOUSE edges (interpretation about planet-in-house)
4. Adds Decan nodes and links interpretations to specific decans
5. Links interpretations to techniques (ZR, profections, etc.)
"""

from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "selene_gnosis")

SIGN_ORDER = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
              "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

ALL_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
               "Uranus", "Neptune", "Pluto"]


def create_decan_nodes(session):
    """Create 36 Decan nodes linked to their signs."""
    DECAN_RULERS = {
        # Chaldean order decans
        "Aries": ["Mars", "Sun", "Venus"],
        "Taurus": ["Mercury", "Moon", "Saturn"],
        "Gemini": ["Jupiter", "Mars", "Sun"],
        "Cancer": ["Venus", "Mercury", "Moon"],
        "Leo": ["Saturn", "Jupiter", "Mars"],
        "Virgo": ["Sun", "Venus", "Mercury"],
        "Libra": ["Moon", "Saturn", "Jupiter"],
        "Scorpio": ["Mars", "Sun", "Venus"],
        "Sagittarius": ["Mercury", "Moon", "Saturn"],
        "Capricorn": ["Jupiter", "Mars", "Sun"],
        "Aquarius": ["Venus", "Mercury", "Moon"],
        "Pisces": ["Saturn", "Jupiter", "Mars"],
    }
    
    count = 0
    for sign, rulers in DECAN_RULERS.items():
        for i, ruler in enumerate(rulers):
            decan_num = i + 1
            start_deg = i * 10
            end_deg = start_deg + 10
            decan_id = f"{sign.lower()}_{decan_num}"
            
            session.run("""
                MERGE (d:Decan {id: $id})
                SET d.sign = $sign, d.number = $num,
                    d.start_degree = $start, d.end_degree = $end,
                    d.face_ruler = $ruler,
                    d.label = $label
            """, id=decan_id, sign=sign, num=decan_num,
                 start=start_deg, end=end_deg, ruler=ruler,
                 label=f"{sign} {['I', 'II', 'III'][i]}")
            
            # Link to sign
            session.run("""
                MATCH (d:Decan {id: $id}), (s:Sign {name: $sign})
                MERGE (d)-[:OF_SIGN]->(s)
            """, id=decan_id, sign=sign)
            
            # Link to face ruler planet
            session.run("""
                MATCH (d:Decan {id: $id}), (p:Planet {name: $ruler})
                MERGE (d)-[:FACE_RULER]->(p)
            """, id=decan_id, ruler=ruler)
            
            count += 1
    
    print(f"Created {count} Decan nodes with OF_SIGN and FACE_RULER edges")


def create_term_nodes(session):
    """Create Term (bound) nodes — Egyptian terms."""
    EGYPTIAN_TERMS = {
        "Aries": [("Jupiter", 0, 6), ("Venus", 6, 12), ("Mercury", 12, 20), ("Mars", 20, 25), ("Saturn", 25, 30)],
        "Taurus": [("Venus", 0, 8), ("Mercury", 8, 14), ("Jupiter", 14, 22), ("Saturn", 22, 27), ("Mars", 27, 30)],
        "Gemini": [("Mercury", 0, 6), ("Jupiter", 6, 12), ("Venus", 12, 17), ("Mars", 17, 24), ("Saturn", 24, 30)],
        "Cancer": [("Mars", 0, 7), ("Venus", 7, 13), ("Mercury", 13, 19), ("Jupiter", 19, 26), ("Saturn", 26, 30)],
        "Leo": [("Jupiter", 0, 6), ("Venus", 6, 11), ("Saturn", 11, 18), ("Mercury", 18, 24), ("Mars", 24, 30)],
        "Virgo": [("Mercury", 0, 7), ("Venus", 7, 17), ("Jupiter", 17, 21), ("Mars", 21, 28), ("Saturn", 28, 30)],
        "Libra": [("Saturn", 0, 6), ("Mercury", 6, 14), ("Jupiter", 14, 21), ("Venus", 21, 28), ("Mars", 28, 30)],
        "Scorpio": [("Mars", 0, 7), ("Venus", 7, 11), ("Mercury", 11, 19), ("Jupiter", 19, 24), ("Saturn", 24, 30)],
        "Sagittarius": [("Jupiter", 0, 12), ("Venus", 12, 17), ("Mercury", 17, 21), ("Saturn", 21, 26), ("Mars", 26, 30)],
        "Capricorn": [("Mercury", 0, 7), ("Jupiter", 7, 14), ("Venus", 14, 22), ("Saturn", 22, 26), ("Mars", 26, 30)],
        "Aquarius": [("Mercury", 0, 7), ("Venus", 7, 13), ("Jupiter", 13, 20), ("Mars", 20, 25), ("Saturn", 25, 30)],
        "Pisces": [("Venus", 0, 12), ("Jupiter", 12, 16), ("Mercury", 16, 19), ("Mars", 19, 28), ("Saturn", 28, 30)],
    }
    
    count = 0
    for sign, terms in EGYPTIAN_TERMS.items():
        for ruler, start, end in terms:
            term_id = f"term_{sign.lower()}_{start}_{end}"
            session.run("""
                MERGE (t:Term {id: $id})
                SET t.sign = $sign, t.ruler = $ruler,
                    t.start_degree = $start, t.end_degree = $end,
                    t.label = $label
            """, id=term_id, sign=sign, ruler=ruler,
                 start=start, end=end,
                 label=f"{ruler}'s term in {sign} ({start}°-{end}°)")
            
            session.run("""
                MATCH (t:Term {id: $id}), (s:Sign {name: $sign})
                MERGE (t)-[:OF_SIGN]->(s)
            """, id=term_id, sign=sign)
            
            session.run("""
                MATCH (t:Term {id: $id}), (p:Planet {name: $ruler})
                MERGE (t)-[:TERM_RULER]->(p)
            """, id=term_id, ruler=ruler)
            
            count += 1
    
    print(f"Created {count} Term nodes with OF_SIGN and TERM_RULER edges")


def link_placements_to_decans(session):
    """Link NatalPlacement nodes to their Decan."""
    result = session.run("""
        MATCH (np:NatalPlacement)
        WHERE np.is_planet = true
        RETURN np.id AS id, np.sign AS sign, np.decan AS decan
    """)
    
    count = 0
    for r in result:
        decan_id = f"{r['sign'].lower()}_{r['decan']}"
        session.run("""
            MATCH (np:NatalPlacement {id: $npid}), (d:Decan {id: $did})
            MERGE (np)-[:IN_DECAN]->(d)
        """, npid=r["id"], did=decan_id)
        count += 1
    
    print(f"Linked {count} placements to decans")


def link_placements_to_terms(session):
    """Link NatalPlacement nodes to their Egyptian Term."""
    result = session.run("""
        MATCH (np:NatalPlacement)
        WHERE np.is_planet = true
        RETURN np.id AS id, np.sign AS sign, np.degree AS degree
    """)
    
    count = 0
    for r in result:
        sign = r["sign"]
        degree = r["degree"]
        # Find the term
        term = session.run("""
            MATCH (t:Term {sign: $sign})
            WHERE t.start_degree <= $deg AND t.end_degree > $deg
            RETURN t.id AS id
        """, sign=sign, deg=degree).single()
        
        if term:
            session.run("""
                MATCH (np:NatalPlacement {id: $npid}), (t:Term {id: $tid})
                MERGE (np)-[:IN_TERM]->(t)
            """, npid=r["id"], tid=term["id"])
            count += 1
    
    print(f"Linked {count} placements to terms")


def enrich_interpretation_edges(session):
    """
    For interpretations that DESCRIBE both a Planet and a Sign,
    create an INTERPRETS_PLACEMENT edge indicating planet-in-sign interpretation.
    """
    # Find interpretations linked to both a planet and a sign
    result = session.run("""
        MATCH (i:Interpretation)-[:DESCRIBES]->(p:Planet)
        MATCH (i)-[:DESCRIBES]->(s:Sign)
        RETURN i.chunk_id AS chunk_id, p.name AS planet, s.name AS sign
    """)
    
    records = list(result)
    count = 0
    for r in records:
        session.run("""
            MATCH (i:Interpretation {chunk_id: $cid})
            MATCH (p:Planet {name: $planet})
            MATCH (s:Sign {name: $sign})
            MERGE (i)-[:INTERPRETS_PLACEMENT {planet: $planet, sign: $sign}]->(p)
        """, cid=r["chunk_id"], planet=r["planet"], sign=r["sign"])
        count += 1
    
    print(f"Created {count} INTERPRETS_PLACEMENT edges")
    
    # Interpretations linked to planet + house
    result = session.run("""
        MATCH (i:Interpretation)-[:DESCRIBES]->(p:Planet)
        MATCH (i)-[:DESCRIBES]->(h:House)
        RETURN i.chunk_id AS chunk_id, p.name AS planet, h.name AS house
    """)
    
    records = list(result)
    count = 0
    for r in records:
        session.run("""
            MATCH (i:Interpretation {chunk_id: $cid})
            MATCH (p:Planet {name: $planet})
            MERGE (i)-[:INTERPRETS_HOUSE {planet: $planet, house: $house}]->(p)
        """, cid=r["chunk_id"], planet=r["planet"], house=r["house"])
        count += 1
    
    print(f"Created {count} INTERPRETS_HOUSE edges")
    
    # Interpretations linked to two planets (aspect interpretations)
    result = session.run("""
        MATCH (i:Interpretation)-[:DESCRIBES]->(p1:Planet)
        MATCH (i)-[:DESCRIBES]->(p2:Planet)
        WHERE p1.name < p2.name
        MATCH (i)-[:DESCRIBES]->(a:Aspect)
        RETURN i.chunk_id AS chunk_id, p1.name AS planet1, p2.name AS planet2, a.name AS aspect
    """)
    
    records = list(result)
    count = 0
    for r in records:
        session.run("""
            MATCH (i:Interpretation {chunk_id: $cid})
            MATCH (p1:Planet {name: $p1})
            MERGE (i)-[:INTERPRETS_ASPECT {planet1: $p1, planet2: $p2, aspect: $aspect}]->(p1)
        """, cid=r["chunk_id"], p1=r["planet1"], p2=r["planet2"], aspect=r["aspect"])
        count += 1
    
    print(f"Created {count} INTERPRETS_ASPECT edges")


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    driver.verify_connectivity()
    print("Connected to Neo4j\n")
    
    with driver.session() as s:
        # Phase 2a: Create Decan and Term nodes
        print("--- Creating Decan nodes ---")
        create_decan_nodes(s)
        
        print("\n--- Creating Term nodes ---")
        create_term_nodes(s)
        
        # Phase 2b: Link placements to decans and terms
        print("\n--- Linking placements to decans ---")
        link_placements_to_decans(s)
        
        print("\n--- Linking placements to terms ---")
        link_placements_to_terms(s)
        
        # Phase 2c: Enrich interpretation edges
        print("\n--- Enriching interpretation edges ---")
        enrich_interpretation_edges(s)
        
        # Stats
        print("\n--- Final enrichment stats ---")
        for label in ["Decan", "Term"]:
            c = s.run(f"MATCH (n:{label}) RETURN count(n) as c").single()["c"]
            print(f"  {label}: {c}")
        for rel in ["OF_SIGN", "FACE_RULER", "TERM_RULER", "IN_DECAN", "IN_TERM",
                     "INTERPRETS_PLACEMENT", "INTERPRETS_HOUSE", "INTERPRETS_ASPECT"]:
            c = s.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) as c").single()["c"]
            print(f"  [{rel}]: {c}")
        
        total_n = s.run("MATCH (n) RETURN count(n) as c").single()["c"]
        total_r = s.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
        print(f"\n  TOTAL: {total_n} nodes, {total_r} relationships")
    
    driver.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
