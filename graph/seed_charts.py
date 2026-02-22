#!/usr/bin/env python3
"""
Seed Neo4j with natal chart subgraphs from Helios stored charts.
Uses /chart/:name endpoint which returns full computed data including depositor chains.
"""

import json
import math
from pathlib import Path
from neo4j import GraphDatabase
import requests

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "selene_gnosis")
HELIOS = "http://baratie:3000"
CHART_DIR = Path(__file__).parent.parent / "charts"

ASPECT_TYPES = {0: ("conjunction", 8), 60: ("sextile", 6), 90: ("square", 7), 120: ("trine", 8), 180: ("opposition", 8)}
ALL_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
ANGLES = ["ASC", "MC", "DSC", "IC"]
ANGLE_MAP = {"ascendant": "ASC", "midheaven": "MC", "descendant": "DSC", "imumCoeli": "IC"}

HOUSE_NAMES = {
    1: "Hour-Marker", 2: "Gate of Hades", 3: "Goddess", 4: "Hypogeion",
    5: "Good Fortune", 6: "Bad Fortune", 7: "Setting", 8: "Idle Place",
    9: "God", 10: "Midheaven", 11: "Good Spirit", 12: "Bad Spirit"
}


def compute_aspect(lon1, lon2):
    diff = abs(lon1 - lon2)
    if diff > 180: diff = 360 - diff
    for exact, (name, orb) in ASPECT_TYPES.items():
        if abs(diff - exact) <= orb:
            return {"type": name, "angle": exact, "orb": round(abs(diff - exact), 2)}
    return None


def midpoint_90(lon1, lon2):
    p1, p2 = lon1 % 90, lon2 % 90
    mp = (p1 + p2) / 2
    if abs(p1 - p2) > 45: mp = (mp + 45) % 90
    return mp


def get_helios_chart(name):
    try:
        r = requests.get(f"{HELIOS}/chart/{name}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  Helios error for {name}: {e}")
        return None


def seed_chart(driver, chart_name):
    print(f"\n{'='*60}\nSeeding: {chart_name}\n{'='*60}")
    
    data = get_helios_chart(chart_name)
    if not data:
        return False
    
    planets = data.get("planets", [])
    angles = data.get("angles", {})
    depositors = data.get("depositors", {})
    lots = data.get("lots", {})
    bd = data.get("birthData", {})
    sect_info = data.get("sect", {})
    
    # Build unified placement list
    placements = []
    for p in planets:
        name = p["name"]
        lon = float(p["longitude"])
        sign = p["sign"]
        deg = float(p["degreeInSign"])
        house = p.get("house", 0)
        retro = p.get("isRetrograde", False)
        
        dig = p.get("dignities") or {}
        score = dig.get("score", 0) if dig else 0
        condition = dig.get("condition", "neutral") if dig else "neutral"
        
        placements.append({
            "name": name, "longitude": lon, "sign": sign, "degree": deg,
            "house": house, "retrograde": retro, "dignity_score": score,
            "condition": condition, "decan": int(deg // 10) + 1,
            "is_planet": True
        })
    
    for angle_key, angle_data in angles.items():
        friendly = ANGLE_MAP.get(angle_key, angle_key)
        placements.append({
            "name": friendly, "longitude": float(angle_data["longitude"]),
            "sign": angle_data["sign"], "degree": float(angle_data["degreeInSign"]),
            "house": 0, "retrograde": False, "dignity_score": 0,
            "condition": "angle", "decan": int(float(angle_data["degreeInSign"]) // 10) + 1,
            "is_planet": False
        })
    
    # Add lots
    for lot_name, lot_data in lots.items():
        friendly = f"Lot_{lot_name.title()}"
        placements.append({
            "name": friendly, "longitude": float(lot_data["longitude"]),
            "sign": lot_data["sign"], "degree": float(lot_data["degreeInSign"]),
            "house": 0, "retrograde": False, "dignity_score": 0,
            "condition": "lot", "decan": int(float(lot_data["degreeInSign"]) // 10) + 1,
            "is_planet": False
        })
    
    # Depositor chains from Helios
    chains = depositors.get("chains", {})
    final_dispositor = depositors.get("finalDispositor", depositors.get("final_dispositor"))
    
    # Compute aspects
    planet_placements = [p for p in placements if p["name"] in ALL_PLANETS]
    natal_aspects = []
    for i, p1 in enumerate(planet_placements):
        for p2 in planet_placements[i+1:]:
            asp = compute_aspect(p1["longitude"], p2["longitude"])
            if asp:
                natal_aspects.append({"planet1": p1["name"], "planet2": p2["name"], **asp})
    
    # Compute midpoint pictures (90° dial, ≤1.0°)
    all_for_midpoints = [p for p in placements if p["name"] in ALL_PLANETS + ANGLES]
    midpoint_pictures = []
    for i, p1 in enumerate(all_for_midpoints):
        for j, p2 in enumerate(all_for_midpoints[i+1:], i+1):
            mp = midpoint_90(p1["longitude"], p2["longitude"])
            for p3 in all_for_midpoints:
                if p3["name"] in (p1["name"], p2["name"]): continue
                p3_90 = p3["longitude"] % 90
                diff = abs(p3_90 - mp)
                if diff > 45: diff = 90 - diff
                if diff <= 1.5:  # slightly wider for storage, filter at query time
                    midpoint_pictures.append({
                        "planet": p3["name"], "axis1": p1["name"],
                        "axis2": p2["name"], "orb": round(diff, 3)
                    })
    midpoint_pictures.sort(key=lambda x: x["orb"])
    
    # Check mutual receptions from Helios depositor data
    receptions = []
    planet_signs = {p["name"]: p["sign"] for p in planet_placements}
    RULERSHIPS = {"Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
                  "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
                  "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"}
    EXALTATIONS = {"Aries": "Sun", "Taurus": "Moon", "Cancer": "Jupiter", "Virgo": "Mercury",
                   "Libra": "Saturn", "Capricorn": "Mars", "Pisces": "Venus"}
    
    names = list(planet_signs.keys())
    for i, p1 in enumerate(names):
        for p2 in names[i+1:]:
            s1, s2 = planet_signs[p1], planet_signs[p2]
            if RULERSHIPS.get(s1) == p2 and RULERSHIPS.get(s2) == p1:
                receptions.append({"p1": p1, "p2": p2, "type": "domicile"})
            if EXALTATIONS.get(s1) == p2 and EXALTATIONS.get(s2) == p1:
                receptions.append({"p1": p1, "p2": p2, "type": "exaltation"})
            if (RULERSHIPS.get(s1) == p2 and EXALTATIONS.get(s2) == p1) or \
               (EXALTATIONS.get(s1) == p2 and RULERSHIPS.get(s2) == p1):
                receptions.append({"p1": p1, "p2": p2, "type": "mixed"})
    
    # Write to Neo4j
    with driver.session() as s:
        # Chart node
        s.run("""
            MERGE (c:Chart {name: $name})
            SET c.date = $date, c.time = $time, c.timezone = $tz,
                c.latitude = $lat, c.longitude = $lon,
                c.final_dispositor = $fd,
                c.day_chart = $day_chart,
                c.sect = $sect
        """, name=chart_name, date=bd.get("date", ""), time=bd.get("time", ""),
             tz=bd.get("timezone", ""), lat=bd.get("location", {}).get("latitude", 0),
             lon=bd.get("location", {}).get("longitude", 0),
             fd=final_dispositor or "",
             day_chart=sect_info.get("isDayChart", True),
             sect=sect_info.get("sect", "day"))
        
        # NatalPlacement nodes
        for p in placements:
            pid = f"{chart_name}_{p['name'].lower().replace(' ', '_')}"
            s.run("""
                MERGE (np:NatalPlacement {id: $id})
                SET np.planet = $planet, np.chart = $chart,
                    np.longitude = $lon, np.sign = $sign, np.degree = $degree,
                    np.house = $house, np.retrograde = $retro,
                    np.dignity_score = $score, np.condition = $condition,
                    np.decan = $decan, np.is_planet = $is_planet
            """, id=pid, planet=p["name"], chart=chart_name,
                 lon=p["longitude"], sign=p["sign"], degree=p["degree"],
                 house=p["house"], retro=p["retrograde"],
                 score=p["dignity_score"], condition=p["condition"],
                 decan=p["decan"], is_planet=p["is_planet"])
            
            # Chart -> Placement
            s.run("""
                MATCH (c:Chart {name: $chart}), (np:NatalPlacement {id: $id})
                MERGE (c)-[:HAS_PLACEMENT]->(np)
            """, chart=chart_name, id=pid)
            
            # Placement -> Sign
            s.run("""
                MATCH (np:NatalPlacement {id: $id}), (sign:Sign {name: $sign})
                MERGE (np)-[:OCCUPIES_SIGN]->(sign)
            """, id=pid, sign=p["sign"])
            
            # Placement -> House
            if p["house"] > 0:
                hname = HOUSE_NAMES.get(p["house"])
                if hname:
                    s.run("""
                        MATCH (np:NatalPlacement {id: $id}), (h:House {name: $house})
                        MERGE (np)-[:OCCUPIES_HOUSE]->(h)
                    """, id=pid, house=hname)
            
            # Placement -> Planet ontology node
            if p["is_planet"]:
                s.run("""
                    MATCH (np:NatalPlacement {id: $id}), (planet:Planet {name: $planet})
                    MERGE (np)-[:IS_PLANET]->(planet)
                """, id=pid, planet=p["name"])
        
        # Depositor edges from Helios
        dep_count = 0
        for planet_name, chain_data in chains.items():
            dep_to = chain_data.get("depositsTo") or chain_data.get("depositor")
            if dep_to and dep_to != planet_name:
                from_id = f"{chart_name}_{planet_name.lower()}"
                to_id = f"{chart_name}_{dep_to.lower()}"
                s.run("""
                    MATCH (a:NatalPlacement {id: $fid}), (b:NatalPlacement {id: $tid})
                    MERGE (a)-[:DEPOSITS_TO]->(b)
                """, fid=from_id, tid=to_id)
                dep_count += 1
        
        # Mutual receptions
        for rec in receptions:
            id1 = f"{chart_name}_{rec['p1'].lower()}"
            id2 = f"{chart_name}_{rec['p2'].lower()}"
            s.run("""
                MATCH (a:NatalPlacement {id: $id1}), (b:NatalPlacement {id: $id2})
                MERGE (a)-[:MUTUAL_RECEPTION {type: $type}]->(b)
                MERGE (b)-[:MUTUAL_RECEPTION {type: $type}]->(a)
            """, id1=id1, id2=id2, type=rec["type"])
        
        # Natal aspects
        for asp in natal_aspects:
            id1 = f"{chart_name}_{asp['planet1'].lower()}"
            id2 = f"{chart_name}_{asp['planet2'].lower()}"
            s.run("""
                MATCH (a:NatalPlacement {id: $id1}), (b:NatalPlacement {id: $id2})
                MERGE (a)-[:NATAL_ASPECT {type: $type, angle: $angle, orb: $orb}]->(b)
            """, id1=id1, id2=id2, type=asp["type"], angle=asp["angle"], orb=asp["orb"])
        
        # Midpoint pictures
        for mp in midpoint_pictures:
            pid = f"{chart_name}_{mp['planet'].lower().replace(' ', '_')}"
            a1id = f"{chart_name}_{mp['axis1'].lower().replace(' ', '_')}"
            a2id = f"{chart_name}_{mp['axis2'].lower().replace(' ', '_')}"
            s.run("""
                MATCH (p:NatalPlacement {id: $pid})
                MATCH (a1:NatalPlacement {id: $a1id})
                MATCH (a2:NatalPlacement {id: $a2id})
                MERGE (p)-[:MIDPOINT_ACTIVATES {axis1: $ax1, axis2: $ax2, orb: $orb}]->(a1)
            """, pid=pid, a1id=a1id, a2id=a2id, ax1=mp["axis1"], ax2=mp["axis2"], orb=mp["orb"])
    
    print(f"  ✓ {len(placements)} placements")
    print(f"  ✓ {dep_count} depositor edges")
    print(f"  ✓ {len(receptions)} mutual receptions")
    print(f"  ✓ {len(natal_aspects)} natal aspects")
    print(f"  ✓ {len(midpoint_pictures)} midpoint pictures")
    if final_dispositor:
        print(f"  ✓ Final dispositor: {final_dispositor}")
    return True


def seed_insights(driver, chart_name):
    memory_path = CHART_DIR / "memory" / f"{chart_name}.json"
    if not memory_path.exists():
        return
    with open(memory_path) as f:
        memory = json.load(f)
    insights = memory.get("insights", [])
    if not insights:
        return
    
    with driver.session() as s:
        for ins in insights:
            iid = f"{chart_name}_insight_{ins.get('id', 0)}"
            s.run("""
                MERGE (i:Insight {id: $id})
                SET i.chart = $chart, i.text = $text, i.techniques = $techniques,
                    i.rating = $rating, i.validated = $validated, i.created = $created,
                    i.notes = $notes, i.placements = $placements
            """, id=iid, chart=chart_name,
                 text=ins.get("content", ins.get("insight", "")),
                 techniques=ins.get("techniques", [ins.get("technique", "")]),
                 rating=ins.get("rating", ins.get("score", 0)),
                 validated=ins.get("validated", False),
                 created=ins.get("timestamp", ins.get("created", "")),
                 notes=ins.get("validation_notes", ins.get("notes", "")),
                 placements=ins.get("placements", []))
            
            s.run("""
                MATCH (c:Chart {name: $chart}), (i:Insight {id: $id})
                MERGE (c)-[:HAS_INSIGHT]->(i)
            """, chart=chart_name, id=iid)
            
            # Link to referenced placements
            text_lower = ins.get("content", ins.get("insight", "")).lower()
            for pname in ALL_PLANETS + ANGLES + ["Node", "Lot_Fortune", "Lot_Spirit"]:
                if pname.lower() in text_lower:
                    pid = f"{chart_name}_{pname.lower()}"
                    s.run("""
                        MATCH (i:Insight {id: $iid}), (np:NatalPlacement {id: $pid})
                        MERGE (i)-[:REFERENCES]->(np)
                    """, iid=iid, pid=pid)
    
    print(f"  ✓ {len(insights)} insights")


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    driver.verify_connectivity()
    print("Connected to Neo4j")
    
    # Clear chart data (preserve ontology backbone)
    with driver.session() as s:
        s.run("MATCH (n:NatalPlacement) DETACH DELETE n")
        s.run("MATCH (n:Chart) DETACH DELETE n")
        s.run("MATCH (n:Insight) DETACH DELETE n")
        print("Cleared previous chart data\n")
    
    # Get charts from Helios
    try:
        charts_resp = requests.get(f"{HELIOS}/charts", timeout=5).json()
        helios_charts = charts_resp.get("charts", [])
    except:
        helios_charts = []
    
    # Also check Stella chart JSON files
    stella_charts = [f.stem for f in sorted(CHART_DIR.glob("*.json"))]
    all_charts = sorted(set(helios_charts + stella_charts))
    
    print(f"Charts to seed: {all_charts}\n")
    
    success = 0
    for name in all_charts:
        if seed_chart(driver, name):
            success += 1
        seed_insights(driver, name)
    
    # Final stats
    with driver.session() as s:
        stats = {}
        for label in ["Chart", "NatalPlacement", "Insight"]:
            stats[label] = s.run(f"MATCH (n:{label}) RETURN count(n) as c").single()["c"]
        for rel in ["DEPOSITS_TO", "NATAL_ASPECT", "MIDPOINT_ACTIVATES", "MUTUAL_RECEPTION",
                     "OCCUPIES_SIGN", "OCCUPIES_HOUSE", "IS_PLANET", "HAS_PLACEMENT", "HAS_INSIGHT", "REFERENCES"]:
            stats[rel] = s.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) as c").single()["c"]
        
        total_n = s.run("MATCH (n) RETURN count(n) as c").single()["c"]
        total_r = s.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
        
        print(f"\n{'='*60}\nFINAL GRAPH STATE\n{'='*60}")
        print(f"Total nodes: {total_n} | Total relationships: {total_r}")
        print(f"Charts: {stats['Chart']} | Placements: {stats['NatalPlacement']} | Insights: {stats['Insight']}")
        print(f"DEPOSITS_TO: {stats['DEPOSITS_TO']} | NATAL_ASPECT: {stats['NATAL_ASPECT']}")
        print(f"MIDPOINT_ACTIVATES: {stats['MIDPOINT_ACTIVATES']} | MUTUAL_RECEPTION: {stats['MUTUAL_RECEPTION']}")
        print(f"OCCUPIES_SIGN: {stats['OCCUPIES_SIGN']} | OCCUPIES_HOUSE: {stats['OCCUPIES_HOUSE']}")
        print(f"IS_PLANET: {stats['IS_PLANET']} | HAS_PLACEMENT: {stats['HAS_PLACEMENT']}")
        print(f"HAS_INSIGHT: {stats['HAS_INSIGHT']} | REFERENCES: {stats['REFERENCES']}")
    
    driver.close()
    print(f"\n✓ Seeded {success}/{len(all_charts)} charts")


if __name__ == "__main__":
    main()
