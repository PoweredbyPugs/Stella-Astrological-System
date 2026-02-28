"""Ephemeris tools using pyswisseph — native calculations for Stella.

Tools: transit_timing, search_next_transit, lunar_return, solar_return,
       progressions, elections, eclipses, exact_ingresses, planetary_hours
"""

import json
import swisseph as swe
from datetime import datetime, timedelta, timezone, date
from typing import Optional
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Config ──
EPHE_PATH = "/mnt/baratie/baratie/sweph-service/ephemeris"
swe.set_ephe_path(EPHE_PATH)
CHARTS_DIR = Path(__file__).parent / "charts"
TZ = ZoneInfo("America/New_York")
FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED

SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
SIGN_OFFSETS = {name: i * 30 for i, name in enumerate(SIGN_NAMES)}

PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
    "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
}
PLANET_NAMES = {v: k for k, v in PLANET_IDS.items()}

ASPECTS = {
    "Conjunction": 0, "Sextile": 60, "Square": 90,
    "Trine": 120, "Opposition": 180,
}

# Chaldean order for planetary hours
CHALDEAN_ORDER = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
# Day rulers: Monday=Moon, Tuesday=Mars, etc.
DAY_RULERS = {0: "Moon", 1: "Mars", 2: "Mercury", 3: "Jupiter",
              4: "Venus", 5: "Saturn", 6: "Sun"}  # 0=Monday


# ── Core helpers ──

def _dt_to_jd(dt: datetime) -> float:
    utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt
    h = utc.hour + utc.minute / 60.0 + utc.second / 3600.0
    return swe.julday(utc.year, utc.month, utc.day, h)


def _jd_to_dt(jd: float) -> datetime:
    y, m, d, h = swe.revjul(jd)
    hrs = int(h)
    mins = int((h - hrs) * 60)
    secs = int(((h - hrs) * 60 - mins) * 60)
    return datetime(y, m, d, hrs, mins, secs, tzinfo=timezone.utc)


def _jd_to_local(jd: float) -> str:
    return _jd_to_dt(jd).astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")


def _get_lon(jd: float, body: int) -> float:
    return swe.calc_ut(jd, body, FLAGS)[0][0]


def _get_lon_speed(jd: float, body: int) -> tuple:
    r = swe.calc_ut(jd, body, FLAGS)[0]
    return r[0], r[3]


def _sign_of(lon: float) -> int:
    return int((lon % 360) // 30)


def _sign_name(lon: float) -> str:
    return SIGN_NAMES[_sign_of(lon)]


def _degree_in_sign(lon: float) -> float:
    return lon % 30


def _normalize(angle: float) -> float:
    return angle % 360


def _angular_sep(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d


def _load_chart(name: str) -> dict:
    p = CHARTS_DIR / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(f"Chart '{name}' not found at {p}")
    return json.loads(p.read_text())


def _natal_longitude(chart: dict, planet_name: str) -> float:
    for p in chart["planets"]:
        if p["name"].lower() == planet_name.lower():
            return float(p["longitude"])
    raise ValueError(f"Planet '{planet_name}' not found in chart")


def _all_positions(jd: float) -> list:
    """Get all planet positions at a JD."""
    positions = []
    for name, pid in PLANET_IDS.items():
        lon = _get_lon(jd, pid)
        positions.append({
            "planet": name,
            "longitude": round(lon, 4),
            "sign": _sign_name(lon),
            "degree": round(_degree_in_sign(lon), 2),
        })
    return positions


# ── 1. transit_timing ──

def transit_timing(name: str, transit_planet: str, natal_planet: str,
                   aspect: str, orb: float = 3.0) -> dict:
    """Find when a transit enters orb, perfects, and leaves orb."""
    chart = _load_chart(name)
    natal_lon = _natal_longitude(chart, natal_planet)
    t_id = PLANET_IDS[transit_planet]
    aspect_angle = ASPECTS[aspect]

    now_jd = _dt_to_jd(datetime.now(TZ))
    # Target longitude(s) the transit planet needs to hit
    target1 = _normalize(natal_lon + aspect_angle)
    target2 = _normalize(natal_lon - aspect_angle) if aspect_angle != 0 else None

    # Scan forward — duration depends on planet speed
    max_days = {"Moon": 30, "Sun": 370, "Mercury": 370, "Venus": 370, "Mars": 730,
                "Jupiter": 4400, "Saturn": 10800, "Uranus": 30000, "Neptune": 60000, "Pluto": 90000}
    scan_days = max_days.get(transit_planet, 400)
    step = 1.0  # day
    if transit_planet == "Moon":
        step = 1.0 / 24  # hourly for Moon
    
    # Find next exact aspect via scanning for orb minimum
    best_jd = None
    best_orb = 999.0
    scan_jd = now_jd

    # First, find a window where we're close
    for _ in range(int(scan_days / step)):
        t_lon = _get_lon(scan_jd, t_id)
        sep = _angular_sep(t_lon, natal_lon)
        current_orb = abs(sep - aspect_angle)
        if current_orb < orb + 2:
            # Found a neighborhood, now refine
            # Scan at finer resolution
            fine_start = scan_jd - step * 2
            fine_step = step / 48
            min_orb = 999.0
            min_jd = scan_jd
            for i in range(int(step * 4 / fine_step)):
                fj = fine_start + i * fine_step
                tl = _get_lon(fj, t_id)
                s = _angular_sep(tl, natal_lon)
                o = abs(s - aspect_angle)
                if o < min_orb:
                    min_orb = o
                    min_jd = fj
            # Binary refine
            lo, hi = min_jd - fine_step, min_jd + fine_step
            for _ in range(40):
                m1 = lo + (hi - lo) / 3
                m2 = lo + 2 * (hi - lo) / 3
                o1 = abs(_angular_sep(_get_lon(m1, t_id), natal_lon) - aspect_angle)
                o2 = abs(_angular_sep(_get_lon(m2, t_id), natal_lon) - aspect_angle)
                if o1 < o2:
                    hi = m2
                else:
                    lo = m1
            exact_jd = (lo + hi) / 2
            exact_orb = abs(_angular_sep(_get_lon(exact_jd, t_id), natal_lon) - aspect_angle)
            
            if exact_orb < 0.5 and exact_jd >= now_jd:  # valid perfection
                best_jd = exact_jd
                best_orb = exact_orb
                break
        scan_jd += step

    if best_jd is None:
        return {"error": f"No {transit_planet} {aspect} natal {natal_planet} found within {scan_days} days"}

    # Find enter/leave orb by scanning backward/forward from exact
    search_step = step / 24
    
    # Enter orb (scan backward)
    enter_jd = best_jd
    while True:
        enter_jd -= search_step
        o = abs(_angular_sep(_get_lon(enter_jd, t_id), natal_lon) - aspect_angle)
        if o > orb:
            break
    
    # Leave orb (scan forward)
    leave_jd = best_jd
    while True:
        leave_jd += search_step
        o = abs(_angular_sep(_get_lon(leave_jd, t_id), natal_lon) - aspect_angle)
        if o > orb:
            break

    duration_days = leave_jd - enter_jd
    return {
        "transit": f"{transit_planet} {aspect} natal {natal_planet}",
        "natal_longitude": round(natal_lon, 2),
        "enter_orb": _jd_to_local(enter_jd),
        "exact": _jd_to_local(best_jd),
        "exact_orb": round(best_orb, 4),
        "leave_orb": _jd_to_local(leave_jd),
        "duration_in_orb": f"{duration_days:.1f} days",
    }


# ── 2. search_next_transit ──

def search_next_transit(name: str, transit_planet: str = None,
                        natal_planet: str = None, aspect: str = None,
                        days: int = 90) -> list:
    """Search for upcoming transits to a natal chart."""
    chart = _load_chart(name)
    now_jd = _dt_to_jd(datetime.now(TZ))
    end_jd = now_jd + days

    # Build search space
    t_planets = [transit_planet] if transit_planet else list(PLANET_IDS.keys())
    n_planets = [natal_planet] if natal_planet else [p["name"] for p in chart["planets"]]
    aspects_to_check = {aspect: ASPECTS[aspect]} if aspect else ASPECTS

    # For outer planets use daily step, inner planets use finer
    results = []

    for tp in t_planets:
        t_id = PLANET_IDS.get(tp)
        if t_id is None:
            continue
        step = 0.5 if tp in ("Moon",) else 1.0 if tp in ("Sun", "Mercury", "Venus", "Mars") else 2.0

        for np_name in n_planets:
            try:
                n_lon = _natal_longitude(chart, np_name)
            except ValueError:
                continue
            if tp == np_name:
                continue  # skip self-transits for same planet

            for asp_name, asp_angle in aspects_to_check.items():
                # Scan for orb minima
                prev_orb = None
                was_shrinking = False
                jd = now_jd

                while jd < end_jd:
                    t_lon = _get_lon(jd, t_id)
                    sep = _angular_sep(t_lon, n_lon)
                    orb_val = abs(sep - asp_angle)

                    if prev_orb is not None:
                        now_shrinking = orb_val < prev_orb
                        if was_shrinking and not now_shrinking and prev_orb < 1.5:
                            # Refine with ternary search
                            lo, hi = jd - step, jd
                            for _ in range(35):
                                m1 = lo + (hi - lo) / 3
                                m2 = lo + 2 * (hi - lo) / 3
                                o1 = abs(_angular_sep(_get_lon(m1, t_id), n_lon) - asp_angle)
                                o2 = abs(_angular_sep(_get_lon(m2, t_id), n_lon) - asp_angle)
                                if o1 < o2:
                                    hi = m2
                                else:
                                    lo = m1
                            exact_jd = (lo + hi) / 2
                            exact_orb = abs(_angular_sep(_get_lon(exact_jd, t_id), n_lon) - asp_angle)
                            if exact_orb < 0.5:
                                results.append({
                                    "transit_planet": tp,
                                    "natal_planet": np_name,
                                    "aspect": asp_name,
                                    "exact_date": _jd_to_local(exact_jd),
                                    "orb": round(exact_orb, 4),
                                })
                        was_shrinking = now_shrinking
                    prev_orb = orb_val
                    jd += step

    results.sort(key=lambda r: r["exact_date"])
    return results


# ── 3. lunar_return ──

def lunar_return(name: str, target_date: str = None) -> dict:
    """Calculate lunar return chart."""
    chart = _load_chart(name)
    natal_moon = _natal_longitude(chart, "Moon")

    if target_date:
        start_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=TZ)
    else:
        start_dt = datetime.now(TZ)

    jd = _dt_to_jd(start_dt)

    # Moon completes a cycle in ~27.3 days, scan in 2-hour steps
    step = 2.0 / 24
    prev_diff = None

    for _ in range(500):
        moon_lon = _get_lon(jd, swe.MOON)
        diff = _normalize(moon_lon - natal_moon)
        
        if prev_diff is not None and prev_diff > 350 and diff < 10:
            # Crossed the natal Moon longitude — binary search
            lo, hi = jd - step, jd
            for _ in range(45):
                mid = (lo + hi) / 2
                ml = _get_lon(mid, swe.MOON)
                d = _normalize(ml - natal_moon)
                if d > 180:  # haven't crossed yet
                    lo = mid
                else:
                    hi = mid
            exact_jd = (lo + hi) / 2
            
            return {
                "type": "Lunar Return",
                "name": name,
                "natal_moon": round(natal_moon, 4),
                "exact_time": _jd_to_local(exact_jd),
                "moon_sign": _sign_name(_get_lon(exact_jd, swe.MOON)),
                "moon_degree": round(_degree_in_sign(_get_lon(exact_jd, swe.MOON)), 2),
                "positions": _all_positions(exact_jd),
            }
        prev_diff = diff
        jd += step

    return {"error": "Could not find lunar return within scan range"}


# ── 4. solar_return ──

def solar_return(name: str, year: int = None) -> dict:
    """Calculate solar return chart for a given year."""
    chart = _load_chart(name)
    natal_sun = _natal_longitude(chart, "Sun")

    if year is None:
        year = datetime.now(TZ).year

    # Start scanning from March of that year (Sun is ~0° Aries)
    # More precisely, start ~10 days before the birthday
    birth_month = int(chart["birthData"]["date"].split("-")[1])
    birth_day = int(chart["birthData"]["date"].split("-")[2])
    start = datetime(year, birth_month, birth_day, tzinfo=TZ) - timedelta(days=10)
    jd = _dt_to_jd(start)

    step = 0.5  # half-day steps
    prev_diff = None

    for _ in range(100):
        sun_lon = _get_lon(jd, swe.SUN)
        diff = _normalize(sun_lon - natal_sun)

        if prev_diff is not None and prev_diff > 350 and diff < 10:
            lo, hi = jd - step, jd
            for _ in range(45):
                mid = (lo + hi) / 2
                sl = _get_lon(mid, swe.SUN)
                d = _normalize(sl - natal_sun)
                if d > 180:
                    lo = mid
                else:
                    hi = mid
            exact_jd = (lo + hi) / 2

            return {
                "type": "Solar Return",
                "name": name,
                "year": year,
                "natal_sun": round(natal_sun, 4),
                "exact_time": _jd_to_local(exact_jd),
                "sun_sign": _sign_name(_get_lon(exact_jd, swe.SUN)),
                "sun_degree": round(_degree_in_sign(_get_lon(exact_jd, swe.SUN)), 2),
                "positions": _all_positions(exact_jd),
            }
        prev_diff = diff
        jd += step

    return {"error": f"Could not find solar return for year {year}"}


# ── 5. progressions ──

def progressions(name: str, target_date: str = None) -> dict:
    """Calculate secondary progressed chart."""
    chart = _load_chart(name)
    bd = chart["birthData"]
    birth_dt = datetime.strptime(f"{bd['date']} {bd['time']}", "%Y-%m-%d %H:%M:%S")
    birth_dt = birth_dt.replace(tzinfo=ZoneInfo(bd.get("timezone", "America/New_York")))

    if target_date:
        target_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=TZ)
    else:
        target_dt = datetime.now(TZ)

    # Secondary progressions: 1 day = 1 year
    age_days = (target_dt - birth_dt).total_seconds() / 86400.0
    progressed_dt = birth_dt + timedelta(days=age_days / 365.25)
    prog_jd = _dt_to_jd(progressed_dt)

    positions = _all_positions(prog_jd)

    # Try to calculate progressed Ascendant using ARMC progression
    # (Solar arc: progressed Sun - natal Sun added to natal MC)
    natal_sun = _natal_longitude(chart, "Sun")
    prog_sun = _get_lon(prog_jd, swe.SUN)
    solar_arc = _normalize(prog_sun - natal_sun)

    natal_asc = float(chart["angles"]["ascendant"]["longitude"])
    natal_mc = float(chart["angles"]["midheaven"]["longitude"])

    return {
        "type": "Secondary Progressions",
        "name": name,
        "target_date": target_dt.strftime("%Y-%m-%d"),
        "progressed_date": progressed_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "age_years": round(age_days / 365.25, 2),
        "solar_arc": round(solar_arc, 2),
        "progressed_ascendant": {
            "longitude": round(_normalize(natal_asc + solar_arc), 2),
            "sign": _sign_name(_normalize(natal_asc + solar_arc)),
            "degree": round(_degree_in_sign(_normalize(natal_asc + solar_arc)), 2),
        },
        "progressed_mc": {
            "longitude": round(_normalize(natal_mc + solar_arc), 2),
            "sign": _sign_name(_normalize(natal_mc + solar_arc)),
            "degree": round(_degree_in_sign(_normalize(natal_mc + solar_arc)), 2),
        },
        "positions": positions,
    }


# ── 6. elections ──

def elections(criteria: dict = None, start_date: str = None,
              end_date: str = None, lat: float = 28.5383,
              lon: float = -81.3792) -> list:
    """Scan for favorable electional windows (basic version).
    
    Criteria keys: moon_signs (list), avoid_voc (bool), require_benefic_aspect (bool)
    """
    if criteria is None:
        criteria = {}
    moon_signs = criteria.get("moon_signs", None)  # None = any non-detriment
    avoid_voc = criteria.get("avoid_voc", True)
    require_benefic = criteria.get("require_benefic_aspect", False)

    # Default detriment/fall signs for Moon
    moon_bad_signs = {"Capricorn", "Scorpio"}

    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=TZ)
    else:
        start_dt = datetime.now(TZ)
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, tzinfo=TZ)
    else:
        end_dt = start_dt + timedelta(days=7)

    jd = _dt_to_jd(start_dt)
    jd_end = _dt_to_jd(end_dt)
    step = 1.0 / 24  # hourly

    candidates = []

    while jd < jd_end:
        moon_lon = _get_lon(jd, swe.MOON)
        moon_sign = _sign_name(moon_lon)
        score = 0

        # Moon sign quality
        if moon_signs:
            if moon_sign not in moon_signs:
                jd += step
                continue
            score += 3
        elif moon_sign not in moon_bad_signs:
            score += 1
            if moon_sign in ("Cancer", "Taurus"):  # dignity/exaltation
                score += 2
        else:
            jd += step
            continue

        # Check benefic aspects to Moon
        venus_lon = _get_lon(jd, swe.VENUS)
        jupiter_lon = _get_lon(jd, swe.JUPITER)
        
        for b_lon, b_name in [(venus_lon, "Venus"), (jupiter_lon, "Jupiter")]:
            sep = _angular_sep(moon_lon, b_lon)
            for asp_name, asp_angle in ASPECTS.items():
                if abs(sep - asp_angle) < 3.0:
                    score += 2
                    break

        # Malefic check (Mars/Saturn aspecting Moon = penalty)
        mars_lon = _get_lon(jd, swe.MARS)
        saturn_lon = _get_lon(jd, swe.SATURN)
        for m_lon in [mars_lon, saturn_lon]:
            sep = _angular_sep(moon_lon, m_lon)
            for asp_angle in [0, 90, 180]:
                if abs(sep - asp_angle) < 3.0:
                    score -= 2

        if require_benefic and score < 3:
            jd += step
            continue

        if score > 0:
            candidates.append({
                "datetime": _jd_to_local(jd),
                "moon_sign": moon_sign,
                "moon_degree": round(_degree_in_sign(moon_lon), 1),
                "score": score,
            })

        jd += step

    # Return top 10
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:10]


# ── 7. eclipses ──

def eclipses(start_date: str = None, end_date: str = None,
             name: str = None) -> list:
    """Find upcoming eclipses, optionally checking natal contacts."""
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=TZ)
    else:
        start_dt = datetime.now(TZ)
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=TZ)
    else:
        end_dt = start_dt + timedelta(days=365)

    jd_start = _dt_to_jd(start_dt)
    jd_end = _dt_to_jd(end_dt)

    natal_points = {}
    if name:
        chart = _load_chart(name)
        for p in chart["planets"]:
            natal_points[p["name"]] = float(p["longitude"])
        for angle_name in ["ascendant", "midheaven"]:
            natal_points[angle_name.capitalize()] = float(chart["angles"][angle_name]["longitude"])

    results = []

    # Solar eclipses
    jd = jd_start
    for _ in range(20):
        try:
            res, tret = swe.sol_eclipse_when_glob(jd, FLAGS, 0)
        except Exception:
            break
        ecl_jd = tret[0]
        if ecl_jd > jd_end:
            break

        ecl_type = []
        if res & swe.ECL_TOTAL:
            ecl_type.append("Total")
        if res & swe.ECL_ANNULAR:
            ecl_type.append("Annular")
        if res & swe.ECL_PARTIAL:
            ecl_type.append("Partial")
        if res & swe.ECL_ANNULAR_TOTAL:
            ecl_type.append("Hybrid")

        sun_lon = _get_lon(ecl_jd, swe.SUN)
        
        ecl = {
            "type": "Solar",
            "subtype": " / ".join(ecl_type) if ecl_type else "Unknown",
            "date": _jd_to_local(ecl_jd),
            "longitude": round(sun_lon, 2),
            "sign": _sign_name(sun_lon),
            "degree": round(_degree_in_sign(sun_lon), 2),
        }

        if natal_points:
            contacts = []
            for pname, plon in natal_points.items():
                if _angular_sep(sun_lon, plon) <= 3.0:
                    contacts.append({"point": pname, "orb": round(_angular_sep(sun_lon, plon), 2)})
            ecl["natal_contacts"] = contacts

        results.append(ecl)
        jd = ecl_jd + 1

    # Lunar eclipses
    jd = jd_start
    for _ in range(20):
        try:
            res, tret = swe.lun_eclipse_when(jd, FLAGS, 0)
        except Exception:
            break
        ecl_jd = tret[0]
        if ecl_jd > jd_end:
            break

        ecl_type = []
        if res & swe.ECL_TOTAL:
            ecl_type.append("Total")
        if res & swe.ECL_PARTIAL:
            ecl_type.append("Partial")
        if res & swe.ECL_PENUMBRAL:
            ecl_type.append("Penumbral")

        moon_lon = _get_lon(ecl_jd, swe.MOON)

        ecl = {
            "type": "Lunar",
            "subtype": " / ".join(ecl_type) if ecl_type else "Unknown",
            "date": _jd_to_local(ecl_jd),
            "longitude": round(moon_lon, 2),
            "sign": _sign_name(moon_lon),
            "degree": round(_degree_in_sign(moon_lon), 2),
        }

        if natal_points:
            contacts = []
            for pname, plon in natal_points.items():
                if _angular_sep(moon_lon, plon) <= 3.0:
                    contacts.append({"point": pname, "orb": round(_angular_sep(moon_lon, plon), 2)})
            ecl["natal_contacts"] = contacts

        results.append(ecl)
        jd = ecl_jd + 1

    results.sort(key=lambda e: e["date"])
    return results


# ── 8. exact_ingresses ──

def exact_ingresses(planet: str = None, start_date: str = None,
                    end_date: str = None) -> list:
    """Find exact sign ingress times for a planet."""
    if planet is None:
        planet = "Moon"
    pid = PLANET_IDS[planet]

    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=TZ)
    else:
        start_dt = datetime.now(TZ)
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=TZ)
    else:
        end_dt = start_dt + timedelta(days=30)

    jd = _dt_to_jd(start_dt)
    jd_end = _dt_to_jd(end_dt)

    # Step size depends on planet speed
    if planet == "Moon":
        step = 2.0 / 24  # 2 hours
    elif planet in ("Mercury", "Venus", "Sun", "Mars"):
        step = 1.0  # daily
    else:
        step = 5.0  # 5 days for outer planets

    results = []
    current_sign = _sign_of(_get_lon(jd, pid))

    while jd < jd_end:
        jd += step
        new_sign = _sign_of(_get_lon(jd, pid))
        if new_sign != current_sign:
            # Binary search for exact crossing
            lo, hi = jd - step, jd
            for _ in range(40):
                mid = (lo + hi) / 2
                if _sign_of(_get_lon(mid, pid)) == current_sign:
                    lo = mid
                else:
                    hi = mid
            exact_jd = (lo + hi) / 2

            results.append({
                "planet": planet,
                "from_sign": SIGN_NAMES[current_sign],
                "to_sign": SIGN_NAMES[new_sign],
                "exact_time": _jd_to_local(exact_jd),
            })
            current_sign = new_sign

    return results


# ── 9. planetary_hours ──

def planetary_hours(date_str: str = None, lat: float = 28.5383,
                    lon: float = -81.3792) -> dict:
    """Calculate planetary hours for a date at a location."""
    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=TZ)
    else:
        dt = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)

    jd_noon = _dt_to_jd(dt.replace(hour=12))
    geopos = (lon, lat, 0.0)  # lon, lat, alt

    # Sunrise
    _, tret_rise = swe.rise_trans(jd_noon - 0.5, swe.SUN, swe.CALC_RISE, geopos)
    jd_sunrise = tret_rise[0]

    # Sunset
    _, tret_set = swe.rise_trans(jd_noon, swe.SUN, swe.CALC_SET, geopos)
    jd_sunset = tret_set[0]

    # Next sunrise (for night hours)
    _, tret_rise2 = swe.rise_trans(jd_noon + 0.5, swe.SUN, swe.CALC_RISE, geopos)
    jd_sunrise2 = tret_rise2[0]

    day_length = jd_sunset - jd_sunrise
    night_length = jd_sunrise2 - jd_sunset
    day_hour = day_length / 12
    night_hour = night_length / 12

    # Day ruler from weekday (Monday=0 in Python)
    weekday = dt.weekday()
    day_ruler = DAY_RULERS[weekday]
    
    # Find starting index in Chaldean order
    start_idx = CHALDEAN_ORDER.index(day_ruler)

    hours = []
    for i in range(24):
        ruler = CHALDEAN_ORDER[(start_idx + i) % 7]
        if i < 12:
            h_start = jd_sunrise + i * day_hour
            h_end = jd_sunrise + (i + 1) * day_hour
            period = "Day"
        else:
            h_start = jd_sunset + (i - 12) * night_hour
            h_end = jd_sunset + (i - 11) * night_hour
            period = "Night"

        hours.append({
            "hour": i + 1,
            "period": period,
            "ruler": ruler,
            "start": _jd_to_local(h_start),
            "end": _jd_to_local(h_end),
        })

    return {
        "date": dt.strftime("%Y-%m-%d"),
        "location": {"lat": lat, "lon": lon},
        "day_ruler": day_ruler,
        "sunrise": _jd_to_local(jd_sunrise),
        "sunset": _jd_to_local(jd_sunset),
        "hours": hours,
    }


# ── Test ──

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("EPHEMERIS TOOLS TEST — Chart: chris")
    print("=" * 60)

    print("\n--- 1. Transit Timing: Saturn Conjunction natal Sun ---")
    r = transit_timing("chris", "Saturn", "Sun", "Conjunction")
    print(json.dumps(r, indent=2))

    print("\n--- 2. Search Next Transits (Jupiter, 90 days) ---")
    r = search_next_transit("chris", transit_planet="Jupiter", days=90)
    for t in r[:5]:
        print(f"  {t['transit_planet']} {t['aspect']} {t['natal_planet']} — {t['exact_date']} (orb {t['orb']}°)")

    print("\n--- 3. Lunar Return ---")
    r = lunar_return("chris")
    print(f"  Exact: {r.get('exact_time')}")
    print(f"  Moon: {r.get('moon_sign')} {r.get('moon_degree')}°")

    print("\n--- 4. Solar Return 2026 ---")
    r = solar_return("chris", 2026)
    print(f"  Exact: {r.get('exact_time')}")
    print(f"  Sun: {r.get('sun_sign')} {r.get('sun_degree')}°")

    print("\n--- 5. Progressions ---")
    r = progressions("chris")
    print(f"  Age: {r.get('age_years')} years")
    print(f"  Solar arc: {r.get('solar_arc')}°")
    print(f"  Prog ASC: {r['progressed_ascendant']['sign']} {r['progressed_ascendant']['degree']}°")
    for p in r["positions"][:4]:
        print(f"  {p['planet']}: {p['sign']} {p['degree']}°")

    print("\n--- 6. Elections (next 3 days) ---")
    r = elections()
    for e in r[:3]:
        print(f"  {e['datetime']} — Moon in {e['moon_sign']} {e['moon_degree']}° — score {e['score']}")

    print("\n--- 7. Eclipses (next year, natal contacts for chris) ---")
    r = eclipses(name="chris")
    for e in r[:4]:
        contacts = e.get("natal_contacts", [])
        c_str = ", ".join(f"{c['point']} ({c['orb']}°)" for c in contacts) if contacts else "none"
        print(f"  {e['type']} {e['subtype']} — {e['date']} — {e['sign']} {e['degree']}° — contacts: {c_str}")

    print("\n--- 8. Exact Ingresses (Moon, next 7 days) ---")
    r = exact_ingresses("Moon", end_date=(datetime.now(TZ) + timedelta(days=7)).strftime("%Y-%m-%d"))
    for i in r:
        print(f"  {i['planet']}: {i['from_sign']} → {i['to_sign']} at {i['exact_time']}")

    print("\n--- 9. Planetary Hours (today) ---")
    r = planetary_hours()
    print(f"  Day ruler: {r['day_ruler']}")
    print(f"  Sunrise: {r['sunrise']}, Sunset: {r['sunset']}")
    for h in r["hours"][:3]:
        print(f"  Hour {h['hour']}: {h['ruler']} ({h['period']}) {h['start']}–{h['end']}")
    print(f"  ... ({len(r['hours'])} total hours)")
