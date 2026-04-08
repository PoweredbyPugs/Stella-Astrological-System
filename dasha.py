"""Vimshottari Dasha calculation module.

Computes the full dasha stack (5 levels: maha through prana) plus
the transiting Moon's nakshatra/pada as levels 6-7.

Correct Vimshottari lord sequence (nakshatra order):
  Ketu, Venus, Sun, Moon, Mars, Rahu, Jupiter, Saturn, Mercury

Each lord owns 3 nakshatras (every 9th): lord at position i owns
nakshatras i, i+9, i+18 (1-indexed).

Birth nakshatra determines the first maha dasha lord and the
fraction remaining at birth.
"""

from datetime import datetime, timedelta
from typing import Optional
import swisseph as swe

# ── Constants ──

# Correct Vimshottari sequence (nakshatra lordship order)
LORDS = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']
YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]  # Total = 120
TOTAL_YEARS = 120

# Planetary glyphs
GLYPHS = {
    'Ketu': '☋', 'Venus': '♀', 'Sun': '☉', 'Moon': '☽', 'Mars': '♂',
    'Rahu': '☊', 'Jupiter': '♃', 'Saturn': '♄', 'Mercury': '☿',
}

NAKSHATRA_NAMES = [
    'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
    'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
    'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
    'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta',
    'Shatabhisha', 'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati',
]

PADA_AIMS = ['Dharma', 'Artha', 'Kama', 'Moksha']

# Nakshatra span = 360° / 27 = 13°20'
NAK_SPAN = 360.0 / 27  # 13.3333...°
PADA_SPAN = NAK_SPAN / 4  # 3.3333...°

SIGN_NAMES = [
    'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
    'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
]


def _lon_to_nakshatra(lon: float) -> dict:
    """Convert ecliptic longitude to nakshatra, pada, and lord."""
    lon = lon % 360
    nak_idx = int(lon / NAK_SPAN)  # 0-26
    deg_in_nak = lon - nak_idx * NAK_SPAN
    pada = int(deg_in_nak / PADA_SPAN)  # 0-3
    if pada > 3:
        pada = 3  # edge case at exact boundary

    lord_idx = nak_idx % 9  # 0-8
    return {
        'nakshatra_num': nak_idx + 1,
        'nakshatra': NAKSHATRA_NAMES[nak_idx],
        'pada': pada + 1,
        'pada_aim': PADA_AIMS[pada],
        'lord': LORDS[lord_idx],
        'lord_position': lord_idx + 1,
        'lord_years': YEARS[lord_idx],
        'degree_in_nakshatra': round(deg_in_nak, 4),
        'sign': SIGN_NAMES[int(lon / 30)],
        'degree_in_sign': round(lon % 30, 4),
        'longitude': round(lon, 4),
    }


def _birth_dasha_fraction(moon_lon: float) -> tuple:
    """Calculate the fraction of the first maha dasha remaining at birth.

    Returns (lord_index, fraction_remaining) where lord_index is 0-8.
    """
    nak_idx = int(moon_lon / NAK_SPAN)
    deg_in_nak = moon_lon - nak_idx * NAK_SPAN
    fraction_elapsed = deg_in_nak / NAK_SPAN
    fraction_remaining = 1.0 - fraction_elapsed
    lord_idx = nak_idx % 9
    return lord_idx, fraction_remaining


def compute_dasha_stack(
    birth_date: str,
    birth_moon_lon: float,
    target_date: str = None,
    target_time: str = None,
) -> dict:
    """Compute the full 5-level Vimshottari dasha stack.

    Args:
        birth_date: YYYY-MM-DD
        birth_moon_lon: Natal Moon ecliptic longitude in degrees
        target_date: YYYY-MM-DD (default: today)
        target_time: HH:MM:SS (default: current time)

    Returns dict with maha through prana dashas, each with lord, position,
    start/end dates, and period duration.
    """
    bd = datetime.fromisoformat(birth_date)

    if target_date:
        td = datetime.fromisoformat(target_date)
        if target_time:
            h, m, s = (int(x) for x in target_time.split(':'))
            td = td.replace(hour=h, minute=m, second=s)
    else:
        td = datetime.now()

    birth_lord_idx, fraction_remaining = _birth_dasha_fraction(birth_moon_lon)
    birth_nak = _lon_to_nakshatra(birth_moon_lon)

    # Build maha dasha timeline from birth
    maha_periods = []
    start = bd
    for i in range(18):  # Two full cycles to be safe
        idx = (birth_lord_idx + i) % 9
        full_days = YEARS[idx] * 365.25
        if i == 0:
            period_days = full_days * fraction_remaining
        else:
            period_days = full_days
        end = start + timedelta(days=period_days)
        maha_periods.append({
            'lord': LORDS[idx],
            'lord_position': idx + 1,
            'years': YEARS[idx],
            'start': start,
            'end': end,
            'days': period_days,
        })
        start = end
        if start > td + timedelta(days=365 * 50):
            break

    # Find current maha dasha
    maha = None
    for p in maha_periods:
        if p['start'] <= td < p['end']:
            maha = p
            break

    if not maha:
        return {'error': 'Target date outside computed dasha range'}

    # Subdivide: each sub-level divides the parent period proportionally
    # by the same lord sequence, starting from the parent's lord
    def _subdivide(parent_lord_idx, parent_start, parent_days, level_name):
        """Subdivide a dasha period into 9 sub-periods."""
        periods = []
        start = parent_start
        for i in range(9):
            idx = (parent_lord_idx + i) % 9
            sub_days = parent_days * (YEARS[idx] / TOTAL_YEARS)
            end = start + timedelta(days=sub_days)
            periods.append({
                'lord': LORDS[idx],
                'lord_position': idx + 1,
                'start': start,
                'end': end,
                'days': sub_days,
                'level': level_name,
            })
            start = end
        return periods

    def _find_current(periods, target):
        for p in periods:
            if p['start'] <= target < p['end']:
                return p
        return periods[-1] if periods else None

    # Level 2: Bhukti (sub-period of maha)
    maha_lord_idx = LORDS.index(maha['lord'])
    bhukti_periods = _subdivide(maha_lord_idx, maha['start'], maha['days'], 'bhukti')
    bhukti = _find_current(bhukti_periods, td)

    # Level 3: Pratyantara (sub-period of bhukti)
    bhukti_lord_idx = LORDS.index(bhukti['lord'])
    pratya_periods = _subdivide(bhukti_lord_idx, bhukti['start'], bhukti['days'], 'pratyantara')
    pratya = _find_current(pratya_periods, td)

    # Level 4: Sookshma (sub-period of pratyantara)
    pratya_lord_idx = LORDS.index(pratya['lord'])
    sookshma_periods = _subdivide(pratya_lord_idx, pratya['start'], pratya['days'], 'sookshma')
    sookshma = _find_current(sookshma_periods, td)

    # Level 5: Prana (sub-period of sookshma)
    sookshma_lord_idx = LORDS.index(sookshma['lord'])
    prana_periods = _subdivide(sookshma_lord_idx, sookshma['start'], sookshma['days'], 'prana')
    prana = _find_current(prana_periods, td)

    def _format_period(p, level_name):
        duration = p['days']
        if duration >= 365:
            dur_str = f"{duration / 365.25:.1f} years"
        elif duration >= 30:
            dur_str = f"{duration:.1f} days ({duration / 30.44:.1f} months)"
        elif duration >= 1:
            dur_str = f"{duration:.1f} days"
        elif duration * 24 >= 1:
            dur_str = f"{duration * 24:.1f} hours"
        else:
            dur_str = f"{duration * 24 * 60:.1f} minutes"

        return {
            'level': level_name,
            'lord': p['lord'],
            'glyph': GLYPHS.get(p['lord'], '?'),
            'lord_position': p['lord_position'],
            'start': p['start'].isoformat(),
            'end': p['end'].isoformat(),
            'duration': dur_str,
            'duration_days': round(p['days'], 4),
        }

    return {
        'birth': {
            'date': birth_date,
            'moon_longitude': birth_moon_lon,
            'nakshatra': birth_nak,
            'first_lord': LORDS[birth_lord_idx],
            'fraction_remaining': round(fraction_remaining, 4),
        },
        'target': td.isoformat(),
        'stack': [
            _format_period(maha, 'maha'),
            _format_period(bhukti, 'bhukti'),
            _format_period(pratya, 'pratyantara'),
            _format_period(sookshma, 'sookshma'),
            _format_period(prana, 'prana'),
        ],
        'sequence': f"{GLYPHS[maha['lord']]}{maha['lord']}-{GLYPHS[bhukti['lord']]}{bhukti['lord']}-{GLYPHS[pratya['lord']]}{pratya['lord']}-{GLYPHS[sookshma['lord']]}{sookshma['lord']}-{GLYPHS[prana['lord']]}{prana['lord']}",
    }


def get_current_nakshatra_transit(
    target_date: str = None,
    target_time: str = None,
    lat: float = 28.5383,
    lon: float = -81.3792,
) -> dict:
    """Get the Moon's current nakshatra position as a live transit layer.

    Args:
        target_date: YYYY-MM-DD (default: today)
        target_time: HH:MM (default: now)
        lat: Latitude (for local time context)
        lon: Longitude (for local time context)
    """
    if target_date:
        td = datetime.fromisoformat(target_date)
        if target_time:
            parts = target_time.split(':')
            td = td.replace(hour=int(parts[0]), minute=int(parts[1]),
                          second=int(parts[2]) if len(parts) > 2 else 0)
    else:
        td = datetime.now()

    # Convert to JD (assume EST/UTC-5 for now)
    utc_offset = 5.0 / 24.0  # EST
    jd = swe.julday(td.year, td.month, td.day,
                    td.hour + td.minute / 60.0 + td.second / 3600.0) + utc_offset

    # Current Moon position
    moon = swe.calc_ut(jd, swe.MOON)[0]
    moon_lon = moon[0]

    nak_info = _lon_to_nakshatra(moon_lon)

    # Find when Moon entered this nakshatra (scan backward)
    nak_start_lon = (nak_info['nakshatra_num'] - 1) * NAK_SPAN
    nak_end_lon = nak_start_lon + NAK_SPAN

    # Scan backward for entry
    check_jd = jd
    while check_jd > jd - 3:  # Max 3 days back
        check_jd -= 1.0 / 24  # 1-hour steps
        m = swe.calc_ut(check_jd, swe.MOON)[0]
        if int(m[0] / NAK_SPAN) != nak_info['nakshatra_num'] - 1:
            # Refine with binary search
            lo, hi = check_jd, check_jd + 1.0 / 24
            for _ in range(20):
                mid = (lo + hi) / 2
                mm = swe.calc_ut(mid, swe.MOON)[0]
                if int(mm[0] / NAK_SPAN) == nak_info['nakshatra_num'] - 1:
                    hi = mid
                else:
                    lo = mid
            entry_jd = hi
            break
    else:
        entry_jd = None

    # Scan forward for exit
    check_jd = jd
    while check_jd < jd + 3:
        check_jd += 1.0 / 24
        m = swe.calc_ut(check_jd, swe.MOON)[0]
        if int(m[0] / NAK_SPAN) != nak_info['nakshatra_num'] - 1:
            lo, hi = check_jd - 1.0 / 24, check_jd
            for _ in range(20):
                mid = (lo + hi) / 2
                mm = swe.calc_ut(mid, swe.MOON)[0]
                if int(mm[0] / NAK_SPAN) == nak_info['nakshatra_num'] - 1:
                    lo = mid
                else:
                    hi = mid
            exit_jd = hi
            break
    else:
        exit_jd = None

    def _jd_to_str(j):
        if j is None:
            return None
        # Convert JD back to local time
        y, mo, d, h = swe.revjul(j - utc_offset)
        hours = int(h)
        minutes = int((h - hours) * 60)
        return f"{y}-{mo:02d}-{d:02d} {hours:02d}:{minutes:02d}"

    # Pada timing
    pada_start_lon = nak_start_lon + (nak_info['pada'] - 1) * PADA_SPAN
    pada_end_lon = pada_start_lon + PADA_SPAN

    return {
        'moon': {
            'longitude': round(moon_lon, 4),
            'sign': nak_info['sign'],
            'degree': f"{nak_info['degree_in_sign']:.2f}° {nak_info['sign']}",
        },
        'nakshatra': {
            'name': nak_info['nakshatra'],
            'number': nak_info['nakshatra_num'],
            'lord': nak_info['lord'],
            'glyph': GLYPHS.get(nak_info['lord'], '?'),
            'lord_position': nak_info['lord_position'],
            'entered': _jd_to_str(entry_jd),
            'exits': _jd_to_str(exit_jd),
            'duration_hours': round((exit_jd - entry_jd) * 24, 1) if entry_jd and exit_jd else None,
        },
        'pada': {
            'number': nak_info['pada'],
            'aim': nak_info['pada_aim'],
            'degree_range': f"{pada_start_lon:.2f}° - {pada_end_lon:.2f}°",
        },
    }


def get_full_timing_stack(
    name: str,
    target_date: str = None,
    target_time: str = None,
) -> dict:
    """Compute the full 7-level timing stack for a stored chart.

    Levels 1-5: Vimshottari dasha (mathematical, birth-seeded)
    Level 6: Transiting Moon nakshatra lord (~24 hours)
    Level 7: Transiting Moon pada (~6 hours)

    Plus Ki stack (solar-terrestrial cascade) if birth_date available.

    Args:
        name: Chart name (e.g., 'chris', 'lisa')
        target_date: YYYY-MM-DD (default: today)
        target_time: HH:MM:SS (default: now)
    """
    import json as _json
    import os

    chart_path = os.path.join(os.path.dirname(__file__), 'charts', f'{name}.json')
    if not os.path.exists(chart_path):
        return {'error': f'Chart not found: {name}'}

    with open(chart_path) as f:
        chart = _json.load(f)

    birth_data = chart.get('birthData', {})
    birth_date = birth_data.get('date')
    if not birth_date:
        return {'error': 'Chart has no birth date'}

    # Get natal Moon longitude
    moon_planet = next((p for p in chart.get('planets', []) if p['name'] == 'Moon'), None)
    if not moon_planet:
        return {'error': 'Chart has no Moon data'}
    birth_moon_lon = float(moon_planet['longitude'])

    # Dasha stack (levels 1-5)
    dasha = compute_dasha_stack(birth_date, birth_moon_lon, target_date, target_time)

    # Nakshatra transit (levels 6-7)
    lat = birth_data.get('location', {}).get('latitude', 28.5383)
    lon_val = birth_data.get('location', {}).get('longitude', -81.3792)
    transit = get_current_nakshatra_transit(target_date, target_time, lat, lon_val)

    # Ki stack
    ki_stack = None
    try:
        from convergence_ki import get_convergence_ki
        ki_kwargs = {'birth_date': birth_date}
        if target_date:
            ki_kwargs['target_date'] = target_date
        ki_kwargs['lat'] = lat
        ki_kwargs['lon'] = lon_val
        ki_result = get_convergence_ki(**ki_kwargs)
        if 'personal' in ki_result:
            ki_stack = ki_result['personal']
        ki_global = {
            'year': ki_result.get('year', {}),
            'month': ki_result.get('month', {}),
            'day': ki_result.get('day', {}),
            'hour': ki_result.get('hour', {}),
        }
    except Exception as e:
        ki_stack = {'error': str(e)}
        ki_global = {'error': str(e)}

    # ── Zodiacal Releasing (both lots) ──
    zr_data = {}
    try:
        from zr import zr_for_chart, format_zr_summary

        if target_date:
            if target_time:
                zr_target = datetime.fromisoformat(f"{target_date}T{target_time}")
            else:
                zr_target = datetime.fromisoformat(f"{target_date}T12:00:00")
        else:
            zr_target = datetime.now()

        for lot_name in ['spirit', 'fortune']:
            try:
                snapshot = zr_for_chart(chart, zr_target, lot_name)
                snap_dict = snapshot.to_dict()

                # Extract concise level summary
                levels = []
                for i in range(1, 6):
                    lkey = f'L{i}'
                    if lkey in snap_dict:
                        lv = snap_dict[lkey]
                        levels.append({
                            'level': lkey,
                            'sign': lv.get('sign'),
                            'ruler': lv.get('ruler'),
                            'start': lv.get('start'),
                            'end': lv.get('end'),
                            'is_angular': lv.get('is_angular', False),
                            'is_peak': lv.get('is_peak', False),
                            'peak_type': lv.get('peak_type'),
                            'duration_days': lv.get('duration_days'),
                        })

                zr_data[lot_name] = {
                    'levels': levels,
                    'is_loosing': snap_dict.get('is_loosing_of_bond', False),
                    'loosing_details': snap_dict.get('loosing_details'),
                    'lot_sign': snap_dict.get('lot_sign'),
                    'lot_degree': snap_dict.get('lot_degree'),
                }
            except Exception as e:
                zr_data[lot_name] = {'error': str(e)}
    except ImportError as e:
        zr_data = {'error': f'ZR module not available: {e}'}

    # ── Resonances ──
    transit_lord = transit['nakshatra']['lord']
    resonances = []
    for level in dasha.get('stack', []):
        if level['lord'] == transit_lord:
            resonances.append(level['level'])

    return {
        'name': chart.get('name', name),
        'target': dasha.get('target'),
        'dasha': {
            'birth_nakshatra': dasha['birth']['nakshatra']['nakshatra'],
            'birth_lord': dasha['birth']['first_lord'],
            'sequence': dasha['sequence'],
            'stack': dasha['stack'],
        },
        'zodiacal_releasing': zr_data,
        'nakshatra_transit': transit,
        'ki': {
            'global': ki_global,
            'personal': ki_stack,
        },
        'resonances': {
            'transit_lord_in_dasha': resonances if resonances else None,
            'note': f"Transit Moon in {transit['nakshatra']['name']} ({transit_lord}) {'matches ' + ', '.join(resonances) + ' dasha' if resonances else 'no dasha lord match'}"
        },
    }
