"""
9 Star Ki Calculator

Calculates the three Ki numbers for any date using lookup tables
derived from the Lo Shu (Magic Square) and Flying Star sequence.

The Lo Shu palace layout (fixed positions):
    ④ | ⑨ | ②
    ---------
    ③ | ⑤ | ⑦
    ---------
    ⑧ | ① | ⑥

Ki Year: Changes on February 4 (Lichun/Spring Begins)
Ki Month + Third: Looked up from table based on year Ki and date range
"""

from datetime import datetime, date
from typing import Tuple, Dict, Optional

# Year Ki lookup - maps Ki number to list of years
# Ki years change on Feb 4, so Jan 1 - Feb 3 belongs to previous year
YEAR_TABLE = {
    1: [1909, 1918, 1927, 1936, 1945, 1954, 1963, 1972, 1981, 1990, 1999, 2008, 2017, 2026, 2035, 2044],
    2: [1908, 1917, 1926, 1935, 1944, 1953, 1962, 1971, 1980, 1989, 1998, 2007, 2016, 2025, 2034, 2043],
    3: [1907, 1916, 1925, 1934, 1943, 1952, 1961, 1970, 1979, 1988, 1997, 2006, 2015, 2024, 2033, 2042],
    4: [1906, 1915, 1924, 1933, 1942, 1951, 1960, 1969, 1978, 1987, 1996, 2005, 2014, 2023, 2032, 2041],
    5: [1905, 1914, 1923, 1932, 1941, 1950, 1959, 1968, 1977, 1986, 1995, 2004, 2013, 2022, 2031, 2040],
    6: [1904, 1913, 1922, 1931, 1940, 1949, 1958, 1967, 1976, 1985, 1994, 2003, 2012, 2021, 2030, 2039],
    7: [1903, 1912, 1921, 1930, 1939, 1948, 1957, 1966, 1975, 1984, 1993, 2002, 2011, 2020, 2029, 2038],
    8: [1902, 1911, 1920, 1929, 1938, 1947, 1956, 1965, 1974, 1983, 1992, 2001, 2010, 2019, 2028, 2037],
    9: [1901, 1910, 1919, 1928, 1937, 1946, 1955, 1964, 1973, 1982, 1991, 2000, 2009, 2018, 2027, 2036],
}

# Build reverse lookup: year -> Ki number
YEAR_TO_KI = {}
for ki, years in YEAR_TABLE.items():
    for y in years:
        YEAR_TO_KI[y] = ki

# Month table: (start_month, start_day, end_month, end_day) -> values for Ki 1-9
# Values are 3-digit numbers encoding Month.X.Third
MONTH_TABLE = [
    # Feb 4 - Mar 5
    ((2, 4), (3, 5), [187, 225, 353, 481, 528, 656, 784, 822, 959]),
    # Mar 6 - Apr 4
    ((3, 6), (4, 4), [178, 216, 344, 472, 519, 647, 775, 813, 941]),
    # Apr 5 - May 4
    ((4, 5), (5, 4), [169, 297, 335, 463, 591, 638, 766, 894, 932]),
    # May 5 - Jun 5
    ((5, 5), (6, 5), [151, 288, 326, 454, 582, 629, 757, 885, 923]),
    # Jun 6 - Jul 6
    ((6, 6), (7, 6), [142, 279, 317, 445, 573, 611, 748, 876, 914]),
    # Jul 7 - Aug 6
    ((7, 7), (8, 6), [133, 261, 398, 436, 564, 692, 739, 867, 995]),
    # Aug 7 - Sep 7
    ((8, 7), (9, 7), [124, 252, 389, 427, 555, 683, 721, 858, 986]),
    # Sep 8 - Oct 7
    ((9, 8), (10, 7), [115, 243, 371, 418, 546, 674, 712, 849, 977]),
    # Oct 8 - Nov 6
    ((10, 8), (11, 6), [196, 234, 362, 499, 537, 665, 793, 831, 968]),
    # Nov 7 - Dec 6
    ((11, 7), (12, 6), [187, 225, 353, 481, 528, 656, 784, 822, 959]),
    # Dec 7 - Jan 4
    ((12, 7), (1, 4), [178, 216, 344, 472, 519, 647, 775, 813, 941]),
    # Jan 5 - Feb 3
    ((1, 5), (2, 3), [169, 297, 335, 463, 591, 638, 766, 894, 932]),
]

# Flying star sequence (for personal year calculation)
FLYING_SEQUENCE = [5, 6, 7, 8, 9, 1, 2, 3, 4]
NUM_TO_IDX = {n: i for i, n in enumerate(FLYING_SEQUENCE)}


def calculate_personal_year(natal_year_ki: int, global_year_ki: int) -> int:
    """
    Calculate personal year Ki based on natal Ki and global year.
    
    Uses Flying Star method: finds which palace/house natal Ki occupies
    when global year Ki is in the center.
    """
    shift = -NUM_TO_IDX[global_year_ki]
    new_idx = (NUM_TO_IDX[natal_year_ki] + shift) % 9
    return FLYING_SEQUENCE[new_idx]


def calculate_personal_month(natal_month_ki: int, global_month_ki: int) -> int:
    """
    Calculate personal month Ki based on natal month Ki and global month.
    """
    shift = -NUM_TO_IDX[global_month_ki]
    new_idx = (NUM_TO_IDX[natal_month_ki] + shift) % 9
    return FLYING_SEQUENCE[new_idx]


# Ki number to trigram mapping
KI_TRIGRAMS = {
    1: {"name": "Water", "trigram": "☵", "chinese": "Kan", "element": "Water"},
    2: {"name": "Earth", "trigram": "☷", "chinese": "Kun", "element": "Earth"},
    3: {"name": "Thunder", "trigram": "☳", "chinese": "Zhen", "element": "Wood"},
    4: {"name": "Wind", "trigram": "☴", "chinese": "Xun", "element": "Wood"},
    5: {"name": "Center", "trigram": "☯", "chinese": "Tai Chi", "element": "Earth"},
    6: {"name": "Heaven", "trigram": "☰", "chinese": "Qian", "element": "Metal"},
    7: {"name": "Lake", "trigram": "☱", "chinese": "Dui", "element": "Metal"},
    8: {"name": "Mountain", "trigram": "☶", "chinese": "Gen", "element": "Earth"},
    9: {"name": "Fire", "trigram": "☲", "chinese": "Li", "element": "Fire"},
}


def _date_in_range(month: int, day: int, start: tuple, end: tuple) -> bool:
    """Check if month/day falls within a range (handles year wraparound)."""
    start_m, start_d = start
    end_m, end_d = end
    
    date_val = month * 100 + day
    start_val = start_m * 100 + start_d
    end_val = end_m * 100 + end_d
    
    if start_val <= end_val:
        # Normal range (e.g., Mar 6 - Apr 4)
        return start_val <= date_val <= end_val
    else:
        # Wraps around year (e.g., Dec 7 - Jan 4)
        return date_val >= start_val or date_val <= end_val


def calculate_ki_year(year: int, month: int, day: int) -> int:
    """
    Calculate the Ki Year number for a given date.
    
    Ki year changes on February 4 (Lichun).
    """
    # Adjust year if before Feb 4 (Ki new year)
    effective_year = year
    if month < 2 or (month == 2 and day < 4):
        effective_year = year - 1
    
    # Look up in table, or calculate for years outside table range
    if effective_year in YEAR_TO_KI:
        return YEAR_TO_KI[effective_year]
    else:
        # Calculate based on 9-year cycle from a known year
        # 2026 = Ki 1, so offset from there
        offset = (effective_year - 2026) % 9
        ki = 1 - offset
        if ki <= 0:
            ki += 9
        return ki


def calculate_ki_all(year: int, month: int, day: int) -> Tuple[int, int, int]:
    """
    Calculate all three Ki numbers for a given date.
    
    Returns (year_ki, month_ki, third_ki).
    """
    year_ki = calculate_ki_year(year, month, day)
    
    # Find the matching month range
    for start, end, values in MONTH_TABLE:
        if _date_in_range(month, day, start, end):
            # Get the 3-digit value for this year Ki
            value = values[year_ki - 1]
            
            # Parse the three digits: Year.Month.Third
            value_str = str(value)
            # First digit = Year Ki (for verification)
            month_ki = int(value_str[1])  # Second digit = Month Ki
            third_ki = int(value_str[2])  # Third digit = Third Ki
            
            return (year_ki, month_ki, third_ki)
    
    # Fallback (shouldn't happen)
    return (year_ki, 0, 0)


def calculate_ki(target_date: date) -> Dict:
    """
    Calculate all three Ki numbers for a given date.
    
    Returns dict with year_ki, month_ki, third_ki and metadata.
    """
    year_ki, month_ki, third_ki = calculate_ki_all(
        target_date.year, target_date.month, target_date.day
    )
    
    return {
        "date": target_date.isoformat(),
        "ki_year": year_ki,
        "ki_month": month_ki,
        "ki_third": third_ki,
        "sequence": f"{year_ki}.{month_ki}.{third_ki}",
        "year_info": KI_TRIGRAMS[year_ki],
        "month_info": KI_TRIGRAMS[month_ki],
        "third_info": KI_TRIGRAMS[third_ki],
    }


def calculate_natal_ki(birth_date: date) -> Dict:
    """
    Calculate natal (birth) Ki profile.
    """
    result = calculate_ki(birth_date)
    result["type"] = "natal"
    result["birth_date"] = birth_date.isoformat()
    return result


def calculate_current_ki(target_date: Optional[date] = None) -> Dict:
    """
    Calculate current/transiting Ki energy for a date.
    
    If no date provided, uses today.
    """
    if target_date is None:
        target_date = date.today()
    
    result = calculate_ki(target_date)
    result["type"] = "transiting"
    return result


def calculate_personal_cycle(natal_year_ki: int, target_date: Optional[date] = None) -> Dict:
    """
    Calculate personal year and month for someone with given natal year Ki.
    
    Personal position = where natal year Ki lands when global Ki is in center.
    """
    if target_date is None:
        target_date = date.today()
    
    # Get global Ki
    global_ki = calculate_ki(target_date)
    global_year = global_ki['ki_year']
    global_month = global_ki['ki_month']
    
    # Personal year: where natal year Ki lands when global year Ki is in center
    shift = -NUM_TO_IDX[global_year]
    personal_year = FLYING_SEQUENCE[(NUM_TO_IDX[natal_year_ki] + shift) % 9]
    
    # Personal month: where natal year Ki lands when global month Ki is in center
    shift = -NUM_TO_IDX[global_month]
    personal_month = FLYING_SEQUENCE[(NUM_TO_IDX[natal_year_ki] + shift) % 9]
    
    return {
        "date": target_date.isoformat(),
        "natal_year_ki": natal_year_ki,
        "global_year": global_year,
        "global_month": global_month,
        "personal_year": personal_year,
        "personal_month": personal_month,
        "personal_year_info": KI_TRIGRAMS[personal_year],
        "personal_month_info": KI_TRIGRAMS[personal_month],
    }


def get_full_profile(birth_date: date, target_date: Optional[date] = None) -> Dict:
    """
    Get complete Ki profile: natal + current personal cycle.
    """
    natal = calculate_natal_ki(birth_date)
    cycle = calculate_personal_cycle(natal['ki_year'], target_date)
    
    return {
        "natal": natal,
        "current_cycle": cycle,
    }


def format_ki_report(ki_data: Dict) -> str:
    """Format Ki data as a readable report."""
    lines = []
    
    ki_type = ki_data.get("type", "")
    if ki_type == "natal":
        lines.append(f"# Natal 9 Star Ki Profile")
        lines.append(f"**Birth Date:** {ki_data['birth_date']}")
    else:
        lines.append(f"# 9 Star Ki for {ki_data['date']}")
    
    lines.append("")
    lines.append(f"**Ki Sequence:** {ki_data['sequence']}")
    lines.append("")
    
    # Year Ki
    yi = ki_data['year_info']
    lines.append(f"**Year Ki: {ki_data['ki_year']} {yi['trigram']} {yi['name']}** ({yi['chinese']})")
    lines.append(f"  Element: {yi['element']}")
    lines.append("")
    
    # Month Ki
    mi = ki_data['month_info']
    lines.append(f"**Month Ki: {ki_data['ki_month']} {mi['trigram']} {mi['name']}** ({mi['chinese']})")
    lines.append(f"  Element: {mi['element']}")
    lines.append("")
    
    # Third Ki
    ti = ki_data['third_info']
    lines.append(f"**Third Ki: {ki_data['ki_third']} {ti['trigram']} {ti['name']}** ({ti['chinese']})")
    lines.append(f"  Element: {ti['element']}")
    
    return "\n".join(lines)


# Quick test
def calculate_daily_ki(birth_date: date, target_date: Optional[date] = None, 
                      lat: float = 28.5383, lon: float = -81.3792) -> Dict:
    """
    Calculate traditional daily Ki cascade: year, month, day, hour Ki with personal offsets.
    
    This implements the traditional -3 descending pattern used in 9 Star Ki:
    - Year Ki: ((2027 - year) % 9) or 9, adjusted for Lichun (Sun at 315°)
    - Month Ki: first_sub(year_ki) start, counts down by Sun's 30° segments from 315°
    - Day Ki: day_starts_by_year lookup table, counts days since Lichun, descends by 1 per day
    - Hour Ki: first_sub(day_ki) start, counts down by 2-hour blocks
    
    Personal Ki at each level uses Flying Star: flying_star(natal_year_ki, global_ki)
    
    Args:
        birth_date: Date of birth for natal year Ki calculation
        target_date: Target date for Ki calculation (default: today)
        lat: Latitude for precise Lichun timing (default: Orlando)
        lon: Longitude for precise Lichun timing (default: Orlando)
        
    Returns:
        Dict with global and personal Ki at all 4 levels (year, month, day, hour)
    """
    import swisseph as swe
    import zoneinfo
    from datetime import timedelta
    
    # Set ephemeris path
    swe.set_ephe_path('/mnt/baratie/baratie/sweph-service/ephemeris')
    
    if target_date is None:
        target_date = date.today()
    
    # Convert to datetime for calculations
    target_dt = datetime.combine(target_date, datetime.min.time())
    target_dt = target_dt.replace(tzinfo=zoneinfo.ZoneInfo("America/New_York"))
    
    # Helper function for -3 descending pattern
    def first_sub(parent):
        return [None, 8, 5, 2, 8, 5, 2, 8, 5, 2][parent]
    
    # Find Lichun (Sun at 315° = 15° Aquarius) for the Ki year
    def find_lichun(start_jd):
        jd = start_jd
        prev_lon = swe.calc_ut(jd, swe.SUN)[0][0]
        while True:
            jd += 0.5
            lon = swe.calc_ut(jd, swe.SUN)[0][0]
            dp = (315.0 - prev_lon) % 360
            dc = (315.0 - lon) % 360
            if dp < 180 and dp > 0 and dc > 180:
                lo, hi = jd - 0.5, jd
                for _ in range(50):
                    mid = (lo + hi) / 2
                    m = swe.calc_ut(mid, swe.SUN)[0][0]
                    d = (315.0 - m) % 360
                    if d < 180: 
                        lo = mid
                    else: 
                        hi = mid
                return (lo + hi) / 2
            prev_lon = lon
    
    # Calculate Julian day for target date
    target_jd = swe.julday(target_dt.year, target_dt.month, target_dt.day, 
                          target_dt.hour + target_dt.minute / 60.0)
    
    # Find Lichun for this Ki year
    lichun_jd = find_lichun(swe.julday(target_dt.year, 1, 1, 0.0))
    if lichun_jd > target_jd:
        lichun_jd = find_lichun(swe.julday(target_dt.year - 1, 1, 1, 0.0))
    
    # Global year Ki: ((2027 - year) % 9) or 9, adjusted for Lichun
    year_ki = ((2027 - target_dt.year) % 9) or 9
    if lichun_jd > target_jd:
        year_ki = ((2027 - (target_dt.year - 1)) % 9) or 9
    
    # Current Sun longitude for month calculation
    sun_lon = swe.calc_ut(target_jd, swe.SUN)[0][0]
    month_idx = int(((sun_lon - 315 + 360) % 360) / 30)
    
    # Month Ki: -3 cascade from year Ki
    month_start = first_sub(year_ki)
    month_ki = ((month_start - month_idx - 1) % 9) + 1
    
    # Day Ki: 365 solar days from Lichun with local midnight boundaries
    local_tz = zoneinfo.ZoneInfo("America/New_York")
    day_starts_by_year = {1: 5, 9: 9, 8: 4, 7: 8, 6: 3, 5: 7, 4: 2, 3: 6, 2: 1}
    day_start_ki = day_starts_by_year.get(year_ki, 5)
    
    # Convert Lichun and target to local time
    lichun_dt = datetime.utcfromtimestamp((lichun_jd - 2440587.5) * 86400).replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
    lichun_local = lichun_dt.astimezone(local_tz)
    target_local = target_dt.astimezone(local_tz)
    
    days_since_lichun = (target_local.date() - lichun_local.date()).days
    day_ki = ((day_start_ki - days_since_lichun - 1) % 9) + 1
    
    # Hour Ki: 12 double-hours per day, -3 cascade from day
    local_hour = target_local.hour + target_local.minute / 60.0
    dh_idx = int(local_hour / 2)  # which 2-hour block (0-11)
    hour_start = first_sub(day_ki)
    hour_ki = ((hour_start - dh_idx - 1) % 9) + 1
    
    # Calculate natal year Ki
    natal_year_ki = calculate_ki_year(birth_date.year, birth_date.month, birth_date.day)
    
    # Personal Ki using Flying Star method at each level
    def flying_star(natal_ki, global_ki):
        shift = -NUM_TO_IDX[global_ki]
        new_idx = (NUM_TO_IDX[natal_ki] + shift) % 9
        return FLYING_SEQUENCE[new_idx]
    
    personal_year_ki = flying_star(natal_year_ki, year_ki)
    personal_month_ki = flying_star(natal_year_ki, month_ki)
    personal_day_ki = flying_star(natal_year_ki, day_ki)
    personal_hour_ki = flying_star(natal_year_ki, hour_ki)
    
    # Build result structure
    result = {
        "target_date": target_date.isoformat(),
        "birth_date": birth_date.isoformat(),
        "natal_year_ki": natal_year_ki,
        "lichun_date": lichun_local.date().isoformat(),
        "days_since_lichun": days_since_lichun,
        "local_time": target_local.strftime("%H:%M"),
        "global": {
            "year": {"ki": year_ki, "info": KI_TRIGRAMS[year_ki]},
            "month": {"ki": month_ki, "info": KI_TRIGRAMS[month_ki]},
            "day": {"ki": day_ki, "info": KI_TRIGRAMS[day_ki]},
            "hour": {"ki": hour_ki, "info": KI_TRIGRAMS[hour_ki]},
        },
        "personal": {
            "year": {"ki": personal_year_ki, "info": KI_TRIGRAMS[personal_year_ki]},
            "month": {"ki": personal_month_ki, "info": KI_TRIGRAMS[personal_month_ki]},
            "day": {"ki": personal_day_ki, "info": KI_TRIGRAMS[personal_day_ki]},
            "hour": {"ki": personal_hour_ki, "info": KI_TRIGRAMS[personal_hour_ki]},
        },
        "sequences": {
            "global": f"{year_ki}.{month_ki}.{day_ki}.{hour_ki}",
            "personal": f"{personal_year_ki}.{personal_month_ki}.{personal_day_ki}.{personal_hour_ki}",
        }
    }
    
    return result


if __name__ == "__main__":
    # Test May 1, 1986 - should be 5.9.1
    print("Testing May 1, 1986 (should be 5.9.1):")
    result = calculate_ki(date(1986, 5, 1))
    print(f"  Result: {result['sequence']}")
    print(f"  {'✓' if result['sequence'] == '5.9.1' else '✗'}")
    print()
    
    # Test today
    today = date.today()
    print(f"Today ({today}):")
    result = calculate_current_ki(today)
    print(f"  Ki: {result['sequence']}")
    print()
    
    # Test a few more known dates
    print("Feb 5, 2026:")
    result = calculate_ki(date(2026, 2, 5))
    print(f"  Ki: {result['sequence']}")
    print()
    
    # Test daily Ki cascade
    print("Testing daily Ki cascade for Buckley (1986-05-01) on 2026-03-22:")
    daily_result = calculate_daily_ki(date(1986, 5, 1), date(2026, 3, 22))
    print(f"  Global: {daily_result['sequences']['global']}")
    print(f"  Personal: {daily_result['sequences']['personal']}")
    print(f"  Personal Day Ki: {daily_result['personal']['day']['ki']} (should be 7)")
    print(f"  Personal Month Ki: {daily_result['personal']['month']['ki']} (should be 3)")
