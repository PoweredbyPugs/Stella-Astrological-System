"""Convergence Ki — Astronomical Ki calculation using the 15° grid.

Three bodies cross the same 12 mid-sign gates (15° of each sign) at three speeds:
  Sun:       12 gates in 1 year        → each gate = 1 month (~30 days)
  Moon:      12 gates in 1 sid. month  → each gate = 1 lunar gate (~2.3 days)
  Ascendant: 12 gates in 1 sid. day   → each gate = 1 mid-sign hour (~2 hrs)

Same grid. Same 12. Same 15°. Same 9 Ki numbers. Same remainder 3. Same triad lock.
One relationship, three octaves.

Convergence sockets (15° Aquarius, Gemini, Libra) are a subset of the 12 mid-sign gates
— the air trine, where the 9-fold and 15-fold grids converge (LCM=120°). The Moon
crosses these every ~9.09 days, giving the traditional day Ki rhythm.

Research: stella/research/convergence-sockets.md
"""

import swisseph as swe
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Config ──
EPHE_PATH = "/mnt/baratie/baratie/sweph-service/ephemeris"
swe.set_ephe_path(EPHE_PATH)
TZ = ZoneInfo("America/New_York")

SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

CONVERGENCE_SOCKETS = {
    315.0: {"name": "S1", "sign": "15° Aquarius", "role": "Lichun / Year Start"},
    75.0:  {"name": "S2", "sign": "15° Gemini",   "role": "Center / Pivot"},
    195.0: {"name": "S3", "sign": "15° Libra",    "role": "Completion"},
}

TRIAD_OF = {1: "Man", 2: "Earth", 3: "Heaven", 4: "Man", 5: "Earth",
            6: "Heaven", 7: "Man", 8: "Earth", 9: "Heaven"}

TRIAD_NUMBERS = {"Man": [1, 4, 7], "Earth": [2, 5, 8], "Heaven": [3, 6, 9]}

# Gate triad: cycles Man → Heaven → Earth every 15° starting from 0° Aries
GATE_TRIAD_CYCLE = ["Man", "Heaven", "Earth"]

# Mid-sign gates: 15° of each sign (the 12 gates shared by all three bodies)
MID_SIGN_GATES = {
    15.0:  {"sign": "15° Aries",       "sign_idx": 0},
    45.0:  {"sign": "15° Taurus",      "sign_idx": 1},
    75.0:  {"sign": "15° Gemini",      "sign_idx": 2,  "socket": "S2"},
    105.0: {"sign": "15° Cancer",      "sign_idx": 3},
    135.0: {"sign": "15° Leo",         "sign_idx": 4},
    165.0: {"sign": "15° Virgo",       "sign_idx": 5},
    195.0: {"sign": "15° Libra",       "sign_idx": 6,  "socket": "S3"},
    225.0: {"sign": "15° Scorpio",     "sign_idx": 7},
    255.0: {"sign": "15° Sagittarius", "sign_idx": 8},
    285.0: {"sign": "15° Capricorn",   "sign_idx": 9},
    315.0: {"sign": "15° Aquarius",    "sign_idx": 10, "socket": "S1"},
    345.0: {"sign": "15° Pisces",      "sign_idx": 11},
}


# ── Helpers ──

def _dt_to_jd(dt: datetime) -> float:
    utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt
    return swe.julday(utc.year, utc.month, utc.day,
                      utc.hour + utc.minute / 60.0 + utc.second / 3600.0)


def _jd_to_dt(jd: float, tz: ZoneInfo = TZ) -> datetime:
    y, m, d, h = swe.revjul(jd)
    hr = int(h)
    mn = int((h - hr) * 60)
    sec = int(((h - hr) * 60 - mn) * 60)
    return datetime(y, m, d, hr, mn, sec, tzinfo=timezone.utc).astimezone(tz)


def _year_ki(year: int, month: int, day: int) -> int:
    """Calculate year Ki for a given date. Ki year changes Feb 4."""
    ki_year = year if (month > 2 or (month == 2 and day >= 4)) else year - 1
    digit_sum = sum(int(d) for d in str(ki_year))
    while digit_sum > 9:
        digit_sum = sum(int(d) for d in str(digit_sum))
    ki = (11 - digit_sum) % 9
    return ki if ki != 0 else 9


def _find_moon_socket_crossings(start_jd: float, end_jd: float) -> list:
    """Find all Moon crossings of convergence sockets in a JD range."""
    crossings = []
    jd = start_jd
    prev_lon = None
    step = 1.0 / 24.0  # hourly steps

    while jd < end_jd:
        moon = swe.calc_ut(jd, swe.MOON)[0]
        lon = moon[0]

        if prev_lon is not None:
            for target_deg, info in CONVERGENCE_SOCKETS.items():
                prev_dist = (target_deg - prev_lon) % 360
                curr_dist = (target_deg - lon) % 360
                if 0 < prev_dist < 15 and curr_dist > 345:
                    # Refine with binary search
                    lo, hi = jd - step, jd
                    for _ in range(20):
                        mid = (lo + hi) / 2
                        mid_lon = swe.calc_ut(mid, swe.MOON)[0][0]
                        mid_dist = (target_deg - mid_lon) % 360
                        if mid_dist > 180:
                            lo = mid
                        else:
                            hi = mid
                    crossings.append({
                        "jd": (lo + hi) / 2,
                        "socket": info["name"],
                        "degree": target_deg,
                        "sign": info["sign"],
                        "role": info["role"],
                    })

        prev_lon = lon
        jd += step

    crossings.sort(key=lambda c: c["jd"])
    return crossings


def _find_moon_midsign_crossings(start_jd: float, end_jd: float) -> list:
    """Find all Moon crossings of mid-sign gates (15° of each sign) in a JD range."""
    crossings = []
    jd = start_jd
    prev_lon = None
    step = 1.0 / 24.0  # hourly steps

    while jd < end_jd:
        moon = swe.calc_ut(jd, swe.MOON)[0]
        lon = moon[0]

        if prev_lon is not None:
            for target_deg, info in MID_SIGN_GATES.items():
                prev_dist = (target_deg - prev_lon) % 360
                curr_dist = (target_deg - lon) % 360
                if 0 < prev_dist < 15 and curr_dist > 345:
                    # Refine with binary search
                    lo, hi = jd - step, jd
                    for _ in range(20):
                        mid = (lo + hi) / 2
                        mid_lon = swe.calc_ut(mid, swe.MOON)[0][0]
                        mid_dist = (target_deg - mid_lon) % 360
                        if mid_dist > 180:
                            lo = mid
                        else:
                            hi = mid
                    crossings.append({
                        "jd": (lo + hi) / 2,
                        "gate": target_deg,
                        "sign": info["sign"],
                        "sign_idx": info["sign_idx"],
                        "is_socket": "socket" in info,
                        "socket": info.get("socket"),
                    })

        prev_lon = lon
        jd += step

    crossings.sort(key=lambda c: c["jd"])
    return crossings


def _find_moon_sidereal_month_start(target_jd: float) -> float:
    """Find the most recent Moon crossing of S1 (15° Aquarius) before target_jd.

    This marks the start of the current sidereal month for lunar gate counting.
    """
    # Search backward up to 30 days
    crossings = _find_moon_socket_crossings(target_jd - 30, target_jd)
    s1_crossings = [c for c in crossings if c["socket"] == "S1" and c["jd"] <= target_jd]
    if s1_crossings:
        return s1_crossings[-1]["jd"]
    # Fallback: search further back
    crossings = _find_moon_socket_crossings(target_jd - 60, target_jd - 30)
    s1_crossings = [c for c in crossings if c["socket"] == "S1"]
    return s1_crossings[-1]["jd"] if s1_crossings else target_jd


def _find_lichun(year: int) -> float:
    """Find exact Julian Day of Lichun (Sun at 315° ecliptic) for a given year."""
    jd = swe.julday(year, 2, 4, 0.0)
    for _ in range(50):
        sun_lon = swe.calc_ut(jd, swe.SUN)[0][0]
        diff = (315.0 - sun_lon) % 360
        if diff > 180:
            diff -= 360
        if abs(diff) < 0.0001:
            break
        jd += diff / 1.0  # Sun moves ~1°/day
    return jd


def gate_triad(ecliptic_lon: float) -> str:
    """Get the permanently locked triad for any ecliptic longitude."""
    gate_idx = int(ecliptic_lon / 15) % 24
    return GATE_TRIAD_CYCLE[gate_idx % 3]


def gate_label(ecliptic_lon: float) -> str:
    """Human-readable gate label for an ecliptic longitude."""
    gate = int(ecliptic_lon / 15) * 15
    sign_idx = gate // 30
    deg = gate % 30
    return f"{deg}° {SIGN_NAMES[sign_idx]}"


# ── Public API ──

def _find_jupiter_perihelion(near_year: float) -> float:
    """Find exact Julian Day of Jupiter's perihelion nearest to a given year.

    Jupiter's perihelion (~14-16° Aries) occurs every ~11.86 years.
    Uses heliocentric distance minimization.
    """
    # Start search 6 years before target
    jd = swe.julday(int(near_year) - 6, 1, 1, 0.0)
    end_jd = swe.julday(int(near_year) + 7, 1, 1, 0.0)

    # Sample every 10 days, find distance minimum
    distances = []
    while jd < end_jd:
        dist = swe.calc_ut(jd, swe.JUPITER, swe.FLG_HELCTR)[0][2]
        distances.append((jd, dist))
        jd += 10

    # Find local minimum closest to target year
    target_jd = swe.julday(int(near_year), 6, 1, 0.0)
    best = None
    for i in range(1, len(distances) - 1):
        if distances[i][1] < distances[i-1][1] and distances[i][1] < distances[i+1][1]:
            if best is None or abs(distances[i][0] - target_jd) < abs(best[0] - target_jd):
                best = distances[i]

    if best is None:
        return swe.julday(int(near_year), 1, 1, 0.0)

    # Refine with golden section search
    lo, hi = best[0] - 10, best[0] + 10
    for _ in range(50):
        m1 = lo + (hi - lo) / 3
        m2 = lo + 2 * (hi - lo) / 3
        d1 = swe.calc_ut(m1, swe.JUPITER, swe.FLG_HELCTR)[0][2]
        d2 = swe.calc_ut(m2, swe.JUPITER, swe.FLG_HELCTR)[0][2]
        if d1 < d2:
            hi = m2
        else:
            lo = m1
    return (lo + hi) / 2


def get_synodic_gate(target_date: str = None, birth_date: str = None) -> dict:
    """Calculate the Synodic Gate Ki — the ~12-year Jupiter cycle level.

    The Sun orbits the solar system's barycenter with a dominant period of
    ~11.86 years (Jupiter's orbital period). Jupiter's perihelion marks the
    peak gravitational coupling. The synodic gate starts at the Lichun
    preceding perihelion, following the same pattern as all other Ki levels:
    the gate before the astronomical event.

    12 years per synodic gate, 9 Ki count → remainder 3 → triad-locked.
    At each synodic gate boundary, the year Ki is always Earth (2, 5, 8).
    This mirrors month/day/hour always being Earth at Lichun.

    9 synodic gates = one full cycle = ~108 years.

    Args:
        target_date: ISO date YYYY-MM-DD (default: today)
        birth_date: Birth date YYYY-MM-DD for personal synodic Ki
    """
    if target_date:
        td = datetime.fromisoformat(target_date)
        if td.tzinfo is None:
            td = td.replace(tzinfo=TZ)
    else:
        td = datetime.now(TZ)

    # Find current and surrounding Jupiter perihelia
    current_year = td.year + td.month / 12
    peri_jd = _find_jupiter_perihelion(current_year)
    peri_dt = _jd_to_dt(peri_jd)

    # Find the Lichun preceding this perihelion
    # Lichun is ~Feb 4. If perihelion is after Feb 4, use same year's Lichun.
    # If before, use previous year's Lichun.
    peri_year = peri_dt.year
    peri_month = peri_dt.month
    if peri_month >= 2 and peri_dt.day >= 4:
        lichun_year_for_gate = peri_year
    elif peri_month > 2:
        lichun_year_for_gate = peri_year
    else:
        lichun_year_for_gate = peri_year - 1

    gate_lichun_jd = _find_lichun(lichun_year_for_gate)
    gate_lichun_dt = _jd_to_dt(gate_lichun_jd)

    # Year Ki at the synodic gate boundary (Lichun preceding perihelion)
    # Use the Ki year that STARTS at this Lichun (the lichun_year itself)
    gate_year_ki = _year_ki(lichun_year_for_gate, 2, 4)  # Feb 4 ensures we get this year's Ki

    # Are we past this gate's perihelion? If so, check if we're closer to next gate
    now_jd = _dt_to_jd(td)
    if now_jd > peri_jd:
        # We're past perihelion — still in this gate (it runs ~12 years)
        pass

    # Find previous perihelion to determine gate boundaries
    prev_peri_jd = _find_jupiter_perihelion(current_year - 12)
    prev_peri_dt = _jd_to_dt(prev_peri_jd)
    next_peri_jd = _find_jupiter_perihelion(current_year + 12)
    next_peri_dt = _jd_to_dt(next_peri_jd)

    # Determine which synodic gate we're in:
    # Gate boundary = Lichun preceding each perihelion
    # Check if we're between current gate Lichun and next gate Lichun
    if peri_month >= 2:
        next_gate_lichun_year = peri_year + int(round((next_peri_jd - peri_jd) / 365.25))
    else:
        next_gate_lichun_year = peri_year - 1 + int(round((next_peri_jd - peri_jd) / 365.25))

    # Recalculate: find which gate we're actually in
    # Find the most recent Lichun-before-perihelion that's in the past
    if now_jd >= gate_lichun_jd:
        current_gate_lichun = gate_lichun_jd
        current_gate_year_ki = gate_year_ki
        current_peri = peri_jd
    else:
        # We're before this gate's Lichun — use previous gate
        current_peri = prev_peri_jd
        prev_peri_dt_check = _jd_to_dt(prev_peri_jd)
        if prev_peri_dt_check.month > 2 or (prev_peri_dt_check.month == 2 and prev_peri_dt_check.day >= 4):
            prev_lichun_year = prev_peri_dt_check.year
        else:
            prev_lichun_year = prev_peri_dt_check.year - 1
        current_gate_lichun = _find_lichun(prev_lichun_year)
        current_gate_year_ki = _year_ki(prev_peri_dt_check.year, prev_peri_dt_check.month, prev_peri_dt_check.day)

    # Synodic gate Ki: count backwards through perihelia to find position in 9-cycle
    # We use the year Ki at each gate boundary (always Earth: 2, 5, 8)
    # and the synodic Ki descends 9, 8, 7... one per gate
    # To determine current synodic Ki, we count perihelia mod 9 from a reference
    # Reference: find a chain of perihelia and their gate year Ki values
    perihelia_chain = []
    for offset in range(-9, 3):
        yr = current_year + offset * 11.86
        pjd = _find_jupiter_perihelion(yr)
        pdt = _jd_to_dt(pjd)
        if pdt.month > 2 or (pdt.month == 2 and pdt.day >= 4):
            ly = pdt.year
        else:
            ly = pdt.year - 1
        yki = _year_ki(ly, 2, 4)  # Year Ki that starts at this Lichun
        perihelia_chain.append({
            "perihelion": pdt.strftime("%Y-%m-%d"),
            "lichun_year": ly,
            "year_ki": yki,
        })

    # Find our gate in the chain
    current_gate_idx = None
    for i, pc in enumerate(perihelia_chain):
        pdt_check = datetime.fromisoformat(pc["perihelion"])
        if pdt_check.year == peri_dt.year and abs(pdt_check.month - peri_dt.month) <= 2:
            current_gate_idx = i
            break

    # Synodic Ki: the gate_year_ki at the current gate tells us the Earth sub-value
    # Earth cycle at boundaries: 8, 5, 2, 8, 5, 2... (same pattern as month at Lichun)
    # Map: gate_year_ki 8 → synodic position in 3-cycle; then extend to 9
    # The synodic Ki descends. We anchor using the Earth year pattern.
    # Earth years at gate boundaries cycle: 5, 8, 2, 5, 8, 2... (verified for 2022=5)
    # Synodic Ki mapping via -3 cascade:
    #   Synodic 8 → year 5, Synodic 5 → year 2, Synodic 2 → year 8
    #   Synodic 7 → year 4... wait, 4 isn't Earth.
    # Actually: at EACH gate boundary, year is Earth. Synodic goes through ALL 9.
    # The -3 cascade: synodic_ki - 3 → year_ki at boundary (modular within Earth)

    # Derive synodic Ki from gate year Ki using the cascade pattern:
    # When synodic is Man (1,4,7): year starts 8 (Earth)
    # When synodic is Earth (2,5,8): year starts 2 (Earth)
    # When synodic is Heaven (3,6,9): year starts 5 (Earth)
    # This mirrors: when year is Man→month 8, year Earth→month 2, year Heaven→month 5
    year_to_synodic = {
        8: [1, 4, 7],  # Man synodic → year 8
        2: [2, 5, 8],  # Earth synodic → year 2
        5: [3, 6, 9],  # Heaven synodic → year 5
    }

    # But we need to know WHICH of the 3 in each triad. Use the 9-cycle position.
    # Track the descending pattern across perihelia
    gate_year_kis = [pc["year_ki"] for pc in perihelia_chain]

    # The synodic Ki descends by 1 each gate. We need one anchor point.
    # Anchor: current gate (2022/2023) has year_ki = 5, synodic = 8
    # From this, count forward/backward
    if current_gate_idx is not None:
        anchor_synodic = 8  # Verified: Lichun 2022, year Ki 5, synodic 8
        synodic_ki = ((anchor_synodic - (current_gate_idx - current_gate_idx)) % 9) or 9
        # Actually, anchor at current gate = synodic 8
        synodic_ki = 8  # Current gate is 8

        # For other gates, count from anchor
        gate_synodic_map = {}
        for i, pc in enumerate(perihelia_chain):
            offset = i - current_gate_idx
            ski = ((8 - offset - 1) % 9) + 1
            gate_synodic_map[i] = ski
            pc["synodic_ki"] = ski

        synodic_ki = gate_synodic_map.get(current_gate_idx, 8)
    else:
        synodic_ki = 8  # fallback

    # Progress through current synodic gate
    current_peri_dt = _jd_to_dt(current_peri)
    orbital_period = (next_peri_jd - peri_jd) / 365.25
    years_into_gate = (now_jd - current_gate_lichun) / 365.25
    gate_length_years = orbital_period  # ~11.86 years

    # Personal synodic Ki
    personal_synodic = None
    if birth_date:
        bd = datetime.fromisoformat(birth_date)
        natal_yki = _year_ki(bd.year, bd.month, bd.day)
        personal_synodic = _flying_star(natal_yki, synodic_ki)

    result = {
        "synodic_gate": {
            "ki": synodic_ki,
            "triad": TRIAD_OF[synodic_ki],
            "element": "Earth" if synodic_ki in [2, 5, 8] else ("Man" if synodic_ki in [1, 4, 7] else "Heaven"),
        },
        "current_perihelion": {
            "date": peri_dt.strftime("%Y-%m-%d"),
            "distance_au": round(swe.calc_ut(peri_jd, swe.JUPITER, swe.FLG_HELCTR)[0][2], 4),
        },
        "gate_boundary": {
            "lichun_date": gate_lichun_dt.strftime("%Y-%m-%d"),
            "year_ki_at_boundary": gate_year_ki,
            "year_ki_triad": TRIAD_OF[gate_year_ki],
        },
        "progress": {
            "years_into_gate": round(years_into_gate, 2),
            "gate_length_years": round(gate_length_years, 2),
            "percent": round(years_into_gate / gate_length_years * 100, 1),
        },
        "next_perihelion": {
            "date": next_peri_dt.strftime("%Y-%m-%d"),
        },
        "orbital_period_years": round(orbital_period, 3),
        "cycle_108": {
            "gates_per_cycle": 9,
            "years_per_cycle": "~108",
            "current_gate_position": f"{synodic_ki}/9",
        },
        "perihelia_chain": perihelia_chain,
    }

    if personal_synodic is not None:
        result["personal_synodic"] = {
            "ki": personal_synodic,
            "triad": TRIAD_OF[personal_synodic],
            "natal_year_ki": natal_yki,
        }

    return result


def _flying_star(natal_ki: int, global_ki: int) -> int:
    """Apply Flying Star transformation to convert global Ki to personal Ki.

    Uses the Lo Shu Flying Star sequence [5,6,7,8,9,1,2,3,4].
    Personal Ki = natal Ki's position when global Ki occupies the center.
    Applied independently to each level (year, month, day, hour).
    """
    FLYING_SEQUENCE = [5, 6, 7, 8, 9, 1, 2, 3, 4]
    NUM_TO_IDX = {n: i for i, n in enumerate(FLYING_SEQUENCE)}
    shift = -NUM_TO_IDX[global_ki]
    new_idx = (NUM_TO_IDX[natal_ki] + shift) % 9
    return FLYING_SEQUENCE[new_idx]


def get_convergence_ki(target_date: str = None, lat: float = 28.5383,
                        lon: float = -81.3792,
                        birth_date: str = None) -> dict:
    """Calculate full convergence Ki state for a given date and location.

    **EXPERIMENTAL ASTRONOMICAL MODEL** — This day Ki calculation uses Moon
    socket crossings (every ~9 days) instead of the traditional daily cascade.
    The convergence socket theory is a modern astronomical interpretation,
    not classical 9 Star Ki practice.

    For traditional personal daily Ki, use `get_daily_ki` instead.

    Returns year, month, day, and hour Ki with astronomical positions,
    socket crossings, gate triads, and timing. If birth_date is provided,
    also returns personal Ki (year/day/hour offset by natal year Ki).

    Args:
        target_date: ISO date string YYYY-MM-DD (default: today)
        lat: Latitude for hour Ki / ascendant (default: Orlando)
        lon: Longitude for hour Ki / ascendant (default: Orlando)
        birth_date: Birth date YYYY-MM-DD for personal Ki calculation
    """
    if target_date:
        td = datetime.fromisoformat(target_date)
        if td.tzinfo is None:
            td = td.replace(tzinfo=TZ)
    else:
        td = datetime.now(TZ)

    now_jd = _dt_to_jd(td)

    # ── Year Ki ──
    yki = _year_ki(td.year, td.month, td.day)
    lichun_year = td.year if (td.month > 2 or (td.month == 2 and td.day >= 4)) else td.year - 1

    # ── Month Ki ──
    # Sun position determines month
    sun = swe.calc_ut(now_jd, swe.SUN)[0]
    sun_lon = sun[0]
    sun_sign = SIGN_NAMES[int(sun_lon / 30)]
    sun_deg = sun_lon % 30

    # Month Ki: determined by year Ki group and which 15° segment Sun is in
    # The month Ki counts down from a starting value based on year Ki
    # Year Ki 1/4/7 start month at 5; 2/5/8 start at 8; 3/6/9 start at 2
    month_starts = {1: 8, 4: 8, 7: 8, 2: 5, 5: 5, 8: 5, 3: 2, 6: 2, 9: 2}
    month_start_ki = month_starts[yki]

    # Which month are we in? Count 15° segments from Lichun (315° = 15° Aquarius)
    # Month 1 starts when Sun crosses 315° (15° Aquarius)
    months_from_lichun = int(((sun_lon - 315) % 360) / 30)
    mki = (month_start_ki - months_from_lichun) % 9
    if mki <= 0:
        mki += 9

    # ── Day Ki ──
    # Day Ki uses the -3 cascade: day_start = month_start - 3 (mod 9).
    # Counts down by 1 per solar day from Lichun.
    # 365 mod 9 = 5 → all 9 starting values appear over 9 years.
    # Month always starts Earth (8, 5, 2). Day start values over 9 years:
    # 5, 9, 4, 8, 3, 7, 2, 6, 1 (for global years 1, 9, 8, 7, 6, 5, 4, 3, 2).
    # Moon is NOT structural for day Ki — kept as parallel observation layer only.
    lichun_jd = _find_lichun(lichun_year)

    # Day start from -3 cascade: month_start - 3
    day_starts = {1: 5, 9: 9, 8: 4, 7: 8, 6: 3, 5: 7, 4: 2, 3: 6, 2: 1}
    day_start_ki = day_starts[yki]

    # Count solar days since Lichun using calendar dates (not JD fractional math).
    # Lichun day itself = offset 0 = day_start_ki, regardless of what time Lichun falls.
    # JD subtraction gives wrong results when Lichun is mid-afternoon.
    lichun_dt = _jd_to_dt(lichun_jd)
    lichun_date = lichun_dt.date()
    today_date = td.date()
    days_since_lichun = (today_date - lichun_date).days

    # Day Ki counts down by 1 per day
    dki = (day_start_ki - (days_since_lichun % 9)) % 9
    if dki <= 0:
        dki += 9
    day_triad = TRIAD_OF[dki]

    # ── Hour Ki ──
    # Hour Ki uses the -3 cascade: hour_start = day_ki - 3 (mod 9).
    # 12 double-hours per day (Chinese shíchén), descending by 1 each.
    # Rat hour (23:00-01:00) = hour 1, Ox (01-03) = 2, ... Pig (21-23) = 12.
    # Hour shifts by 3 per day (12 mod 9 = 3).
    # Hour always starts Earth at Lichun (2, 5, 8).
    hour_start_ki = (dki - 3) % 9
    if hour_start_ki <= 0:
        hour_start_ki += 9

    # Determine current double-hour (1-12, starting at 23:00)
    local_hour = td.hour
    if local_hour >= 23:
        double_hour = 1
    elif local_hour < 1:
        double_hour = 1
    else:
        double_hour = (local_hour + 1) // 2 + 1

    hki = (hour_start_ki - (double_hour - 1)) % 9
    if hki <= 0:
        hki += 9
    hour_triad = TRIAD_OF[hki]

    DOUBLE_HOUR_NAMES = ['Rat','Ox','Tiger','Rabbit','Dragon','Snake',
                         'Horse','Goat','Monkey','Rooster','Dog','Pig']
    current_dh_name = DOUBLE_HOUR_NAMES[double_hour - 1]
    # Double hour number (1-12) is the primary identifier; animal names kept as reference only

    # ── Minute Ki ──
    # 5th level: minute_start = hour_ki - 3 (mod 9).
    # 9 segments per double-hour (~13.3 min each), descending by 1.
    # 9/9 = remainder 0 → all 9 numbers appear once per double-hour.
    minute_start_ki = (hki - 3) % 9
    if minute_start_ki <= 0:
        minute_start_ki += 9

    # Which minute segment are we in? (1-9)
    # Each double-hour = 120 minutes, each segment = 120/9 = 13.333 min
    dh_start_hour = (23 + (double_hour - 1) * 2) % 24
    minutes_into_dh = ((local_hour - dh_start_hour) % 24) * 60 + td.minute
    minute_segment = min(int(minutes_into_dh / (120 / 9)) + 1, 9)

    min_ki = (minute_start_ki - (minute_segment - 1)) % 9
    if min_ki <= 0:
        min_ki += 9
    minute_triad = TRIAD_OF[min_ki]

    # Also compute ascendant for observation (parallel layer, not structural)
    houses = swe.houses(now_jd, lat, lon, b'P')
    asc = houses[1][0]
    asc_sign = SIGN_NAMES[int(asc / 30)]
    asc_deg = asc % 30
    current_gate = int(asc / 15) * 15

    # ── Moon position ──
    moon = swe.calc_ut(now_jd, swe.MOON)[0]
    moon_lon = moon[0]
    moon_sign = SIGN_NAMES[int(moon_lon / 30)]
    moon_deg = moon_lon % 30

    # ── Lunar Gate Ki (Moon crossing 12 mid-sign gates per sidereal month) ──
    # Find start of current sidereal month (last S1 crossing)
    sid_month_start_jd = _find_moon_sidereal_month_start(now_jd)
    # Find all mid-sign crossings since sidereal month start
    lunar_gate_crossings = _find_moon_midsign_crossings(sid_month_start_jd, now_jd + 5)
    lunar_gates_passed = [c for c in lunar_gate_crossings if c["jd"] <= now_jd]
    lunar_gate_count = len(lunar_gates_passed)

    # Lunar gate Ki: count down from the day Ki at the sidereal month start.
    # Use the solar day cascade to find what day Ki was at the S1 crossing.
    days_to_s1 = int(sid_month_start_jd - lichun_jd)
    sid_month_start_ki = (day_start_ki - (days_to_s1 % 9)) % 9
    if sid_month_start_ki <= 0:
        sid_month_start_ki += 9

    # The S1 crossing IS the first lunar gate (15° Aquarius is a mid-sign gate)
    # So lunar_gate_count includes the S1 itself as gate #1
    # Subsequent gates count down from there
    lunar_gate_ki = (sid_month_start_ki - (lunar_gate_count - 1)) % 9
    if lunar_gate_ki <= 0:
        lunar_gate_ki += 9
    lunar_gate_triad = TRIAD_OF[lunar_gate_ki]

    # Current and next lunar gate
    last_lunar_gate = lunar_gates_passed[-1] if lunar_gates_passed else None
    future_lunar_gates = [c for c in lunar_gate_crossings if c["jd"] > now_jd]
    next_lunar_gate = future_lunar_gates[0] if future_lunar_gates else None

    # ── Apsidal info ──
    apogee = swe.calc_ut(now_jd, swe.MEAN_APOG)[0]
    apogee_lon = apogee[0]
    apogee_sign = SIGN_NAMES[int(apogee_lon / 30)]
    apogee_deg = apogee_lon % 30

    # Which arc has the long leg?
    if apogee_lon >= 315 or apogee_lon < 75:
        long_leg = "S1→S2 (Aquarius→Gemini)"
    elif 75 <= apogee_lon < 195:
        long_leg = "S2→S3 (Gemini→Libra)"
    else:
        long_leg = "S3→S1 (Libra→Aquarius)"

    # ── Synodic Ki (Great Year / Jupiter orbit) ──
    synodic_data = get_synodic_gate(
        target_date=td.strftime("%Y-%m-%d") if target_date else None,
        birth_date=birth_date,
    )
    synodic_ki = synodic_data.get("synodic_gate", {}).get("ki", None)
    synodic_triad = TRIAD_OF[synodic_ki] if synodic_ki else None

    # ── Build result ──
    result = {
        "timestamp": td.isoformat(),
        "location": {"lat": lat, "lon": lon},

        "synodic": {
            "ki": synodic_ki,
            "triad": synodic_triad,
            "gate": synodic_data.get("current_gate", {}),
            "anchor": "Jupiter perihelion cycle (~11.86 yr). 9 gates = ~108 years.",
        },

        "year": {
            "ki": yki,
            "triad": TRIAD_OF[yki],
            "period": f"Feb 4, {lichun_year} → Feb 3, {lichun_year + 1}",
            "anchor": "Sun at Lichun (15° Aquarius). Apsidal precession (~8.85yr) drives socket asymmetry.",
        },

        "month": {
            "ki": mki,
            "triad": TRIAD_OF[mki],
            "sun": f"{sun_deg:.1f}° {sun_sign}",
            "sun_ecliptic": round(sun_lon, 2),
            "anchor": "Sun crossing 15° of each sign",
        },

        "lunar_gate": {
            "ki": lunar_gate_ki,
            "triad": lunar_gate_triad,
            "gates_since_sid_month": lunar_gate_count,
            "sid_month_start": _jd_to_dt(sid_month_start_jd).strftime("%Y-%m-%d %I:%M %p"),
            "last_gate": {
                "sign": last_lunar_gate["sign"] if last_lunar_gate else None,
                "date": _jd_to_dt(last_lunar_gate["jd"]).strftime("%Y-%m-%d %I:%M %p") if last_lunar_gate else None,
                "is_socket": last_lunar_gate["is_socket"] if last_lunar_gate else None,
            },
            "next_gate": {
                "sign": next_lunar_gate["sign"] if next_lunar_gate else None,
                "date": _jd_to_dt(next_lunar_gate["jd"]).strftime("%Y-%m-%d %I:%M %p") if next_lunar_gate else None,
                "is_socket": next_lunar_gate["is_socket"] if next_lunar_gate else None,
            },
            "math": "12 gates per sidereal month, 12/9 = remainder 3, triad-locked",
            "anchor": "Moon crossing 15° of each sign (~2.3 days per gate)",
        },

        "day": {
            "ki": dki,
            "triad": day_triad,
            "day_start_ki": day_start_ki,
            "days_since_lichun": days_since_lichun,
            "lichun": _jd_to_dt(lichun_jd).strftime("%Y-%m-%d %I:%M %p"),
            "anchor": "Solar day cascade: day_start = month_start - 3. Counts down 1/day from Lichun. 365 mod 9 = 5 ensures full 9-year continuity.",
        },

        "hour": {
            "ki": hki,
            "triad": hour_triad,
            "double_hour": double_hour,
            "double_hour_name": current_dh_name,
            "hour_start_ki": hour_start_ki,
            "ascendant": f"{asc_deg:.1f}° {asc_sign} (observation layer)",
            "anchor": "Hour cascade: hour_start = day_ki - 3. 12 double-hours/day, descend 1 each. Shift 3/day.",
        },



        "apsidal": {
            "apogee": f"{apogee_deg:.1f}° {apogee_sign}",
            "apogee_ecliptic": round(apogee_lon, 2),
            "long_leg": long_leg,
            "note": "Apogee determines which day Ki leg is longest",
        },

        "socket_triad_lock": {
            "day_level": {"S1": "Man (1,4,7)", "S2": "Heaven (9,6,3)", "S3": "Earth (8,5,2)"},
            "hour_level": "All 24 gates locked: Man→Heaven→Earth cycling every 15°",
        },

        "summary": f"Synodic {synodic_ki}({synodic_triad}) · Year {yki}({TRIAD_OF[yki]}) · Month {mki}({TRIAD_OF[mki]}) · Day {dki}({day_triad}) · Hour {hki}({hour_triad})",

        "framework": {
            "note": "Three bodies, same 12 mid-sign gates, same 15°, same 9 Ki, same remainder 3, same triad lock. One relationship, three octaves.",
            "solar":      {"body": "Sun",       "cycle": "Tropical year",    "gates_per_cycle": 12, "gate_duration": "~30 days",  "repeats_after": "9 years"},
            "lunar":      {"body": "Moon",      "cycle": "Sidereal month",   "gates_per_cycle": 12, "gate_duration": "~2.3 days", "repeats_after": "9 sidereal months"},
            "terrestrial":{"body": "Ascendant", "cycle": "Sidereal day",     "gates_per_cycle": 12, "gate_duration": "~2 hours",  "repeats_after": "9 sidereal days"},
        },
    }

    # ── Personal Ki (if birth_date provided) ──
    if birth_date:
        from ki import calculate_ki, get_full_profile
        from datetime import date as date_type

        bd = date_type.fromisoformat(birth_date)
        natal_yki = _year_ki(bd.year, bd.month, bd.day)

        # Personal Ki = Flying Star applied independently to each global level.
        # The natal year Ki transforms every level the same way.
        # Global 1 with natal 5 → personal 9 at ALL levels where global=1.
        profile = get_full_profile(bd, td.date() if hasattr(td, 'date') else td)
        personal_synodic = _flying_star(natal_yki, synodic_ki) if synodic_ki else None
        personal_year = _flying_star(natal_yki, yki)
        personal_month = _flying_star(natal_yki, mki)
        personal_dki = _flying_star(natal_yki, dki)
        personal_hki = _flying_star(natal_yki, hki)
        personal_day_triad = TRIAD_OF[personal_dki]
        personal_hour_triad = TRIAD_OF[personal_hki]

        result["personal"] = {
            "natal_ki": profile['natal']['sequence'],
            "natal_year_ki": natal_yki,
            "synodic": {"ki": personal_synodic, "triad": TRIAD_OF[personal_synodic]} if personal_synodic else None,
            "year": {"ki": personal_year, "triad": TRIAD_OF[personal_year]},
            "month": {"ki": personal_month, "triad": TRIAD_OF[personal_month]},
            "day": {"ki": personal_dki, "triad": personal_day_triad},
            "hour": {"ki": personal_hki, "triad": personal_hour_triad},
            "summary": f"Personal: Synodic {personal_synodic}({TRIAD_OF[personal_synodic] if personal_synodic else '?'}) · Year {personal_year}({TRIAD_OF[personal_year]}) · Month {personal_month}({TRIAD_OF[personal_month]}) · Day {personal_dki}({personal_day_triad}) · Hour {personal_hki}({personal_hour_triad})",
        }

    return result


def get_natal_gates(name: str) -> dict:
    """Map a natal chart's planets to their 15° gates and permanent triads.

    Shows which gate each planet falls in, its locked triad, possible Ki numbers,
    and whether it sits on a convergence socket.

    Args:
        name: Chart name (e.g., 'chris', 'lisa')
    """
    import json

    charts_dir = Path(__file__).parent / "charts"
    chart_path = charts_dir / f"{name}.json"
    if not chart_path.exists():
        return {"error": f"Chart '{name}' not found. Available: {[f.stem for f in charts_dir.glob('*.json')]}"}

    chart = json.loads(chart_path.read_text())
    planets_raw = chart.get("planets", [])
    angles_raw = chart.get("angles", {})

    results = []
    triad_counts = {"Man": 0, "Earth": 0, "Heaven": 0}

    # Helper to process a single body
    def _process_body(body_name, lon):
        lon = float(lon)
        gate = int(lon / 15) * 15
        triad = gate_triad(lon)
        is_socket = gate in [315, 75, 195]
        socket_name = CONVERGENCE_SOCKETS[float(gate)]["name"] if is_socket else None
        sign_idx = int(lon / 30)
        deg = lon % 30
        results.append({
            "planet": body_name,
            "position": f"{deg:.1f}° {SIGN_NAMES[sign_idx]}",
            "ecliptic": round(lon, 2),
            "gate": gate_label(gate),
            "triad": triad,
            "ki_numbers": TRIAD_NUMBERS[triad],
            "convergence_socket": socket_name,
        })
        triad_counts[triad] += 1

    # Process planets (list of dicts with 'name' and 'longitude')
    if isinstance(planets_raw, list):
        for p in planets_raw:
            if isinstance(p, dict) and "longitude" in p:
                _process_body(p.get("name", "?"), p["longitude"])
    elif isinstance(planets_raw, dict):
        for body_name, data in planets_raw.items():
            if isinstance(data, dict) and "longitude" in data:
                _process_body(body_name, data["longitude"])
            elif isinstance(data, (int, float)):
                _process_body(body_name, data)

    # Process angles (dict with 'ASC', 'MC', etc. or list)
    if isinstance(angles_raw, dict):
        for angle_name, data in angles_raw.items():
            if isinstance(data, dict) and "longitude" in data:
                _process_body(angle_name, data["longitude"])
            elif isinstance(data, (int, float)):
                _process_body(angle_name, data)
    elif isinstance(angles_raw, list):
        for a in angles_raw:
            if isinstance(a, dict) and "longitude" in a:
                _process_body(a.get("name", "?"), a["longitude"])

    return {
        "chart": name,
        "planets": results,
        "triad_balance": triad_counts,
        "socket_planets": [p for p in results if p["convergence_socket"]],
    }
