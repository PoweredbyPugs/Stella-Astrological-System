"""
Neo4j graph tools for Stella MCP server.
Provides traversal, chain walking, and novel interpretation generation.
"""

import json
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "selene_gnosis")

_driver = None

def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    return _driver


def traverse_chain(chart_name: str, planet: str) -> dict:
    """Walk the depositor chain from a planet to its terminus."""
    driver = get_driver()
    with driver.session() as s:
        # Walk the full chain
        result = s.run("""
            MATCH path = (start:NatalPlacement {chart: $chart, planet: $planet})
                         -[:DEPOSITS_TO*1..10]->(terminus)
            WHERE NOT (terminus)-[:DEPOSITS_TO]->()
            RETURN [n IN nodes(path) | {
                planet: n.planet, sign: n.sign, degree: n.degree,
                house: n.house, dignity_score: n.dignity_score,
                condition: n.condition
            }] AS chain,
            terminus.planet AS final_dispositor
        """, chart=chart_name, planet=planet)
        
        record = result.single()
        if not record:
            # Planet might be the terminus itself (domicile)
            r2 = s.run("""
                MATCH (p:NatalPlacement {chart: $chart, planet: $planet})
                RETURN p.planet AS planet, p.sign AS sign, p.condition AS condition
            """, chart=chart_name, planet=planet).single()
            if r2:
                return {
                    "chain": [{"planet": r2["planet"], "sign": r2["sign"], "condition": r2["condition"]}],
                    "final_dispositor": r2["planet"],
                    "note": "Planet is in domicile — chain terminus"
                }
            return {"error": f"Planet {planet} not found in chart {chart_name}"}
        
        return {
            "chain": record["chain"],
            "final_dispositor": record["final_dispositor"],
            "length": len(record["chain"])
        }


def find_receptions(chart_name: str) -> list:
    """Find all mutual receptions in a chart."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (a:NatalPlacement {chart: $chart})-[r:MUTUAL_RECEPTION]->(b:NatalPlacement {chart: $chart})
            WHERE a.planet < b.planet
            RETURN a.planet AS planet1, a.sign AS sign1, a.dignity_score AS score1,
                   b.planet AS planet2, b.sign AS sign2, b.dignity_score AS score2,
                   r.type AS reception_type
        """, chart=chart_name)
        
        return [dict(r) for r in result]


def get_aspect_network(chart_name: str, planet: str = None) -> list:
    """Get natal aspect network for a chart, optionally filtered to one planet."""
    driver = get_driver()
    with driver.session() as s:
        if planet:
            result = s.run("""
                MATCH (a:NatalPlacement {chart: $chart, planet: $planet})
                      -[r:NATAL_ASPECT]-(b:NatalPlacement {chart: $chart})
                RETURN a.planet AS planet1, b.planet AS planet2,
                       r.type AS aspect_type, r.orb AS orb, r.angle AS angle
                ORDER BY r.orb
            """, chart=chart_name, planet=planet)
        else:
            result = s.run("""
                MATCH (a:NatalPlacement {chart: $chart})-[r:NATAL_ASPECT]->(b:NatalPlacement {chart: $chart})
                RETURN a.planet AS planet1, b.planet AS planet2,
                       r.type AS aspect_type, r.orb AS orb, r.angle AS angle
                ORDER BY r.orb
            """, chart=chart_name)
        
        return [dict(r) for r in result]


def get_midpoint_pictures(chart_name: str, planet: str = None, max_orb: float = 1.0) -> list:
    """Get midpoint pictures for a chart, optionally filtered."""
    driver = get_driver()
    with driver.session() as s:
        if planet:
            result = s.run("""
                MATCH (p:NatalPlacement {chart: $chart, planet: $planet})
                      -[r:MIDPOINT_ACTIVATES]->(a1:NatalPlacement {chart: $chart})
                WHERE r.orb <= $orb
                RETURN p.planet AS planet, r.axis1 AS axis1, r.axis2 AS axis2, r.orb AS orb
                ORDER BY r.orb
            """, chart=chart_name, planet=planet, orb=max_orb)
        else:
            result = s.run("""
                MATCH (p:NatalPlacement {chart: $chart})
                      -[r:MIDPOINT_ACTIVATES]->(a1:NatalPlacement {chart: $chart})
                WHERE r.orb <= $orb
                RETURN p.planet AS planet, r.axis1 AS axis1, r.axis2 AS axis2, r.orb AS orb
                ORDER BY r.orb
            """, chart=chart_name, orb=max_orb)
        
        return [dict(r) for r in result]


def chart_as_graph(chart_name: str) -> dict:
    """Return complete chart structure as a graph object."""
    driver = get_driver()
    with driver.session() as s:
        # Chart metadata
        chart = s.run("""
            MATCH (c:Chart {name: $name})
            RETURN c
        """, name=chart_name).single()
        
        if not chart:
            return {"error": f"Chart {chart_name} not found"}
        
        chart_data = dict(chart["c"])
        
        # All placements
        placements = s.run("""
            MATCH (c:Chart {name: $name})-[:HAS_PLACEMENT]->(np:NatalPlacement)
            RETURN np
            ORDER BY np.longitude
        """, name=chart_name)
        placement_list = [dict(r["np"]) for r in placements]
        
        # All depositor edges
        deps = s.run("""
            MATCH (a:NatalPlacement {chart: $name})-[:DEPOSITS_TO]->(b:NatalPlacement {chart: $name})
            RETURN a.planet AS from, b.planet AS to
        """, name=chart_name)
        dep_list = [dict(r) for r in deps]
        
        # All aspects
        aspects = s.run("""
            MATCH (a:NatalPlacement {chart: $name})-[r:NATAL_ASPECT]->(b:NatalPlacement {chart: $name})
            RETURN a.planet AS planet1, b.planet AS planet2, r.type AS type, r.orb AS orb
            ORDER BY r.orb
        """, name=chart_name)
        aspect_list = [dict(r) for r in aspects]
        
        # Receptions
        recs = find_receptions(chart_name)
        
        # Insights
        insights = s.run("""
            MATCH (c:Chart {name: $name})-[:HAS_INSIGHT]->(i:Insight)
            RETURN i.text AS text, i.technique AS technique, i.rating AS rating, i.validated AS validated
            ORDER BY i.rating DESC
        """, name=chart_name)
        insight_list = [dict(r) for r in insights]
        
        return {
            "chart": chart_data,
            "placements": placement_list,
            "depositor_chain": dep_list,
            "aspects": aspect_list,
            "mutual_receptions": recs,
            "insights": insight_list
        }


def walk_interpretation(chart_name: str, planet: str) -> dict:
    """
    Walk the graph from a natal placement, collecting everything connected:
    - The placement itself (sign, house, dignity)
    - Its depositor chain
    - All aspects it makes
    - Midpoint pictures it participates in
    - Which sign it occupies and what the ontology says about that sign
    - Relevant interpretations from the knowledge base
    - Connected insights from the emergent triad
    
    Returns a structured object for synthesis.
    """
    driver = get_driver()
    with driver.session() as s:
        # The placement
        placement = s.run("""
            MATCH (np:NatalPlacement {chart: $chart, planet: $planet})
            RETURN np
        """, chart=chart_name, planet=planet).single()
        
        if not placement:
            return {"error": f"{planet} not found in {chart_name}"}
        
        p = dict(placement["np"])
        
        # Depositor chain
        chain = traverse_chain(chart_name, planet)
        
        # Aspects
        aspects = get_aspect_network(chart_name, planet)
        
        # Midpoint pictures
        midpoints = get_midpoint_pictures(chart_name, planet, max_orb=1.0)
        
        # Sign properties from ontology
        sign_data = s.run("""
            MATCH (np:NatalPlacement {chart: $chart, planet: $planet})-[:OCCUPIES_SIGN]->(sign:Sign)
            OPTIONAL MATCH (sign)-[:OF_ELEMENT]->(elem:Element)
            OPTIONAL MATCH (sign)-[:OF_MODALITY]->(mod:Modality)
            OPTIONAL MATCH (ruler:Planet)-[:RULES]->(sign)
            OPTIONAL MATCH (exalted:Planet)-[:EXALTED_IN]->(sign)
            RETURN sign.name AS sign, elem.name AS element, mod.name AS modality,
                   ruler.name AS ruler, exalted.name AS exalted_planet
        """, chart=chart_name, planet=planet).single()
        
        # House info
        house_data = s.run("""
            MATCH (np:NatalPlacement {chart: $chart, planet: $planet})-[:OCCUPIES_HOUSE]->(h:House)
            RETURN h.name AS house_name
        """, chart=chart_name, planet=planet).single()
        
        # Decan and Term
        decan_data = s.run("""
            MATCH (np:NatalPlacement {chart: $chart, planet: $planet})-[:IN_DECAN]->(d:Decan)
            RETURN d.label AS decan, d.face_ruler AS face_ruler
        """, chart=chart_name, planet=planet).single()
        
        term_data = s.run("""
            MATCH (np:NatalPlacement {chart: $chart, planet: $planet})-[:IN_TERM]->(t:Term)
            RETURN t.label AS term, t.ruler AS term_ruler
        """, chart=chart_name, planet=planet).single()
        
        # Relevant interpretations — prefer INTERPRETS_PLACEMENT (planet-in-sign specific)
        interps = s.run("""
            MATCH (i:Interpretation)-[r:INTERPRETS_PLACEMENT {planet: $planet, sign: $sign}]->(p:Planet)
            RETURN i.text AS text, i.source_title AS source, i.trust_tier AS tier
            ORDER BY i.trust_tier DESC
            LIMIT 5
        """, planet=planet, sign=p.get("sign", ""))
        interp_list_specific = [dict(r) for r in interps]
        
        # Fallback to general DESCRIBES if no specific found
        if not interp_list_specific:
            interps = s.run("""
                MATCH (np:NatalPlacement {chart: $chart, planet: $planet})-[:IS_PLANET]->(planet:Planet)
                MATCH (np)-[:OCCUPIES_SIGN]->(sign:Sign)
                MATCH (i:Interpretation)-[:DESCRIBES]->(planet)
                WHERE (i)-[:DESCRIBES]->(sign)
                RETURN i.text AS text, i.source_title AS source, i.trust_tier AS tier
                LIMIT 5
            """, chart=chart_name, planet=planet)
            interp_list_specific = [dict(r) for r in interps]
        
        # Connected insights
        insights = s.run("""
            MATCH (i:Insight {chart: $chart})-[:REFERENCES]->(np:NatalPlacement {chart: $chart, planet: $planet})
            RETURN i.text AS text, i.rating AS rating, i.validated AS validated, i.technique AS technique
        """, chart=chart_name, planet=planet)
        insight_list = [dict(r) for r in insights]
        
        # Who deposits TO this planet?
        receives_from = s.run("""
            MATCH (other:NatalPlacement {chart: $chart})-[:DEPOSITS_TO]->(np:NatalPlacement {chart: $chart, planet: $planet})
            RETURN other.planet AS planet, other.sign AS sign, other.dignity_score AS score
        """, chart=chart_name, planet=planet)
        receives_list = [dict(r) for r in receives_from]
        
        return {
            "placement": p,
            "sign_properties": dict(sign_data) if sign_data else {},
            "house": dict(house_data) if house_data else {},
            "decan": dict(decan_data) if decan_data else {},
            "term": dict(term_data) if term_data else {},
            "depositor_chain": chain,
            "receives_deposits_from": receives_list,
            "aspects": aspects,
            "midpoint_pictures": midpoints,
            "interpretations": interp_list_specific,
            "insights": insight_list
        }


def query_graph(cypher: str, params: dict = None) -> list:
    """Execute raw Cypher query against the graph."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(cypher, **(params or {}))
        return [dict(r) for r in result]


def compare_charts(chart1: str, chart2: str) -> dict:
    """Compare two charts — find shared sign placements, cross-aspects, synastry."""
    driver = get_driver()
    with driver.session() as s:
        # Shared signs
        shared = s.run("""
            MATCH (a:NatalPlacement {chart: $c1})-[:OCCUPIES_SIGN]->(sign:Sign)
                  <-[:OCCUPIES_SIGN]-(b:NatalPlacement {chart: $c2})
            WHERE a.is_planet = true AND b.is_planet = true
            RETURN sign.name AS sign, a.planet AS planet1, b.planet AS planet2,
                   a.degree AS degree1, b.degree AS degree2
            ORDER BY sign.name
        """, c1=chart1, c2=chart2)
        shared_list = [dict(r) for r in shared]
        
        # Cross-chart aspects (planets in same sign within orb)
        cross_aspects = []
        p1s = s.run("MATCH (p:NatalPlacement {chart: $c}) WHERE p.is_planet = true RETURN p", c=chart1)
        p2s = s.run("MATCH (p:NatalPlacement {chart: $c}) WHERE p.is_planet = true RETURN p", c=chart2)
        
        placements1 = [dict(r["p"]) for r in p1s]
        placements2 = [dict(r["p"]) for r in p2s]
        
        from graph.seed_charts import compute_aspect
        for p1 in placements1:
            for p2 in placements2:
                asp = compute_aspect(p1["longitude"], p2["longitude"])
                if asp:
                    cross_aspects.append({
                        f"{chart1}": p1["planet"],
                        f"{chart2}": p2["planet"],
                        **asp
                    })
        cross_aspects.sort(key=lambda x: x["orb"])
        
        # Shared final dispositors
        fd1 = s.run("MATCH (c:Chart {name: $n}) RETURN c.final_dispositor AS fd", n=chart1).single()
        fd2 = s.run("MATCH (c:Chart {name: $n}) RETURN c.final_dispositor AS fd", n=chart2).single()
        
        return {
            "shared_signs": shared_list,
            "cross_aspects": cross_aspects[:20],
            "final_dispositors": {chart1: fd1["fd"] if fd1 else None, chart2: fd2["fd"] if fd2 else None}
        }


def graph_stats() -> dict:
    """Return current graph statistics."""
    driver = get_driver()
    with driver.session() as s:
        stats = {}
        for label in ["Chart", "NatalPlacement", "Insight", "Planet", "Sign", "House", "Interpretation"]:
            stats[label] = s.run(f"MATCH (n:{label}) RETURN count(n) as c").single()["c"]
        for rel in ["DEPOSITS_TO", "NATAL_ASPECT", "MIDPOINT_ACTIVATES", "MUTUAL_RECEPTION",
                     "DESCRIBES", "HAS_INSIGHT", "REFERENCES"]:
            stats[rel] = s.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) as c").single()["c"]
        
        charts = s.run("MATCH (c:Chart) RETURN c.name AS name ORDER BY c.name")
        stats["chart_names"] = [r["name"] for r in charts]
        
        return stats
