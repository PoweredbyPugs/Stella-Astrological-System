"""Void of Course Moon calculation using pyswisseph.

Pure ephemeris computation — no Helios dependency.

Traditional definition: The Moon is Void of Course when it has separated
from its last PERFECTED Ptolemaic aspect to a traditional visible planet
(Sun through Saturn) and will NOT perfect any other Ptolemaic aspect
before leaving its current sign.

"Perfect" = the aspect goes exact (orb reaches minimum and begins growing).

Algorithm:
1. Find each Moon ingress (sign change)
2. Scan forward through the sign, tracking orb minima for each aspect
3. Record the moment each aspect's orb hits its minimum (= perfection)
4. The last such perfection before ingress = VOC start
5. VOC end = ingress time
"""

import swisseph as swe
from datetime import datetime, timedelta, timezone
from typing import Optional

# Ephemeris path — shared with Helios via NAS mount
EPHE_PATH = "/mnt/baratie/baratie/sweph-service/ephemeris"
swe.set_ephe_path(EPHE_PATH)

# All major planets (modern VOC technique)
PLANETS = [
    (swe.SUN, "Sun"),
    (swe.MERCURY, "Mercury"),
    (swe.VENUS, "Venus"),
    (swe.MARS, "Mars"),
    (swe.JUPITER, "Jupiter"),
    (swe.SATURN, "Saturn"),
    (swe.URANUS, "Uranus"),
    (swe.NEPTUNE, "Neptune"),
    (swe.PLUTO, "Pluto"),
]

# Ptolemaic aspects
ASPECTS = [
    ("Conjunction", 0),
    ("Sextile", 60),
    ("Square", 90),
    ("Trine", 120),
    ("Opposition", 180),
]

SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED


def _dt_to_jd(dt: datetime) -> float:
    """Convert datetime to Julian Day (UTC)."""
    utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt
    hour_frac = utc.hour + utc.minute / 60.0 + utc.second / 3600.0
    return swe.julday(utc.year, utc.month, utc.day, hour_frac)


def _jd_to_dt(jd: float) -> datetime:
    """Convert Julian Day to UTC datetime."""
    y, m, d, h = swe.revjul(jd)
    hours = int(h)
    minutes = int((h - hours) * 60)
    seconds = int(((h - hours) * 60 - minutes) * 60)
    return datetime(y, m, d, hours, minutes, seconds, tzinfo=timezone.utc)


def _get_body(jd: float, body_id: int) -> tuple:
    """Return (longitude, speed_deg_per_day) for a body at JD."""
    result = swe.calc_ut(jd, body_id, FLAGS)
    return result[0][0], result[0][3]


def _sign_of(lon: float) -> int:
    """Return sign index (0-11) for an ecliptic longitude."""
    return int((lon % 360) // 30)


def _angular_separation(lon1: float, lon2: float) -> float:
    """Shortest angular distance between two longitudes (0-180)."""
    diff = abs(lon1 - lon2) % 360
    return diff if diff <= 180 else 360 - diff


def _aspect_orb(moon_lon: float, planet_lon: float) -> list:
    """Return all Ptolemaic aspects within 10° for this Moon-planet pair.
    
    Returns list of (aspect_name, aspect_angle, orb).
    """
    sep = _angular_separation(moon_lon, planet_lon)
    results = []
    for name, angle in ASPECTS:
        orb = abs(sep - angle)
        if orb <= 10.0:  # generous detection window
            results.append((name, angle, orb))
    return results


def _find_moon_ingress(jd_start: float) -> tuple:
    """Find the next moment when Moon changes sign after jd_start.
    
    Returns (jd_ingress, from_sign, to_sign) or (None, sign, None).
    """
    moon_lon, _ = _get_body(jd_start, swe.MOON)
    current_sign = _sign_of(moon_lon)

    step = 2.0 / 24.0  # 2-hour coarse scan
    jd = jd_start

    while jd < jd_start + 3.5:
        jd += step
        moon_lon, _ = _get_body(jd, swe.MOON)
        new_sign = _sign_of(moon_lon)
        if new_sign != current_sign:
            # Binary search refinement (~1 second precision)
            lo, hi = jd - step, jd
            for _ in range(30):
                mid = (lo + hi) / 2.0
                mid_lon, _ = _get_body(mid, swe.MOON)
                if _sign_of(mid_lon) == current_sign:
                    lo = mid
                else:
                    hi = mid
            return hi, current_sign, _sign_of(_get_body(hi, swe.MOON)[0])

    return None, current_sign, None


def _find_sign_entry(jd_ingress: float, from_sign: int) -> float:
    """Find when the Moon entered `from_sign` (scanning backward from ingress)."""
    step = 2.0 / 24.0
    jd = jd_ingress - step

    while jd > jd_ingress - 3.5:
        moon_lon, _ = _get_body(jd, swe.MOON)
        if _sign_of(moon_lon) != from_sign:
            lo, hi = jd, jd + step
            for _ in range(30):
                mid = (lo + hi) / 2.0
                mid_lon, _ = _get_body(mid, swe.MOON)
                if _sign_of(mid_lon) != from_sign:
                    lo = mid
                else:
                    hi = mid
            return hi
        jd -= step

    return jd_ingress - 3.0


def _refine_perfection(jd_before: float, jd_after: float,
                        planet_id: int, aspect_angle: float) -> tuple:
    """Find the exact moment an aspect orb reaches its minimum (perfection).
    
    Uses ternary search to find the minimum orb between jd_before and jd_after.
    Returns (jd_exact, min_orb).
    """
    lo, hi = jd_before, jd_after

    for _ in range(40):  # converges to ~1 second
        if hi - lo < 0.5 / 86400.0:  # less than 0.5 seconds
            break
        m1 = lo + (hi - lo) / 3
        m2 = lo + 2 * (hi - lo) / 3

        moon1, _ = _get_body(m1, swe.MOON)
        planet1, _ = _get_body(m1, planet_id)
        orb1 = abs(_angular_separation(moon1, planet1) - aspect_angle)

        moon2, _ = _get_body(m2, swe.MOON)
        planet2, _ = _get_body(m2, planet_id)
        orb2 = abs(_angular_separation(moon2, planet2) - aspect_angle)

        if orb1 < orb2:
            hi = m2
        else:
            lo = m1

    jd_mid = (lo + hi) / 2
    moon_mid, _ = _get_body(jd_mid, swe.MOON)
    planet_mid, _ = _get_body(jd_mid, planet_id)
    min_orb = abs(_angular_separation(moon_mid, planet_mid) - aspect_angle)

    return jd_mid, min_orb


def _collect_perfections(jd_entry: float, jd_ingress: float,
                          from_sign: int) -> list:
    """Scan through Moon's time in a sign and find every aspect perfection.
    
    A perfection = an orb minimum (was shrinking, then starts growing).
    Only counts if the minimum orb is < 1.0° (aspect actually perfected).
    
    Returns list of dicts sorted by time:
        [{jd, planet, aspect, min_orb}, ...]
    """
    step = 2.0 / 1440.0  # 2-minute steps for better precision
    jd = jd_entry
    perfections = []

    # Track: for each (planet, aspect), store (prev_orb, was_shrinking)
    tracking = {}  # key: (planet_name, aspect_name, planet_id) -> (prev_orb, was_shrinking)

    while jd <= jd_ingress:
        moon_lon, _ = _get_body(jd, swe.MOON)

        if _sign_of(moon_lon) != from_sign:
            break

        for planet_id, planet_name in PLANETS:
            planet_lon, _ = _get_body(jd, planet_id)
            aspects = _aspect_orb(moon_lon, planet_lon)

            for aspect_name, aspect_angle, orb in aspects:
                key = (planet_name, aspect_name, planet_id)

                if key in tracking:
                    prev_orb, was_shrinking = tracking[key]

                    now_shrinking = orb < prev_orb

                    if was_shrinking and not now_shrinking:
                        # Orb was decreasing, now increasing → just passed minimum
                        # Refine the exact perfection time
                        jd_exact, min_orb = _refine_perfection(
                            jd - 2 * step, jd, planet_id, aspect_angle
                        )
                        # Only count if aspect actually got close to exact
                        if min_orb < 1.0:
                            perfections.append({
                                "jd": jd_exact,
                                "planet": planet_name,
                                "aspect": aspect_name,
                                "min_orb": min_orb,
                            })

                    tracking[key] = (orb, now_shrinking)
                else:
                    # First sighting — can't determine direction yet
                    tracking[key] = (orb, False)

        jd += step

    perfections.sort(key=lambda p: p["jd"])
    return perfections


def _format_duration(total_minutes: int) -> str:
    """Format minutes into human-readable duration."""
    if total_minutes < 60:
        return f"{total_minutes} minutes"
    hours = total_minutes // 60
    mins = total_minutes % 60
    return f"{hours}h {mins}m" if mins else f"{hours}h"


def calculate_voc(start_date: str, end_date: str,
                  tz_name: str = "America/New_York") -> list:
    """Calculate Void of Course Moon periods for a date range.
    
    Args:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        tz_name: Timezone for display (default: America/New_York)
    
    Returns:
        List of VOC period dicts with start, end, duration, lastAspect, signs.
    """
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    tz = ZoneInfo(tz_name)

    dt_start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=tz)
    dt_end = datetime.strptime(end_date, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=tz
    )

    # Look back 3 days to catch VOCs starting before the window
    scan_start = dt_start - timedelta(days=3)
    jd_scan = _dt_to_jd(scan_start)
    jd_window_start = _dt_to_jd(dt_start)
    jd_window_end = _dt_to_jd(dt_end)

    voc_periods = []

    for _ in range(60):  # safety limit
        jd_ingress, from_sign, to_sign = _find_moon_ingress(jd_scan)
        if jd_ingress is None or jd_ingress > jd_window_end + 1.0:
            break

        jd_entry = _find_sign_entry(jd_ingress, from_sign)
        perfections = _collect_perfections(jd_entry, jd_ingress, from_sign)

        if perfections:
            last = perfections[-1]
            jd_voc_start = last["jd"]
            last_aspect_str = f"Moon {last['aspect']} {last['planet']}"
        else:
            jd_voc_start = jd_entry
            last_aspect_str = "None (entire sign VOC)"

        # Only include if period overlaps display window
        if jd_ingress >= jd_window_start and jd_voc_start <= jd_window_end:
            voc_start_dt = _jd_to_dt(jd_voc_start).astimezone(tz)
            voc_end_dt = _jd_to_dt(jd_ingress).astimezone(tz)

            duration = voc_end_dt - voc_start_dt
            total_minutes = max(0, int(duration.total_seconds() / 60))

            voc_periods.append({
                "start": voc_start_dt.strftime("%Y-%m-%d %H:%M"),
                "end": voc_end_dt.strftime("%Y-%m-%d %H:%M"),
                "previousSign": SIGN_NAMES[from_sign],
                "newSign": SIGN_NAMES[to_sign],
                "duration": _format_duration(total_minutes),
                "lastAspect": last_aspect_str,
            })

        jd_scan = jd_ingress + 0.01

    return voc_periods


if __name__ == "__main__":
    print("=== Feb 23 – Mar 7 ===")
    results = calculate_voc("2026-02-23", "2026-03-07")
    for v in results:
        print(f"  {v['previousSign']:>11}→{v['newSign']:<11} {v['start']} → {v['end']}  {v['duration']:>10}  {v['lastAspect']}")

    # Cross-reference with MoonTracks (UTC times):
    # Feb 23 22:28 VoC Taurus  → Feb 24 02:28 → Gemini
    # Feb 25 23:00 VoC Gemini  → Feb 26 05:11 → Cancer
    # Feb 28 04:21 VoC Cancer  → Feb 28 08:16 → Leo
    # Mar 2  12:27 VoC Leo     → Mar 2  12:33 → Virgo
    # Mar 4  14:53 VoC Virgo   → Mar 4  18:55 → Libra
    # Mar 5  23:22 VoC Libra   → Mar 7  04:01 → Scorpio
