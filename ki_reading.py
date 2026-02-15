"""
Ki + I Ching Combined Reading Generator

Synthesizes 9 Star Ki profile with I Ching hexagram for deep readings.
"""

from datetime import date
from typing import Dict, Optional, List
import random

from ki import (
    calculate_natal_ki,
    calculate_ki,
    get_full_profile,
    calculate_personal_cycle,
    KI_TRIGRAMS,
    FLYING_SEQUENCE,
    NUM_TO_IDX,
)


# Ki number to I Ching trigram mapping
KI_TO_ICHING = {
    1: {"trigram": "☵", "iching": "Kan", "image": "Water", "quality": "depth, mystery, adaptability", "lines": (0, 1, 0)},
    2: {"trigram": "☷", "iching": "Kun", "image": "Earth", "quality": "receptivity, nurturing, devotion", "lines": (0, 0, 0)},
    3: {"trigram": "☳", "iching": "Zhen", "image": "Thunder", "quality": "initiative, arousal, breakthrough", "lines": (1, 0, 0)},
    4: {"trigram": "☴", "iching": "Xun", "image": "Wind/Wood", "quality": "gentle penetration, growth, influence", "lines": (0, 1, 1)},
    5: {"trigram": "☯", "iching": "Tai Chi", "image": "Center", "quality": "balance, transformation, power", "lines": None},  # Special case
    6: {"trigram": "☰", "iching": "Qian", "image": "Heaven", "quality": "creativity, authority, leadership", "lines": (1, 1, 1)},
    7: {"trigram": "☱", "iching": "Dui", "image": "Lake", "quality": "joy, reflection, expression", "lines": (1, 1, 0)},
    8: {"trigram": "☶", "iching": "Gen", "image": "Mountain", "quality": "stillness, meditation, completion", "lines": (0, 0, 1)},
    9: {"trigram": "☲", "iching": "Li", "image": "Fire", "quality": "clarity, illumination, visibility", "lines": (1, 0, 1)},
}

# King Wen sequence: [lower_trigram_index][upper_trigram_index] -> hexagram number
# Trigram indices: Kun=0, Zhen=1, Kan=2, Dui=3, Gen=4, Li=5, Xun=6, Qian=7
TRIGRAM_TO_INDEX = {
    (0, 0, 0): 0,  # Kun/Earth
    (1, 0, 0): 1,  # Zhen/Thunder
    (0, 1, 0): 2,  # Kan/Water
    (1, 1, 0): 3,  # Dui/Lake
    (0, 0, 1): 4,  # Gen/Mountain
    (1, 0, 1): 5,  # Li/Fire
    (0, 1, 1): 6,  # Xun/Wind
    (1, 1, 1): 7,  # Qian/Heaven
}

# Standard King Wen sequence lookup: [lower][upper] = hexagram
# Verified against standard I Ching
KING_WEN = [
    # Upper:  Kun  Zhen Kan  Dui  Gen  Li   Xun  Qian
    [2,   24,   7,   19,  15,  35,  46,  11],   # Lower: Kun
    [16,  51,  40,   54,  62,  55,  32,  34],   # Lower: Zhen
    [8,    3,  29,   60,  39,  63,  48,   5],   # Lower: Kan
    [45,  17,  47,   58,  31,  49,  28,  43],   # Lower: Dui
    [23,  27,   4,   41,  52,  22,  18,  26],   # Lower: Gen
    [36,  55,  63,   49,  22,  30,  37,  13],   # Lower: Li
    [20,  42,  59,   61,  53,  37,  57,   9],   # Lower: Xun
    [12,  25,   6,   10,  33,  13,  44,   1],   # Lower: Qian
]


def ki_to_hexagram(lower_ki: int, upper_ki: int) -> Optional[int]:
    """
    Convert two Ki numbers into a hexagram number.
    
    Lower Ki = personal year (lower trigram)
    Upper Ki = personal month (upper trigram)
    
    Returns hexagram number (1-64) or None if Ki 5 (Center) involved.
    """
    lower_lines = KI_TO_ICHING[lower_ki]["lines"]
    upper_lines = KI_TO_ICHING[upper_ki]["lines"]
    
    # Ki 5 (Center) doesn't map to a trigram
    if lower_lines is None or upper_lines is None:
        return None
    
    lower_idx = TRIGRAM_TO_INDEX.get(lower_lines)
    upper_idx = TRIGRAM_TO_INDEX.get(upper_lines)
    
    if lower_idx is None or upper_idx is None:
        return None
    
    return KING_WEN[lower_idx][upper_idx]


def get_next_month_ki(natal_year_ki: int, current_date: date) -> int:
    """Get the personal month Ki for the following month."""
    from datetime import timedelta
    # Approximate next month by adding 35 days
    next_month_date = current_date + timedelta(days=35)
    next_cycle = calculate_personal_cycle(natal_year_ki, next_month_date)
    return next_cycle['personal_month']


def get_hexagram_lines(lower_ki: int, upper_ki: int) -> Optional[tuple]:
    """Get the 6 lines of a hexagram from Ki positions."""
    lower_lines = KI_TO_ICHING[lower_ki]["lines"]
    upper_lines = KI_TO_ICHING[upper_ki]["lines"]
    
    if lower_lines is None or upper_lines is None:
        return None
    
    # Combine: lower trigram (lines 1-3) + upper trigram (lines 4-6)
    return lower_lines + upper_lines


def find_changing_lines(current_hex_lines: tuple, next_hex_lines: tuple) -> List[int]:
    """Find which lines differ between two hexagrams (1-indexed)."""
    changing = []
    for i in range(6):
        if current_hex_lines[i] != next_hex_lines[i]:
            changing.append(i + 1)  # 1-indexed
    return changing

# Element interactions
ELEMENT_FEEDS = {
    "Wood": "Fire",
    "Fire": "Earth", 
    "Earth": "Metal",
    "Metal": "Water",
    "Water": "Wood",
}

ELEMENT_CONTROLS = {
    "Wood": "Earth",
    "Fire": "Metal",
    "Earth": "Water",
    "Metal": "Wood",
    "Water": "Fire",
}


def get_element_relationship(elem1: str, elem2: str) -> str:
    """Describe the relationship between two elements."""
    if elem1 == elem2:
        return "same element — reinforcement, intensification"
    if ELEMENT_FEEDS.get(elem1) == elem2:
        return f"{elem1} feeds {elem2} — productive, supportive flow"
    if ELEMENT_FEEDS.get(elem2) == elem1:
        return f"{elem2} feeds {elem1} — receiving nourishment"
    if ELEMENT_CONTROLS.get(elem1) == elem2:
        return f"{elem1} controls {elem2} — disciplining, structuring"
    if ELEMENT_CONTROLS.get(elem2) == elem1:
        return f"{elem2} controls {elem1} — being shaped, challenged"
    return "indirect relationship"


def generate_natal_interpretation(natal: Dict) -> str:
    """Generate interpretation of natal Ki pattern."""
    year_ki = natal['ki_year']
    month_ki = natal['ki_month']
    third_ki = natal['ki_third']
    
    yi = KI_TRIGRAMS[year_ki]
    mi = KI_TRIGRAMS[month_ki]
    ti = KI_TRIGRAMS[third_ki]
    
    year_ich = KI_TO_ICHING[year_ki]
    month_ich = KI_TO_ICHING[month_ki]
    third_ich = KI_TO_ICHING[third_ki]
    
    lines = []
    lines.append(f"## Natal Pattern: {year_ki}.{month_ki}.{third_ki}")
    lines.append("")
    
    # Year Ki - outer self
    lines.append(f"**Year Ki: {year_ki} {yi['trigram']} {yi['name']}** ({yi['element']})")
    lines.append(f"*{year_ich['quality']}*")
    lines.append(f"This is your constitutional energy — how you move through the world, your basic nature visible to others.")
    lines.append("")
    
    # Month Ki - emotional/relational
    lines.append(f"**Month Ki: {month_ki} {mi['trigram']} {mi['name']}** ({mi['element']})")
    lines.append(f"*{month_ich['quality']}*")
    lines.append(f"This is your emotional core — how you relate, what you need in relationships, your inner world.")
    lines.append("")
    
    # Third Ki - deep self
    lines.append(f"**Third Ki: {third_ki} {ti['trigram']} {ti['name']}** ({ti['element']})")
    lines.append(f"*{third_ich['quality']}*")
    lines.append(f"This is your hidden depth — revealed under stress, your deepest motivations, what drives you beneath the surface.")
    lines.append("")
    
    # Pattern analysis
    elements = [yi['element'], mi['element'], ti['element']]
    unique_elements = set(elements)
    
    if len(unique_elements) == 1:
        lines.append(f"**Pattern:** Triple {elements[0]} — intense concentration of this element's qualities.")
    elif len(unique_elements) == 2:
        doubled = [e for e in elements if elements.count(e) > 1][0]
        lines.append(f"**Pattern:** Double {doubled} with {[e for e in unique_elements if e != doubled][0]} — the doubled element dominates.")
    else:
        lines.append(f"**Pattern:** Three different elements ({', '.join(unique_elements)}) — diverse, complex, multifaceted.")
    
    # Year-Month relationship
    ym_rel = get_element_relationship(yi['element'], mi['element'])
    lines.append(f"**Year↔Month:** {ym_rel}")
    
    return "\n".join(lines)


def generate_cycle_interpretation(natal: Dict, cycle: Dict) -> str:
    """Generate interpretation of current personal cycle."""
    natal_year_ki = natal['ki_year']
    personal_year = cycle['personal_year']
    personal_month = cycle['personal_month']
    
    nyi = KI_TRIGRAMS[natal_year_ki]
    pyi = KI_TRIGRAMS[personal_year]
    pmi = KI_TRIGRAMS[personal_month]
    
    py_ich = KI_TO_ICHING[personal_year]
    pm_ich = KI_TO_ICHING[personal_month]
    
    lines = []
    lines.append(f"## Current Cycle: {personal_year}.{personal_month}")
    lines.append(f"*Global: {cycle['global_year']}.{cycle['global_month']}*")
    lines.append("")
    
    # Personal Year
    lines.append(f"**Personal Year: {personal_year} {pyi['trigram']} {pyi['name']}** ({pyi['element']})")
    lines.append(f"*{py_ich['quality']}*")
    
    # Natal to Personal Year relationship
    natal_elem = nyi['element']
    year_elem = pyi['element']
    year_rel = get_element_relationship(natal_elem, year_elem)
    lines.append(f"Your {natal_elem} nature is moving through {year_elem} territory — {year_rel}.")
    lines.append("")
    
    # Personal Month
    lines.append(f"**Personal Month: {personal_month} {pmi['trigram']} {pmi['name']}** ({pmi['element']})")
    lines.append(f"*{pm_ich['quality']}*")
    
    # Year to Month relationship  
    month_elem = pmi['element']
    month_rel = get_element_relationship(year_elem, month_elem)
    lines.append(f"This month within the year: {month_rel}.")
    lines.append("")
    
    return "\n".join(lines)


def generate_synthesis(natal: Dict, cycle: Dict, hexagram: Optional[Dict] = None) -> str:
    """Generate final synthesis combining all elements."""
    year_ki = natal['ki_year']
    month_ki = natal['ki_month']
    personal_year = cycle['personal_year']
    personal_month = cycle['personal_month']
    
    yi = KI_TRIGRAMS[year_ki]
    pyi = KI_TRIGRAMS[personal_year]
    pmi = KI_TRIGRAMS[personal_month]
    
    lines = []
    lines.append("## Synthesis")
    lines.append("")
    
    # Core message based on natal + cycle
    natal_elem = yi['element']
    year_elem = pyi['element']
    month_elem = pmi['element']
    
    if natal_elem == year_elem:
        lines.append(f"You're in a **{year_elem} year matching your {natal_elem} nature** — this is your element, amplified. Natural expression, but watch for excess.")
    elif ELEMENT_FEEDS.get(natal_elem) == year_elem:
        lines.append(f"Your {natal_elem} nature is **feeding into {year_elem}** — you're fueling growth, contributing energy outward. Generative but potentially depleting.")
    elif ELEMENT_FEEDS.get(year_elem) == natal_elem:
        lines.append(f"The {year_elem} year **nourishes your {natal_elem}** — receiving support, being fed. Time to absorb and strengthen.")
    elif ELEMENT_CONTROLS.get(natal_elem) == year_elem:
        lines.append(f"Your {natal_elem} nature **shapes the {year_elem} energy** — you have leverage, influence. Use it wisely.")
    elif ELEMENT_CONTROLS.get(year_elem) == natal_elem:
        lines.append(f"The {year_elem} year **challenges your {natal_elem}** — being shaped, refined. Growth through friction.")
    
    lines.append("")
    
    if hexagram:
        lines.append(f"**The Oracle (Hexagram {hexagram.get('primary', {}).get('number', '?')})** confirms and deepens this pattern. The I Ching doesn't predict — it illuminates. What the Ki shows as elemental flow, the hexagram shows as situational wisdom.")
        
        if hexagram.get('transformed'):
            lines.append(f"The transformation to Hexagram {hexagram['transformed'].get('number', '?')} shows the direction of movement — where this energy wants to go.")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    
    return "\n".join(lines)


def format_full_reading(
    birth_date: date,
    target_date: Optional[date] = None,
    hexagram: Optional[Dict] = None,
    wisdom_snippets: Optional[List[str]] = None,
) -> str:
    """Generate complete Ki + I Ching reading."""
    
    if target_date is None:
        target_date = date.today()
    
    profile = get_full_profile(birth_date, target_date)
    natal = profile['natal']
    cycle = profile['current_cycle']
    
    lines = []
    lines.append(f"# 9 Star Ki + I Ching Reading")
    lines.append(f"**Birth Date:** {birth_date.isoformat()}")
    lines.append(f"**Reading Date:** {target_date.isoformat()}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Natal interpretation
    lines.append(generate_natal_interpretation(natal))
    lines.append("")
    
    # Cycle interpretation
    lines.append(generate_cycle_interpretation(natal, cycle))
    lines.append("")
    
    # Derive hexagram from Ki positions (not random cast)
    personal_year = cycle['personal_year']
    personal_month = cycle['personal_month']
    
    # Current hexagram: Year below, Month above
    current_hex = ki_to_hexagram(personal_year, personal_month)
    
    # Next month's hexagram
    next_month_ki = get_next_month_ki(natal['ki_year'], target_date)
    next_hex = ki_to_hexagram(personal_year, next_month_ki)
    
    if current_hex:
        year_tri = KI_TO_ICHING[personal_year]
        month_tri = KI_TO_ICHING[personal_month]
        
        hexagram = {
            "primary": {
                "number": current_hex,
                "lower_trigram": f"{year_tri['trigram']} {year_tri['image']}",
                "upper_trigram": f"{month_tri['trigram']} {month_tri['image']}",
            },
            "derived_from": f"Year Ki {personal_year} + Month Ki {personal_month}",
        }
        
        if next_hex and next_hex != current_hex:
            next_month_tri = KI_TO_ICHING[next_month_ki]
            
            # Find changing lines
            current_lines = get_hexagram_lines(personal_year, personal_month)
            next_lines = get_hexagram_lines(personal_year, next_month_ki)
            changing_lines = []
            if current_lines and next_lines:
                changing_lines = find_changing_lines(current_lines, next_lines)
            
            hexagram["transformed"] = {
                "number": next_hex,
                "upper_trigram": f"{next_month_tri['trigram']} {next_month_tri['image']}",
                "next_month_ki": next_month_ki,
            }
            hexagram["changing_lines"] = changing_lines
    
    # Hexagram names for common reference
    HEX_NAMES = {
        1: "The Creative", 2: "The Receptive", 3: "Difficulty at Beginning", 4: "Youthful Folly",
        5: "Waiting", 6: "Conflict", 7: "The Army", 8: "Holding Together", 9: "Small Taming",
        10: "Treading", 11: "Peace", 12: "Standstill", 13: "Fellowship", 14: "Great Possession",
        15: "Modesty", 16: "Enthusiasm", 17: "Following", 18: "Repair", 19: "Approach",
        20: "Contemplation", 21: "Biting Through", 22: "Grace", 23: "Splitting Apart", 24: "Return",
        25: "Innocence", 26: "Great Taming", 27: "Nourishment", 28: "Great Excess", 29: "The Abysmal",
        30: "Clarity/Fire", 31: "Influence", 32: "Duration", 33: "Retreat", 34: "Great Power",
        35: "Progress", 36: "Darkening of Light", 37: "The Family", 38: "Opposition", 39: "Obstruction",
        40: "Deliverance", 41: "Decrease", 42: "Increase", 43: "Breakthrough", 44: "Coming to Meet",
        45: "Gathering", 46: "Ascending", 47: "Oppression", 48: "The Well", 49: "Revolution",
        50: "The Cauldron", 51: "Thunder/Shock", 52: "Keeping Still", 53: "Gradual Progress",
        54: "The Marrying Maiden", 55: "Abundance", 56: "The Wanderer", 57: "Gentle Penetration",
        58: "Joy", 59: "Dispersion", 60: "Limitation", 61: "Inner Truth", 62: "Small Excess",
        63: "After Completion", 64: "Before Completion"
    }
    
    # Hexagram derived from Ki positions
    if hexagram:
        primary = hexagram.get('primary', {})
        hex_num = primary.get('number', 0)
        hex_name = HEX_NAMES.get(hex_num, f"Hexagram {hex_num}")
        
        lines.append(f"## Current Hexagram: {hex_num} — {hex_name}")
        lines.append(f"**{primary.get('upper_trigram', '')} above (Month) / {primary.get('lower_trigram', '')} below (Year)**")
        if hexagram.get('derived_from'):
            lines.append(f"*Derived from: {hexagram['derived_from']}*")
        lines.append("")
        
        # Transformation to next month
        if hexagram.get('transformed'):
            transformed = hexagram['transformed']
            trans_num = transformed.get('number', 0)
            trans_name = HEX_NAMES.get(trans_num, f"Hexagram {trans_num}")
            next_ki = transformed.get('next_month_ki', 0)
            next_tri = KI_TO_ICHING.get(next_ki, {})
            
            lines.append(f"### Next Month → Hexagram {trans_num} — {trans_name}")
            lines.append(f"Month shifts to **{next_ki} {next_tri.get('trigram', '')} {next_tri.get('image', '')}**")
            
            # Show changing lines
            if hexagram.get('changing_lines'):
                cl = hexagram['changing_lines']
                lines.append(f"**Changing Line{'s' if len(cl) > 1 else ''}:** {', '.join([str(l) for l in cl])}")
            lines.append("")
        
        if wisdom_snippets:
            lines.append("### From the Gnostic I Ching:")
            for snippet in wisdom_snippets[:2]:
                clean = snippet.replace('\n', ' ').strip()
                if len(clean) > 250:
                    clean = clean[:250] + "..."
                lines.append(f"> {clean}")
                lines.append("")
    
    # Synthesis
    lines.append(generate_synthesis(natal, cycle, hexagram))
    
    return "\n".join(lines)
