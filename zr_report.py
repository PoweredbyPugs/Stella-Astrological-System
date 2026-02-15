"""
Zodiacal Releasing Report Module
Comprehensive ZR analysis using Chris Brennan's worksheet framework.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from zr import calculate_zr, ZRSnapshot, SIGN_YEARS

SIGN_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

MODALITIES = {
    "Cardinal": ["Aries", "Cancer", "Libra", "Capricorn"],
    "Fixed": ["Taurus", "Leo", "Scorpio", "Aquarius"],
    "Mutable": ["Gemini", "Virgo", "Sagittarius", "Pisces"],
}

RULERS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}


def get_sign_index(sign: str) -> int:
    return SIGN_ORDER.index(sign)


def get_sign_at_offset(start_sign: str, offset: int) -> str:
    start_idx = get_sign_index(start_sign)
    return SIGN_ORDER[(start_idx + offset) % 12]


def get_modality(sign: str) -> str:
    for mod, signs in MODALITIES.items():
        if sign in signs:
            return mod
    return "Unknown"


def get_angular_signs_from_fortune(fortune_sign: str) -> Dict[str, Dict]:
    """
    Calculate peak periods from Lot of Fortune.
    Returns the 4 angular signs with their peak type.
    """
    fortune_idx = get_sign_index(fortune_sign)
    
    return {
        "fortune": {
            "sign": fortune_sign,
            "type": "Major Peak",
            "position": "Fortune itself",
            "emoji": "💕"
        },
        "4th": {
            "sign": get_sign_at_offset(fortune_sign, 3),  # 4th sign
            "type": "Minor Peak",
            "position": "4th from Fortune (first square)",
            "emoji": "💕"
        },
        "7th": {
            "sign": get_sign_at_offset(fortune_sign, 6),  # 7th sign (opposition)
            "type": "Moderate Peak", 
            "position": "7th from Fortune (opposition)",
            "emoji": "❤️"
        },
        "10th": {
            "sign": get_sign_at_offset(fortune_sign, 9),  # 10th sign
            "type": "Major Peak",
            "position": "10th from Fortune",
            "emoji": "💕💕"
        }
    }


def get_angular_triads(fortune_sign: str) -> List[Dict]:
    """
    Generate the 4 angular triads based on Fortune's modality.
    Each triad: Preparatory (fixed) -> Peak (mutable) -> Completion (cardinal)
    """
    modality = get_modality(fortune_sign)
    
    # Determine which modality is which phase based on Fortune's modality
    if modality == "Mutable":
        prep_mod = "Fixed"
        peak_mod = "Mutable"
        comp_mod = "Cardinal"
    elif modality == "Fixed":
        prep_mod = "Cardinal"
        peak_mod = "Fixed"
        comp_mod = "Mutable"
    else:  # Cardinal
        prep_mod = "Mutable"
        peak_mod = "Cardinal"
        comp_mod = "Fixed"
    
    triads = []
    
    # Build 4 triads starting from each element
    element_starts = {
        "Earth": "Taurus" if prep_mod == "Fixed" else ("Capricorn" if prep_mod == "Cardinal" else "Virgo"),
        "Fire": "Leo" if prep_mod == "Fixed" else ("Aries" if prep_mod == "Cardinal" else "Sagittarius"),
        "Water": "Scorpio" if prep_mod == "Fixed" else ("Cancer" if prep_mod == "Cardinal" else "Pisces"),
        "Air": "Aquarius" if prep_mod == "Fixed" else ("Libra" if prep_mod == "Cardinal" else "Gemini"),
    }
    
    # Reorder based on Fortune's modality for proper sequence
    for element, prep_sign in element_starts.items():
        prep_idx = get_sign_index(prep_sign)
        peak_sign = SIGN_ORDER[(prep_idx + 1) % 12]
        comp_sign = SIGN_ORDER[(prep_idx + 2) % 12]
        
        triads.append({
            "name": f"{element} Phase",
            "preparatory": {"sign": prep_sign, "modality": prep_mod},
            "peak": {"sign": peak_sign, "modality": peak_mod},
            "completion": {"sign": comp_sign, "modality": comp_mod},
        })
    
    return triads


def get_sect_planets(chart_data: Dict) -> Dict[str, Dict]:
    """Extract sect-based planet rankings from chart data."""
    sect = chart_data.get("sect", {})
    planets = chart_data.get("planets", [])
    
    # Build planet lookup
    planet_signs = {}
    planet_dignities = {}
    for p in planets:
        planet_signs[p["name"]] = p.get("sign", "")
        planet_dignities[p["name"]] = p.get("dignities", {})
    
    is_day = sect.get("isDaySect", True)
    
    result = {
        "sect": "Day" if is_day else "Night",
        "most_positive": {
            "planet": "Jupiter" if is_day else "Venus",
            "sign": planet_signs.get("Jupiter" if is_day else "Venus", ""),
            "role": "In-sect benefic"
        },
        "most_negative": {
            "planet": "Mars" if is_day else "Saturn",
            "sign": planet_signs.get("Mars" if is_day else "Saturn", ""),
            "role": "Contrary-sect malefic"
        },
        "moderate_benefic": {
            "planet": "Venus" if is_day else "Jupiter",
            "sign": planet_signs.get("Venus" if is_day else "Jupiter", ""),
            "role": "Contrary-sect benefic"
        },
        "moderate_malefic": {
            "planet": "Saturn" if is_day else "Mars",
            "sign": planet_signs.get("Saturn" if is_day else "Mars", ""),
            "role": "In-sect malefic"
        }
    }
    
    # Add dignity info
    for key in ["most_positive", "most_negative", "moderate_benefic", "moderate_malefic"]:
        planet = result[key]["planet"]
        dig = planet_dignities.get(planet, {})
        if dig:
            condition = dig.get("condition", "neutral")
            result[key]["condition"] = condition
            if dig.get("domicile"):
                result[key]["dignity"] = "Domicile"
            elif dig.get("exaltation"):
                result[key]["dignity"] = "Exalted"
            elif dig.get("detriment"):
                result[key]["dignity"] = "Detriment"
            elif dig.get("fall"):
                result[key]["dignity"] = "Fall"
    
    return result


def get_planets_by_modality(chart_data: Dict) -> Dict[str, List[Dict]]:
    """Group planets by the modality of their sign."""
    planets = chart_data.get("planets", [])
    
    result = {"Fixed": [], "Mutable": [], "Cardinal": []}
    
    for p in planets:
        name = p.get("name", "")
        sign = p.get("sign", "")
        if not sign or not name:
            continue
        # Skip outer planets and nodes for this analysis
        if name in ["Uranus", "Neptune", "Pluto", "North Node", "Chiron"]:
            continue
        mod = get_modality(sign)
        if mod in result:
            result[mod].append({
                "planet": name,
                "sign": sign,
            })
    
    return result


def is_peak_period(sign: str, fortune_sign: str) -> bool:
    """Check if a sign is angular from Fortune."""
    peaks = get_angular_signs_from_fortune(fortune_sign)
    peak_signs = [p["sign"] for p in peaks.values()]
    return sign in peak_signs


def get_peak_type(sign: str, fortune_sign: str) -> Optional[str]:
    """Get the peak type for a sign if it's angular from Fortune."""
    peaks = get_angular_signs_from_fortune(fortune_sign)
    for p in peaks.values():
        if p["sign"] == sign:
            return p["type"]
    return None


def generate_zr_report(
    chart_data: Dict[str, Any],
    target_dt: datetime,
    lot: str = "spirit"
) -> str:
    """
    Generate comprehensive ZR report using Brennan worksheet framework.
    """
    lots = chart_data.get("lots", {})
    birth_data = chart_data.get("birthData", {})
    
    fortune_data = lots.get("fortune", {})
    spirit_data = lots.get("spirit", {})
    
    fortune_sign = fortune_data.get("sign")
    fortune_degree = float(fortune_data.get("degreeInSign", 0))
    spirit_sign = spirit_data.get("sign")
    spirit_degree = float(spirit_data.get("degreeInSign", 0))
    
    # Calculate current ZR
    birth_date = birth_data.get("date")
    birth_time = birth_data.get("time", "12:00:00")
    birth_dt = datetime.fromisoformat(f"{birth_date}T{birth_time}")
    
    from zr import calculate_zr
    snapshot = calculate_zr(spirit_sign, spirit_degree, birth_dt, target_dt, lot)
    
    # Get framework data
    peaks = get_angular_signs_from_fortune(fortune_sign)
    triads = get_angular_triads(fortune_sign)
    sect_planets = get_sect_planets(chart_data)
    planets_by_mod = get_planets_by_modality(chart_data)
    fortune_modality = get_modality(fortune_sign)
    
    # Determine phase modalities
    if fortune_modality == "Mutable":
        prep_mod, peak_mod, comp_mod = "Fixed", "Mutable", "Cardinal"
    elif fortune_modality == "Fixed":
        prep_mod, peak_mod, comp_mod = "Cardinal", "Fixed", "Mutable"
    else:
        prep_mod, peak_mod, comp_mod = "Mutable", "Cardinal", "Fixed"
    
    # Build report
    lines = []
    
    # Header
    lines.append("# Zodiacal Releasing Report")
    lines.append(f"**Generated:** {target_dt.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    
    # Section 1: Lot Positions
    lines.append("## 1. Lot Positions")
    lines.append(f"- **Lot of Fortune:** {fortune_sign} {fortune_degree:.0f}° (ruler: {RULERS[fortune_sign]})")
    lines.append(f"- **Lot of Spirit:** {spirit_sign} {spirit_degree:.0f}° (ruler: {RULERS[spirit_sign]})")
    lines.append("")
    
    # Section 2: Peak Periods from Fortune
    lines.append("## 2. Peak Periods (from Lot of Fortune)")
    lines.append(f"Fortune is in **{fortune_sign}** ({fortune_modality}), so peak periods = **{peak_mod}** signs")
    lines.append("")
    lines.append("| Position | Sign | Peak Type |")
    lines.append("|----------|------|-----------|")
    for key, data in peaks.items():
        lines.append(f"| {data['position']} | **{data['sign']}** | {data['type']} {data['emoji']} |")
    lines.append("")
    
    # Section 3: Sect & Planet Conditions
    lines.append("## 3. Sect Analysis")
    lines.append(f"**Chart Sect:** {sect_planets['sect']}")
    lines.append("")
    lines.append("| Role | Planet | Sign | Notes |")
    lines.append("|------|--------|------|-------|")
    for key, data in sect_planets.items():
        if key == "sect":
            continue
        dignity = data.get("dignity", "")
        dignity_note = f" ({dignity})" if dignity else ""
        lines.append(f"| {data['role']} | **{data['planet']}** | {data['sign']}{dignity_note} | {key.replace('_', ' ').title()} |")
    lines.append("")
    
    # Section 4: Angular Triads
    lines.append("## 4. Angular Triads")
    lines.append("")
    lines.append("| Phase | Preparatory | Peak | Completion |")
    lines.append("|-------|-------------|------|------------|")
    for triad in triads:
        prep = triad["preparatory"]["sign"]
        peak = triad["peak"]["sign"]
        comp = triad["completion"]["sign"]
        peak_type = get_peak_type(peak, fortune_sign) or ""
        peak_marker = " ⭐" if peak_type else ""
        lines.append(f"| **{triad['name']}** | {prep} | {peak}{peak_marker} | {comp} |")
    lines.append("")
    
    # Section 5: Planets by Modality Phase
    lines.append("## 5. Planets by Phase")
    lines.append("")
    lines.append(f"| Phase | Modality | Planets | Experience |")
    lines.append("|-------|----------|---------|------------|")
    
    for phase, mod in [("Preparatory", prep_mod), ("Peak", peak_mod), ("Completion", comp_mod)]:
        planet_list = planets_by_mod.get(mod, [])
        planet_str = ", ".join([f"{p['planet']} ({p['sign']})" for p in planet_list[:4]])
        if not planet_str:
            planet_str = "None"
        lines.append(f"| {phase} | {mod} | {planet_str} | |")
    lines.append("")
    
    # Section 6: Current ZR Periods
    lines.append("## 6. Current Periods")
    lines.append("")
    
    for level, period in [("L1", snapshot.L1), ("L2", snapshot.L2), 
                          ("L3", snapshot.L3), ("L4", snapshot.L4), ("L5", snapshot.L5)]:
        peak_type = get_peak_type(period.sign, fortune_sign)
        peak_marker = f" ⭐ ({peak_type})" if peak_type else ""
        
        duration = period.duration_days
        if duration >= 365:
            dur_str = f"{duration/365.25:.1f} years"
        elif duration >= 30:
            dur_str = f"{duration/30:.1f} months"
        elif duration >= 1:
            dur_str = f"{duration:.1f} days"
        else:
            dur_str = f"{duration*24:.1f} hours"
        
        lines.append(f"**{level}: {period.sign}** ({period.ruler}){peak_marker}")
        lines.append(f"- {period.start.strftime('%Y-%m-%d')} → {period.end.strftime('%Y-%m-%d')} ({dur_str})")
        lines.append("")
    
    # Section 7: Loosing of the Bond
    if snapshot.is_loosing_of_bond:
        lines.append("## 7. ⚡ Loosing of the Bond")
        lines.append(f"{snapshot.loosing_details}")
        lines.append("")
    
    # Section 8: Interpretation Notes
    lines.append("## 8. Key Observations")
    lines.append("")
    
    # Count active peaks
    active_peaks = []
    for level, period in [("L1", snapshot.L1), ("L2", snapshot.L2), 
                          ("L3", snapshot.L3), ("L4", snapshot.L4)]:
        pt = get_peak_type(period.sign, fortune_sign)
        if pt:
            active_peaks.append(f"{level} {period.sign} ({pt})")
    
    if active_peaks:
        lines.append(f"**Active Peak Periods:** {', '.join(active_peaks)}")
    else:
        lines.append("**Active Peak Periods:** None at major levels")
    
    # Note planets coloring current periods
    lines.append("")
    lines.append("**Planets in Current Signs:**")
    for level, period in [("L2", snapshot.L2), ("L3", snapshot.L3)]:
        planets_in_sign = [p["name"] for p in chart_data.get("planets", []) 
                          if p.get("sign") == period.sign]
        if planets_in_sign:
            lines.append(f"- {level} {period.sign}: {', '.join(planets_in_sign)}")
    
    return "\n".join(lines)


def zr_report_for_chart(chart_data: Dict[str, Any], target_dt: datetime) -> str:
    """Convenience wrapper for Stella integration."""
    return generate_zr_report(chart_data, target_dt, "spirit")


if __name__ == "__main__":
    import json
    
    # Test with sample chart
    with open("charts/chris.json", "r") as f:
        chart = json.load(f)
    
    target = datetime(2026, 2, 5, 1, 30)
    report = generate_zr_report(chart, target)
    print(report)
