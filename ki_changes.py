"""Ki Changes — Mercury's function applied to Ki.

Mercury reads the transitions, not the states. This module computes:
1. When each Ki level changes next (hour, day, month, year, synodic)
2. The hexagram formed by each pair of adjacent Ki levels (lower=stable, upper=changing)
3. The changing lines between current and next Ki at each level
4. Cross-references to the Gnostic Book of Changes for interpretation

The I Ching IS Mercury's grid: 64 = 8², and every Ki transition is a hexagram
because every pair of trigrams (Ki numbers 1-9 map to 8 trigrams + center)
forms a hexagram in the King Wen sequence.

Ki 5 (Center/Tai Chi) has no trigram — it is the pivot that generates change
but doesn't participate in it. When Ki 5 appears, it acts as ☷ Earth (Kun)
in hexagram formation (the receptive ground).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")

# Ki number → I Ching trigram mapping
# Ki uses Later Heaven (King Wen) arrangement
# Ki 5 (Center) has no trigram; we map it to Kun (Earth/receptive) — the ground
KI_TO_TRIGRAM = {
    1: {"idx": 5, "name": "Kan",  "symbol": "☵", "element": "Water",    "lines": [0, 1, 0]},
    2: {"idx": 7, "name": "Kun",  "symbol": "☷", "element": "Earth",    "lines": [0, 0, 0]},
    3: {"idx": 3, "name": "Zhen", "symbol": "☳", "element": "Thunder",  "lines": [1, 0, 0]},
    4: {"idx": 4, "name": "Xun",  "symbol": "☴", "element": "Wind",     "lines": [0, 1, 1]},
    5: {"idx": 7, "name": "Kun",  "symbol": "☷", "element": "Earth",    "lines": [0, 0, 0]},  # Center → Earth
    6: {"idx": 0, "name": "Qian", "symbol": "☰", "element": "Heaven",   "lines": [1, 1, 1]},
    7: {"idx": 1, "name": "Dui",  "symbol": "☱", "element": "Lake",     "lines": [1, 1, 0]},
    8: {"idx": 6, "name": "Gen",  "symbol": "☶", "element": "Mountain", "lines": [0, 0, 1]},
    9: {"idx": 2, "name": "Li",   "symbol": "☲", "element": "Fire",     "lines": [1, 0, 1]},
}

# King Wen sequence table (same as stella_server.py)
KING_WEN = [
    # Lower→  Qian  Dui   Li  Zhen  Xun   Kan  Gen   Kun
    [ 1, 10, 13, 25, 44,  6, 33, 12],   # Upper: Qian ☰
    [43, 58, 49, 17, 28, 47, 31, 45],   # Upper: Dui  ☱
    [14, 38, 30, 21, 50, 64, 56, 35],   # Upper: Li   ☲
    [34, 54, 55, 51, 32, 40, 62, 16],   # Upper: Zhen ☳
    [ 9, 61, 37, 42, 57, 59, 53, 20],   # Upper: Xun  ☴
    [ 5, 60, 63,  3, 48, 29, 39,  8],   # Upper: Kan  ☵
    [26, 41, 22, 27, 18,  4, 52, 23],   # Upper: Gen  ☶
    [11, 19, 36, 24, 46,  7, 15,  2],   # Upper: Kun  ☷
]

# Wu Xing (Five Phases) productive and controlling cycles
WU_XING_PRODUCES = {
    "Wood": "Fire", "Fire": "Earth", "Earth": "Metal",
    "Metal": "Water", "Water": "Wood",
}
WU_XING_CONTROLS = {
    "Wood": "Earth", "Fire": "Metal", "Earth": "Water",
    "Metal": "Wood", "Water": "Fire",
}

LEVEL_NAMES = ["synodic", "year", "month", "day", "hour"]


def _hexagram_from_ki(lower_ki: int, upper_ki: int) -> dict:
    """Form a hexagram from two Ki numbers (lower=stable, upper=changing).

    Returns hexagram number, name, trigram info, and the 6 lines.
    """
    lower = KI_TO_TRIGRAM[lower_ki]
    upper = KI_TO_TRIGRAM[upper_ki]

    hex_num = KING_WEN[upper["idx"]][lower["idx"]]
    lines = lower["lines"] + upper["lines"]  # bottom 3 + top 3

    return {
        "hexagram": hex_num,
        "lower": {
            "ki": lower_ki,
            "trigram": lower["name"],
            "symbol": lower["symbol"],
            "element": lower["element"],
        },
        "upper": {
            "ki": upper_ki,
            "trigram": upper["name"],
            "symbol": upper["symbol"],
            "element": upper["element"],
        },
        "lines": lines,
    }


def _changing_lines(current_ki: int, next_ki: int) -> dict:
    """Compute the changing lines between current and next Ki at a single level.

    Each Ki maps to a trigram (3 lines). The lines that differ are "changing."
    Returns the primary trigram, transformed trigram, and which lines change.
    """
    curr = KI_TO_TRIGRAM[current_ki]
    nxt = KI_TO_TRIGRAM[next_ki]

    changes = []
    for i in range(3):
        if curr["lines"][i] != nxt["lines"][i]:
            direction = "yin→yang" if nxt["lines"][i] == 1 else "yang→yin"
            changes.append({"line": i + 1, "direction": direction})

    return {
        "current": {
            "ki": current_ki,
            "trigram": curr["name"],
            "symbol": curr["symbol"],
            "lines": curr["lines"],
        },
        "next": {
            "ki": next_ki,
            "trigram": nxt["name"],
            "symbol": nxt["symbol"],
            "lines": nxt["lines"],
        },
        "changing_lines": changes,
        "num_changes": len(changes),
    }


def _wu_xing_relationship(elem1: str, elem2: str) -> str:
    """Describe the Wu Xing relationship between two elements."""
    if elem1 == elem2:
        return "same element (resonance)"
    if WU_XING_PRODUCES.get(elem1) == elem2:
        return f"{elem1} GENERATES {elem2} (productive/shēng)"
    if WU_XING_PRODUCES.get(elem2) == elem1:
        return f"{elem2} GENERATES {elem1} (productive/shēng, reverse)"
    if WU_XING_CONTROLS.get(elem1) == elem2:
        return f"{elem1} CONTROLS {elem2} (controlling/kè)"
    if WU_XING_CONTROLS.get(elem2) == elem1:
        return f"{elem2} CONTROLS {elem1} (controlling/kè, reverse)"
    return f"{elem1} → {elem2} (no direct cycle relationship)"


def get_ki_changes(target_date: str = None, birth_date: str = None) -> dict:
    """Compute Ki changes at all levels — Mercury's reading of the Ki field.

    For each level (synodic, year, month, day, hour):
    - Current Ki number and when it changes next
    - Next Ki number after the change
    - Changing lines (trigram transitions)
    - Wu Xing phase relationship of the transition

    For each adjacent pair of levels:
    - The hexagram formed (lower=slower/stable, upper=faster/changing)
    - King Wen number and name

    Optionally includes personal Ki if birth_date is provided.

    Args:
        target_date: ISO date YYYY-MM-DD (default: now)
        birth_date: Birth date YYYY-MM-DD for personal Ki overlay
    """
    from convergence_ki import (
        get_convergence_ki, _year_ki, _find_lichun, _flying_star,
        _dt_to_jd, _jd_to_dt, TRIAD_OF, SIGN_NAMES, TZ as CK_TZ,
    )
    import swisseph as swe

    if target_date:
        td = datetime.fromisoformat(target_date)
        if td.tzinfo is None:
            td = td.replace(tzinfo=TZ)
    else:
        td = datetime.now(TZ)

    # Get current full Ki state
    ki_data = get_convergence_ki(
        target_date=td.strftime("%Y-%m-%d"),
        birth_date=birth_date,
    )

    # Extract current Ki numbers (global)
    synodic_ki = ki_data["synodic"]["ki"]
    year_ki = ki_data["year"]["ki"]
    month_ki = ki_data["month"]["ki"]
    day_ki = ki_data["day"]["ki"]
    hour_ki = ki_data["hour"]["ki"]

    current_global = {
        "synodic": synodic_ki,
        "year": year_ki,
        "month": month_ki,
        "day": day_ki,
        "hour": hour_ki,
    }

    # ── Compute NEXT Ki at each level ──

    # Hour: changes every 2 hours (double-hour boundary)
    local_hour = td.hour
    if local_hour >= 23:
        double_hour = 1
    elif local_hour < 1:
        double_hour = 1
    else:
        double_hour = (local_hour + 1) // 2 + 1

    # Next double-hour start time
    dh_starts = [23, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21]
    if double_hour < 12:
        next_dh_hour = dh_starts[double_hour]  # 0-indexed: double_hour is 1-based, next is +1
        next_hour_dt = td.replace(hour=next_dh_hour, minute=0, second=0, microsecond=0)
        if next_dh_hour <= td.hour:
            next_hour_dt += timedelta(days=1)
    else:
        # Currently in Pig hour (21-23), next is Rat (23:00)
        next_hour_dt = td.replace(hour=23, minute=0, second=0, microsecond=0)
        if td.hour >= 23:
            next_hour_dt += timedelta(days=1)

    next_hour_ki = (hour_ki - 1) % 9
    if next_hour_ki <= 0:
        next_hour_ki += 9

    # Day: changes at midnight (solar day boundary)
    next_day_dt = (td + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    next_day_ki = (day_ki - 1) % 9
    if next_day_ki <= 0:
        next_day_ki += 9

    # Month: changes when Sun crosses next 30° boundary from Lichun
    now_jd = _dt_to_jd(td)
    sun_lon = swe.calc_ut(now_jd, swe.SUN)[0][0]
    # Current month segment (from 315° Lichun)
    deg_from_lichun = (sun_lon - 315) % 360
    current_month_seg = int(deg_from_lichun / 30)
    next_month_deg = (315 + (current_month_seg + 1) * 30) % 360

    # Find when Sun hits next_month_deg
    # Sun moves ~1°/day
    days_to_next = ((next_month_deg - sun_lon) % 360) / 1.0
    approx_jd = now_jd + days_to_next
    # Refine
    for _ in range(20):
        s = swe.calc_ut(approx_jd, swe.SUN)[0][0]
        diff = (next_month_deg - s) % 360
        if diff > 180:
            diff -= 360
        if abs(diff) < 0.001:
            break
        approx_jd += diff / 1.0
    next_month_dt = _jd_to_dt(approx_jd)

    next_month_ki = (month_ki - 1) % 9
    if next_month_ki <= 0:
        next_month_ki += 9

    # Year: changes at Lichun (~Feb 4)
    lichun_year = td.year if (td.month > 2 or (td.month == 2 and td.day >= 4)) else td.year - 1
    next_lichun_jd = _find_lichun(lichun_year + 1)
    next_year_dt = _jd_to_dt(next_lichun_jd)
    next_year_ki = (year_ki - 1) % 9
    if next_year_ki <= 0:
        next_year_ki += 9

    # Synodic: changes at next Jupiter perihelion Lichun (~12 years)
    # Just note it doesn't change soon
    next_synodic_ki = (synodic_ki - 1) % 9
    if next_synodic_ki <= 0:
        next_synodic_ki += 9

    next_global = {
        "synodic": next_synodic_ki,
        "year": next_year_ki,
        "month": next_month_ki,
        "day": next_day_ki,
        "hour": next_hour_ki,
    }

    change_times = {
        "hour": next_hour_dt.isoformat(),
        "day": next_day_dt.isoformat(),
        "month": next_month_dt.strftime("%Y-%m-%d %I:%M %p"),
        "year": next_year_dt.strftime("%Y-%m-%d %I:%M %p"),
        "synodic": "~2034 (next Jupiter perihelion gate)",
    }

    # ── Changing lines at each level ──
    level_changes = {}
    for level in LEVEL_NAMES:
        curr = current_global[level]
        nxt = next_global[level]
        level_changes[level] = _changing_lines(curr, nxt)
        level_changes[level]["changes_at"] = change_times[level]
        # Wu Xing of the transition
        curr_elem = KI_TO_TRIGRAM[curr]["element"]
        nxt_elem = KI_TO_TRIGRAM[nxt]["element"]
        level_changes[level]["wu_xing"] = _wu_xing_relationship(curr_elem, nxt_elem)

    # ── Hexagrams from adjacent level pairs ──
    pairs = [
        ("synodic", "year"),
        ("year", "month"),
        ("month", "day"),
        ("day", "hour"),
    ]

    hexagrams = {}
    for lower_name, upper_name in pairs:
        lower_ki_val = current_global[lower_name]
        upper_ki_val = current_global[upper_name]
        pair_key = f"{lower_name}_{upper_name}"
        hex_info = _hexagram_from_ki(lower_ki_val, upper_ki_val)

        # Wu Xing between the two levels
        wu_xing = _wu_xing_relationship(
            hex_info["lower"]["element"],
            hex_info["upper"]["element"],
        )
        hex_info["wu_xing"] = wu_xing
        hex_info["pair"] = f"{lower_name} (stable) / {upper_name} (changing)"
        hexagrams[pair_key] = hex_info

    # ── Personal Ki changes (if birth_date) ──
    personal = None
    if birth_date and "personal" in ki_data:
        p = ki_data["personal"]
        natal_yki = p["natal_year_ki"]

        personal_current = {
            "synodic": p.get("synodic", {}).get("ki") if p.get("synodic") else None,
            "year": p["year"]["ki"],
            "month": p["month"]["ki"],
            "day": p["day"]["ki"],
            "hour": p["hour"]["ki"],
        }

        # Personal next Ki via flying star on global next
        personal_next = {}
        personal_changes = {}
        personal_hexagrams = {}

        for level in LEVEL_NAMES:
            p_curr = personal_current[level]
            if p_curr is None:
                continue
            p_nxt = _flying_star(natal_yki, next_global[level])
            personal_next[level] = p_nxt
            personal_changes[level] = _changing_lines(p_curr, p_nxt)
            personal_changes[level]["changes_at"] = change_times[level]
            curr_elem = KI_TO_TRIGRAM[p_curr]["element"]
            nxt_elem = KI_TO_TRIGRAM[p_nxt]["element"]
            personal_changes[level]["wu_xing"] = _wu_xing_relationship(curr_elem, nxt_elem)

        for lower_name, upper_name in pairs:
            l_ki = personal_current.get(lower_name)
            u_ki = personal_current.get(upper_name)
            if l_ki and u_ki:
                pair_key = f"{lower_name}_{upper_name}"
                hex_info = _hexagram_from_ki(l_ki, u_ki)
                hex_info["wu_xing"] = _wu_xing_relationship(
                    hex_info["lower"]["element"],
                    hex_info["upper"]["element"],
                )
                hex_info["pair"] = f"{lower_name} (stable) / {upper_name} (changing)"
                personal_hexagrams[pair_key] = hex_info

        personal = {
            "current": personal_current,
            "next": personal_next,
            "level_changes": personal_changes,
            "hexagrams": personal_hexagrams,
        }

    return {
        "timestamp": td.isoformat(),
        "global": {
            "current": current_global,
            "next": next_global,
            "change_times": change_times,
        },
        "level_changes": level_changes,
        "hexagrams": hexagrams,
        "personal": personal,
        "note": "Mercury reads the delta. Lower trigram = slower level (stable ground). Upper trigram = faster level (what's cycling). Changing lines = the transition within each level from current to next Ki.",
    }


NUM_WORDS = {
    1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE",
    6: "SIX", 7: "SEVEN", 8: "EIGHT", 9: "NINE", 10: "TEN",
    11: "ELEVEN", 12: "TWELVE", 13: "THIRTEEN", 14: "FOURTEEN",
    15: "FIFTEEN", 16: "SIXTEEN", 17: "SEVENTEEN", 18: "EIGHTEEN",
    19: "NINETEEN", 20: "TWENTY", 21: "TWENTY-ONE", 22: "TWENTY-TWO",
    23: "TWENTY-THREE", 24: "TWENTY-FOUR", 25: "TWENTY-FIVE",
    26: "TWENTY-SIX", 27: "TWENTY-SEVEN", 28: "TWENTY-EIGHT",
    29: "TWENTY-NINE", 30: "THIRTY", 31: "THIRTY-ONE",
    32: "THIRTY-TWO", 33: "THIRTY-THREE", 34: "THIRTY-FOUR",
    35: "THIRTY-FIVE", 36: "THIRTY-SIX", 37: "THIRTY-SEVEN",
    38: "THIRTY-EIGHT", 39: "THIRTY-NINE", 40: "FORTY",
    41: "FORTY-ONE", 42: "FORTY-TWO", 43: "FORTY-THREE",
    44: "FORTY-FOUR", 45: "FORTY-FIVE", 46: "FORTY-SIX",
    47: "FORTY-SEVEN", 48: "FORTY-EIGHT", 49: "FORTY-NINE",
    50: "FIFTY", 51: "FIFTY-ONE", 52: "FIFTY-TWO", 53: "FIFTY-THREE",
    54: "FIFTY-FOUR", 55: "FIFTY-FIVE", 56: "FIFTY-SIX",
    57: "FIFTY-SEVEN", 58: "FIFTY-EIGHT", 59: "FIFTY-NINE",
    60: "SIXTY", 61: "SIXTY-ONE", 62: "SIXTY-TWO", 63: "SIXTY-THREE",
    64: "SIXTY-FOUR",
}

LINE_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def lookup_hexagram_gnostic(hex_num: int, changing_lines: list = None) -> dict:
    """Search Neo4j for Gnostic Book of Changes content for a hexagram.

    Returns the full line text for each changing line including:
    - All translator versions (Legge, Wilhelm, Blofeld, Liu, etc.)
    - Confucian commentary
    - Editor's commentary with quotes
    - Lettered statements (A, B, C, D...)

    Args:
        hex_num: King Wen hexagram number (1-64)
        changing_lines: List of changing line numbers (1-6)

    Returns:
        Dict with judgment text, full line texts, and chunk references.
    """
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "selene_gnosis"))

        results = {"hexagram": hex_num, "judgment": None, "line_readings": {}}

        with driver.session() as session:
            # ── Get judgment/title text ──
            num_word = NUM_WORDS.get(hex_num, "")
            # Hex marker patterns used in Gnostic I Ching chunks
            # Format varies: "24 -- Return -- 24" or "-- 24 --" or just the number
            hex_marker = f"{hex_num} -- "

            # Try HEXAGRAM NUMBER pattern first (most reliable for title chunk)
            if num_word:
                recs = session.run("""
                    MATCH (i:Interpretation)
                    WHERE i.source_title CONTAINS 'Gnostic Book of Changes'
                      AND i.text CONTAINS $pattern
                    RETURN i.text
                    ORDER BY size(i.text) DESC
                    LIMIT 1
                """, pattern=f"HEXAGRAM NUMBER {num_word}").data()

                if recs:
                    text = recs[0]["i.text"]
                    idx = text.find(f"HEXAGRAM NUMBER {num_word}")
                    if idx >= 0:
                        results["judgment"] = text[idx:idx+1500]

            # ── Get changing line texts ──
            if changing_lines:
                for line_num in changing_lines:
                    line_word = LINE_WORDS.get(line_num, str(line_num))

                    # Search for the Line-N marker (format used in Gnostic I Ching)
                    # and also "Line N" / "line N" in context of this hexagram
                    for search_pattern in [
                        f"Line-{line_num}",
                        f"Legge: The {line_word}",
                        f"Legge: Line {line_word}",
                    ]:
                        recs = session.run("""
                            MATCH (i:Interpretation)
                            WHERE i.source_title CONTAINS 'Gnostic Book of Changes'
                              AND i.text CONTAINS $line_pattern
                              AND i.text CONTAINS $hex_marker
                            RETURN i.text
                            ORDER BY size(i.text) DESC
                            LIMIT 1
                        """, line_pattern=search_pattern, hex_marker=hex_marker).data()

                        if recs:
                            text = recs[0]["i.text"]
                            # Find the line section start
                            line_start = -1
                            for marker in [f"Line-{line_num}", f"Legge: The {line_word}",
                                           f"Legge: Line {line_word}"]:
                                idx = text.find(marker)
                                if idx >= 0:
                                    line_start = idx
                                    break

                            if line_start >= 0:
                                # Find the end: next Line-N marker or end of chunk
                                line_end = len(text)
                                next_line = line_num + 1
                                for end_marker in [
                                    f"Line-{next_line}",
                                    f"Legge: The {LINE_WORDS.get(next_line, '')}",
                                    f"Legge: Line {LINE_WORDS.get(next_line, '')}",
                                ]:
                                    eidx = text.find(end_marker, line_start + 20)
                                    if eidx > 0 and eidx < line_end:
                                        line_end = eidx

                                # Grab the Editor/Notes section BEFORE the line marker.
                                # In the Gnostic I Ching, the pattern is:
                                #   Editor: [commentary]
                                #   [quotes]
                                #   A. [statement]
                                #   B. [statement]
                                #   24 -- Return -- 24
                                #   C. [more statements]
                                #   Line-4
                                #   Legge: [translations]
                                #   COMMENTARY
                                # So we need to go back to "Editor:" or "NOTES AND PARAPHRASES"
                                editor_start = line_start
                                for back_marker in ["Editor:", "NOTES AND PARAPHRASES"]:
                                    bidx = text.rfind(back_marker, max(0, line_start - 3000), line_start)
                                    if bidx >= 0 and bidx < editor_start:
                                        editor_start = bidx

                                full_line_text = text[editor_start:line_end].strip()
                                results["line_readings"][line_num] = full_line_text
                            break

                    # If we still didn't find it, try broader search
                    if line_num not in results["line_readings"]:
                        recs = session.run("""
                            MATCH (i:Interpretation)
                            WHERE i.source_title CONTAINS 'Gnostic Book of Changes'
                              AND i.text CONTAINS $hex_marker
                              AND i.text CONTAINS $editor_marker
                            RETURN i.text
                            ORDER BY size(i.text) DESC
                            LIMIT 3
                        """, hex_marker=hex_marker, editor_marker="Editor:").data()

                        for r in recs:
                            text = r["i.text"]
                            # Check if this chunk has our line
                            for marker in [f"Line-{line_num}", f"line {line_word}"]:
                                if marker.lower() in text.lower():
                                    idx = text.lower().find(marker.lower())
                                    # Get from Editor section before this line to end
                                    editor_idx = text.rfind("Editor:", max(0, idx - 3000), idx)
                                    if editor_idx < 0:
                                        editor_idx = max(0, idx - 500)
                                    line_end = len(text)
                                    next_line = line_num + 1
                                    for em in [f"Line-{next_line}", f"line {LINE_WORDS.get(next_line, '')}"]:
                                        eidx = text.lower().find(em.lower(), idx + 20)
                                        if eidx > 0 and eidx < line_end:
                                            line_end = eidx
                                    results["line_readings"][line_num] = text[editor_idx:line_end].strip()
                                    break
                            if line_num in results["line_readings"]:
                                break

        driver.close()
        return results

    except Exception as e:
        return {"hexagram": hex_num, "error": str(e), "line_readings": {}}


def _get_transformed_hex(lower_ki: int, next_upper_ki: int) -> int:
    """Get the transformed hexagram number after the upper trigram changes."""
    lower = KI_TO_TRIGRAM[lower_ki]
    upper = KI_TO_TRIGRAM[next_upper_ki]
    return KING_WEN[upper["idx"]][lower["idx"]]


def format_ki_changes_full(data: dict, personal: bool = True) -> str:
    """Format Ki changes — FULL STACK view (compact).

    Shows hexagram diagram + judgment + transformed hexagram for each pair.
    Does NOT include individual changing line readings (use individual level
    tools like ki_change_day for that).

    Args:
        data: Output from get_ki_changes()
        personal: If True and personal data exists, show personal hexagrams
    """
    lines = []
    lines.append("═══ KI CHANGES — MERCURY'S READING ═══")
    lines.append(f"Timestamp: {data['timestamp']}")
    lines.append("")

    # Determine which hexagram set to use
    if personal and data.get("personal"):
        p = data["personal"]
        pc = p["current"]
        pn = p["next"]
        levels_str = ".".join(str(pc.get(l, "?")) for l in LEVEL_NAMES)
        next_str = ".".join(str(pn.get(l, "?")) for l in LEVEL_NAMES)
        lines.append(f"PERSONAL: {levels_str}")
        lines.append(f"NEXT:     {next_str}")
        lines.append("")

        hex_source = p.get("hexagrams", {})
        ki_current = pc
        ki_next = pn
    else:
        g = data["global"]
        curr = g["current"]
        nxt = g["next"]
        lines.append(f"GLOBAL: {curr['synodic']}.{curr['year']}.{curr['month']}.{curr['day']}.{curr['hour']}")
        lines.append(f"NEXT:   {nxt['synodic']}.{nxt['year']}.{nxt['month']}.{nxt['day']}.{nxt['hour']}")
        lines.append("")

        hex_source = data.get("hexagrams", {})
        ki_current = curr
        ki_next = nxt

    pairs = [
        ("synodic", "year", "synodic_year"),
        ("year", "month", "year_month"),
        ("month", "day", "month_day"),
        ("day", "hour", "day_hour"),
    ]

    for lower_name, upper_name, pair_key in pairs:
        if pair_key not in hex_source:
            continue

        hx = hex_source[pair_key]
        lower_ki = hx["lower"]["ki"]
        upper_ki = hx["upper"]["ki"]

        # Get next upper Ki for this pair
        next_upper_ki = ki_next.get(upper_name)
        if next_upper_ki is None:
            continue

        lower_tri = KI_TO_TRIGRAM[lower_ki]
        upper_tri = KI_TO_TRIGRAM[upper_ki]
        next_upper_tri = KI_TO_TRIGRAM[next_upper_ki]

        # Full hexagram lines and changing lines
        hex_lines = lower_tri["lines"] + upper_tri["lines"]
        next_hex_lines = lower_tri["lines"] + next_upper_tri["lines"]

        changing = []
        for i in range(6):
            if hex_lines[i] != next_hex_lines[i]:
                direction = "yin→yang" if next_hex_lines[i] == 1 else "yang→yin"
                changing.append({"line": i + 1, "direction": direction})

        # Transformed hexagram
        transformed_num = _get_transformed_hex(lower_ki, next_upper_ki)

        lines.append(f"{'═' * 60}")
        lines.append(f"HEXAGRAM {hx['hexagram']} — {lower_name.upper()}/{upper_name.upper()}")
        lines.append(f"  {upper_tri['symbol']} {upper_tri['name']} above  (Ki {upper_ki})")
        lines.append(f"  {lower_tri['symbol']} {lower_tri['name']} below  (Ki {lower_ki})")
        lines.append(f"  Wu Xing: {hx.get('wu_xing', '')}")
        lines.append("")

        # Line diagram (top to bottom)
        for i in range(5, -1, -1):
            val = hex_lines[i]
            is_changing = any(c["line"] == i + 1 for c in changing)
            sym = "━━━━━" if val == 1 else "━━ ━━"
            marker = ""
            if is_changing:
                ch = [c for c in changing if c["line"] == i + 1][0]
                marker = f" ← ({ch['direction']})"
            lines.append(f"  Line {i+1}: {sym}{marker}")

        lines.append("")

        if changing:
            ch_str = ", ".join(str(c["line"]) for c in changing)
            lines.append(f"  Changing lines: {ch_str}")
            lines.append(f"  → Transforms to: Hexagram {transformed_num}")
        else:
            lines.append(f"  No changing lines (pure hexagram)")
        lines.append("")

        # ── Gnostic I Ching lookup (judgment only for full stack) ──
        gnostic = lookup_hexagram_gnostic(hx["hexagram"])

        if gnostic.get("judgment"):
            lines.append(f"  JUDGMENT:")
            judgment = gnostic["judgment"][:800]
            for jl in judgment.split("\n"):
                lines.append(f"  {jl}")
            lines.append("")

        lines.append("")

    return "\n".join(lines)


def format_ki_changes(data: dict, include_gnostic: bool = True) -> str:
    """Format Ki changes output — compact version without Gnostic text.

    Args:
        data: Output from get_ki_changes()
        include_gnostic: Ignored (kept for backward compat). Use format_ki_changes_full for Gnostic text.
    """
    lines = []
    lines.append("═══ KI CHANGES — MERCURY'S READING ═══")
    lines.append(f"Timestamp: {data['timestamp']}")
    lines.append("")

    # Global current state
    g = data["global"]
    curr = g["current"]
    lines.append(f"CURRENT: {curr['synodic']}.{curr['year']}.{curr['month']}.{curr['day']}.{curr['hour']}")
    nxt = g["next"]
    lines.append(f"NEXT:    {nxt['synodic']}.{nxt['year']}.{nxt['month']}.{nxt['day']}.{nxt['hour']}")
    lines.append("")

    # Level changes
    lines.append("── TRANSITIONS (when each level shifts) ──")
    for level in LEVEL_NAMES:
        lc = data["level_changes"][level]
        curr_t = lc["current"]
        next_t = lc["next"]
        n_ch = lc["num_changes"]
        changes_str = ", ".join(
            f"L{c['line']} {c['direction']}" for c in lc["changing_lines"]
        ) if n_ch > 0 else "no change (same trigram)"

        lines.append(f"  {level.upper():>8}: {curr_t['ki']} {curr_t['symbol']} {curr_t['trigram']}"
                      f" → {next_t['ki']} {next_t['symbol']} {next_t['trigram']}"
                      f"  [{changes_str}]")
        lines.append(f"           Wu Xing: {lc['wu_xing']}")
        lines.append(f"           Changes: {lc['changes_at']}")
        lines.append("")

    # Hexagrams
    lines.append("── HEXAGRAMS (level pairs) ──")
    for pair_key, hx in data["hexagrams"].items():
        lines.append(f"  {hx['pair']}")
        lines.append(f"    {hx['upper']['symbol']} {hx['upper']['trigram']} (above)"
                      f"  Ki {hx['upper']['ki']}")
        lines.append(f"    {hx['lower']['symbol']} {hx['lower']['trigram']} (below)"
                      f"  Ki {hx['lower']['ki']}")
        lines.append(f"    = Hexagram {hx['hexagram']}")
        lines.append(f"    Wu Xing: {hx['wu_xing']}")
        lines.append("")

    # Personal
    if data.get("personal"):
        p = data["personal"]
        lines.append("── PERSONAL KI CHANGES ──")
        pc = p["current"]
        pn = p["next"]
        levels_str = ".".join(str(pc.get(l, "?")) for l in LEVEL_NAMES)
        next_str = ".".join(str(pn.get(l, "?")) for l in LEVEL_NAMES)
        lines.append(f"  CURRENT: {levels_str}")
        lines.append(f"  NEXT:    {next_str}")
        lines.append("")

        for level in LEVEL_NAMES:
            if level not in p["level_changes"]:
                continue
            lc = p["level_changes"][level]
            curr_t = lc["current"]
            next_t = lc["next"]
            n_ch = lc["num_changes"]
            changes_str = ", ".join(
                f"L{c['line']} {c['direction']}" for c in lc["changing_lines"]
            ) if n_ch > 0 else "no change"
            lines.append(f"  {level.upper():>8}: {curr_t['ki']} {curr_t['symbol']}"
                          f" → {next_t['ki']} {next_t['symbol']}"
                          f"  [{changes_str}]")
        lines.append("")

        lines.append("  PERSONAL HEXAGRAMS:")
        for pair_key, hx in p["hexagrams"].items():
            lines.append(f"    {hx['pair']}: Hex {hx['hexagram']}"
                          f" ({hx['lower']['symbol']}/{hx['upper']['symbol']})"
                          f" — {hx['wu_xing']}")
        lines.append("")

    return "\n".join(lines)
