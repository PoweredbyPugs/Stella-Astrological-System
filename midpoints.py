"""
Stella — Cosmobiology / Midpoint Module

90° dial math, midpoint trees, and Ebertin COSI lookup.
"""

import json
from pathlib import Path
from typing import Optional

STELLA_DIR = Path(__file__).parent
EBERTIN_JSON = STELLA_DIR.parent / "reference" / "ebertin" / "ebertin-structured.json"

# ── Body name normalization ──
# Maps various input formats to the canonical pair names used in COSI
BODY_CANONICAL = {
    "sun": "SUN", "moon": "MOON", "mercury": "MERCURY", "venus": "VENUS",
    "mars": "MARS", "jupiter": "JUPITER", "saturn": "SATURN",
    "uranus": "URANUS", "neptune": "NEPTUNE", "pluto": "PLUTO",
    "north_node": "NODE", "north node": "NODE", "node": "NODE",
    "dragon's head": "NODE", "rahu": "NODE",
    "asc": "ASC", "ascendant": "ASC",
    "mc": "MC", "midheaven": "MC", "medium coeli": "MC",
    # Also accept uppercase
    "SUN": "SUN", "MOON": "MOON", "MERCURY": "MERCURY", "VENUS": "VENUS",
    "MARS": "MARS", "JUPITER": "JUPITER", "SATURN": "SATURN",
    "URANUS": "URANUS", "NEPTUNE": "NEPTUNE", "PLUTO": "PLUTO",
    "NODE": "NODE", "ASC": "ASC", "MC": "MC",
    # Bodies present in charts but not in COSI — silently accepted, skipped in pairs
    "chiron": "CHIRON", "CHIRON": "CHIRON",
    "ceres": "CERES", "CERES": "CERES",
    "pallas": "PALLAS", "PALLAS": "PALLAS",
    "juno": "JUNO", "JUNO": "JUNO",
    "vesta": "VESTA", "VESTA": "VESTA",
    "lot_fortune": "LOT_FORTUNE", "lot of fortune": "LOT_FORTUNE",
    "lot_spirit": "LOT_SPIRIT", "lot of spirit": "LOT_SPIRIT",
    "south_node": "SOUTH_NODE", "south node": "SOUTH_NODE",
}

# Display names for output
BODY_DISPLAY = {
    "SUN": "Sun", "MOON": "Moon", "MERCURY": "Mercury", "VENUS": "Venus",
    "MARS": "Mars", "JUPITER": "Jupiter", "SATURN": "Saturn",
    "URANUS": "Uranus", "NEPTUNE": "Neptune", "PLUTO": "Pluto",
    "NODE": "Node", "ASC": "ASC", "MC": "MC",
}

# All bodies used in COSI midpoint pairs
ALL_BODIES = ["SUN", "MOON", "MERCURY", "VENUS", "MARS", "JUPITER",
              "SATURN", "URANUS", "NEPTUNE", "PLUTO", "NODE", "ASC", "MC"]

# ── Ebertin COSI Data ──
_ebertin_data: Optional[dict] = None


def _load_ebertin() -> dict:
    """Load Ebertin structured JSON (lazy, cached)."""
    global _ebertin_data
    if _ebertin_data is None:
        with open(EBERTIN_JSON) as f:
            _ebertin_data = json.load(f)
    return _ebertin_data


def normalize_body(name: str) -> str:
    """Normalize a body name to COSI canonical form."""
    key = name.strip().lower()
    if key in BODY_CANONICAL:
        return BODY_CANONICAL[key]
    raise ValueError(f"Unknown body: {name!r}")


# ── 90° Dial Math ──

def to_90(zodiac_degrees: float) -> float:
    """Convert absolute zodiac longitude to 90° dial position.
    
    The 90° dial folds the 360° zodiac into 90°, collapsing
    conjunction, square, and opposition into the same point.
    """
    return zodiac_degrees % 90


def midpoint_direct(pos_a_90: float, pos_b_90: float) -> float:
    """Calculate the near midpoint of two positions on the 90° dial.
    
    On the 90° dial, each pair of points has two midpoints 45° apart.
    We return the nearer one (standard cosmobiological convention).
    """
    a, b = pos_a_90, pos_b_90
    
    # Ensure a <= b
    if a > b:
        a, b = b, a
    
    diff = b - a
    if diff <= 45:
        # Near midpoint is between them
        mid = (a + b) / 2
    else:
        # Near midpoint wraps around
        mid = ((a + b) / 2 + 45) % 90
    
    return mid % 90


def angular_distance_90(a: float, b: float) -> float:
    """Shortest angular distance between two points on the 90° dial."""
    diff = abs(a - b) % 90
    if diff > 45:
        diff = 90 - diff
    return diff


def find_midpoint_activations(
    positions: dict[str, float],
    orb: float = 1.5,
) -> list[dict]:
    """Find all midpoint activations in a set of positions.
    
    Args:
        positions: {body_name: zodiac_longitude} — all bodies in the chart
        orb: maximum orb on the 90° dial (default 1.5°)
    
    Returns:
        List of activations sorted by orb:
        [
            {
                "activating_body": "JUPITER",
                "body_1": "SUN",
                "body_2": "MOON", 
                "pair": "SUN/MOON",
                "activating_pos_90": 5.15,
                "midpoint_pos_90": 4.82,
                "orb": 0.33,
                "notation": "Jupiter = Sun/Moon",
            },
            ...
        ]
    """
    # Normalize names and compute 90° positions (skip non-COSI bodies)
    bodies = {}
    pos_90 = {}
    for name, lon in positions.items():
        canonical = normalize_body(name)
        if not _in_cosi(canonical):
            continue
        bodies[canonical] = lon
        pos_90[canonical] = to_90(lon)
    
    body_list = list(bodies.keys())
    activations = []
    
    # Generate all midpoints
    for i in range(len(body_list)):
        for j in range(i + 1, len(body_list)):
            b1 = body_list[i]
            b2 = body_list[j]
            mp = midpoint_direct(pos_90[b1], pos_90[b2])
            
            # Check each body as potential activator
            for k in range(len(body_list)):
                bk = body_list[k]
                if bk == b1 or bk == b2:
                    continue
                
                dist = angular_distance_90(pos_90[bk], mp)
                if dist <= orb:
                    # Normalize pair order to match COSI keys
                    pair = _normalize_pair(b1, b2)
                    
                    activations.append({
                        "activating_body": bk,
                        "body_1": pair.split("/")[0],
                        "body_2": pair.split("/")[1],
                        "pair": pair,
                        "activating_pos_90": round(pos_90[bk], 4),
                        "midpoint_pos_90": round(mp, 4),
                        "orb": round(dist, 4),
                        "notation": f"{BODY_DISPLAY.get(bk, bk)} = {BODY_DISPLAY.get(pair.split('/')[0], pair.split('/')[0])}/{BODY_DISPLAY.get(pair.split('/')[1], pair.split('/')[1])}",
                    })
    
    # Sort by orb (tightest first)
    activations.sort(key=lambda x: x["orb"])
    return activations


def find_transit_midpoint_activations(
    natal_positions: dict[str, float],
    transit_positions: dict[str, float],
    orb: float = 1.0,
) -> list[dict]:
    """Find transiting planets activating natal midpoints.
    
    Args:
        natal_positions: {body: zodiac_lon} natal chart
        transit_positions: {body: zodiac_lon} current transits
        orb: max orb on 90° dial (default 1.0° — tighter for transits)
    
    Returns:
        List of transit activations sorted by orb.
    """
    # Natal 90° positions and midpoints (skip non-COSI bodies)
    natal = {}
    natal_90 = {}
    for name, lon in natal_positions.items():
        c = normalize_body(name)
        if not _in_cosi(c):
            continue
        natal[c] = lon
        natal_90[c] = to_90(lon)
    
    # Transit 90° positions (skip non-COSI bodies)
    transit = {}
    transit_90 = {}
    for name, lon in transit_positions.items():
        c = normalize_body(name)
        if not _in_cosi(c):
            continue
        transit[c] = lon
        transit_90[c] = to_90(lon)
    
    natal_list = list(natal.keys())
    activations = []
    
    # All natal midpoints
    for i in range(len(natal_list)):
        for j in range(i + 1, len(natal_list)):
            b1 = natal_list[i]
            b2 = natal_list[j]
            mp = midpoint_direct(natal_90[b1], natal_90[b2])
            
            # Check each transit planet
            for t_body, t_pos in transit_90.items():
                dist = angular_distance_90(t_pos, mp)
                if dist <= orb:
                    pair = _normalize_pair(b1, b2)
                    
                    activations.append({
                        "transit_body": t_body,
                        "natal_body_1": pair.split("/")[0],
                        "natal_body_2": pair.split("/")[1],
                        "pair": pair,
                        "transit_pos_90": round(t_pos, 4),
                        "midpoint_pos_90": round(mp, 4),
                        "orb": round(dist, 4),
                        "notation": f"tr.{BODY_DISPLAY.get(t_body, t_body)} = n.{BODY_DISPLAY.get(pair.split('/')[0], pair.split('/')[0])}/{BODY_DISPLAY.get(pair.split('/')[1], pair.split('/')[1])}",
                    })
    
    activations.sort(key=lambda x: x["orb"])
    return activations


def _in_cosi(body: str) -> bool:
    """Check if a body has COSI midpoint data."""
    return body in ALL_BODIES


def _normalize_pair(b1: str, b2: str) -> str:
    """Normalize a pair to match COSI key order."""
    # COSI order follows ALL_BODIES order
    idx1 = ALL_BODIES.index(b1) if b1 in ALL_BODIES else 99
    idx2 = ALL_BODIES.index(b2) if b2 in ALL_BODIES else 99
    if idx1 <= idx2:
        return f"{b1}/{b2}"
    return f"{b2}/{b1}"


def lookup_ebertin(pair: str) -> Optional[str]:
    """Direct lookup of Ebertin's COSI entry for a midpoint pair.
    
    Args:
        pair: e.g. "SUN/MOON", "MARS/SATURN"
    
    Returns:
        Full COSI text for that pair, or None if not found.
    """
    data = _load_ebertin()
    return data.get(pair)


def lookup_ebertin_pair(body_1: str, body_2: str) -> Optional[str]:
    """Lookup by two body names (normalizes order)."""
    b1 = normalize_body(body_1)
    b2 = normalize_body(body_2)
    pair = _normalize_pair(b1, b2)
    return lookup_ebertin(pair)


def format_midpoint_sort(positions: dict[str, float]) -> str:
    """Format a midpoint sort table (all positions on 90° dial, sorted)."""
    rows = []
    for name, lon in positions.items():
        c = normalize_body(name)
        if not _in_cosi(c):
            continue
        p90 = to_90(lon)
        
        # Convert lon to sign/degree
        signs = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir",
                 "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
        sign_idx = int(lon // 30)
        deg = lon % 30
        sign_str = f"{signs[sign_idx]} {deg:05.2f}°"
        
        rows.append((p90, BODY_DISPLAY.get(c, c), sign_str, f"{p90:05.2f}°"))
    
    rows.sort(key=lambda x: x[0])
    
    lines = ["Planet       Zodiac Position   90° Dial"]
    lines.append("─" * 45)
    for _, name, sign_str, dial_str in rows:
        lines.append(f"{name:<12} {sign_str:<17} {dial_str}")
    
    return "\n".join(lines)
