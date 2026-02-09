"""
Zodiacal Releasing Calculator
Native implementation for Stella MCP server.

Based on Vettius Valens' technique from Anthology.
Uses Egyptian year (360 days) and month (30 days).
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# Sign periods - minor years of planetary rulers
SIGN_YEARS = {
    "Aries": 15,       # Mars
    "Taurus": 8,       # Venus  
    "Gemini": 20,      # Mercury
    "Cancer": 25,      # Moon
    "Leo": 19,         # Sun
    "Virgo": 20,       # Mercury
    "Libra": 8,        # Venus
    "Scorpio": 15,     # Mars
    "Sagittarius": 12, # Jupiter
    "Capricorn": 27,   # Saturn
    "Aquarius": 30,    # Saturn
    "Pisces": 12,      # Jupiter
}

SIGN_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

# Egyptian calendar
EGYPTIAN_YEAR = 360  # days
EGYPTIAN_MONTH = 30  # days

# Level multipliers (days per "year" at each level)
LEVEL_MULTIPLIERS = {
    1: EGYPTIAN_YEAR,           # L1: years → 360 days per year
    2: EGYPTIAN_MONTH,          # L2: months → 30 days per "year"  
    3: EGYPTIAN_MONTH / 12,     # L3: ~2.5 days per "year"
    4: EGYPTIAN_MONTH / 144,    # L4: ~0.208 days per "year" (~5 hours)
    5: EGYPTIAN_MONTH / 1728,   # L5: ~0.017 days per "year" (~25 min)
}


@dataclass
class ZRPeriod:
    """A single Zodiacal Releasing period."""
    sign: str
    start: datetime
    end: datetime
    level: int
    is_angular: bool  # angular from the lot being released (used for loosing of bond)
    is_peak: bool     # angular from Fortune (used for peak periods — ALWAYS from Fortune)
    peak_type: Optional[str]  # "Major Peak", "Moderate Peak", "Minor Peak", or None
    ruler: str
    
    @property
    def duration_days(self) -> float:
        return (self.end - self.start).total_seconds() / 86400
    
    def contains(self, dt: datetime) -> bool:
        return self.start <= dt < self.end
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sign": self.sign,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "level": self.level,
            "is_angular": self.is_angular,
            "is_peak": self.is_peak,
            "peak_type": self.peak_type,
            "ruler": self.ruler,
            "duration_days": round(self.duration_days, 2),
        }


@dataclass 
class ZRSnapshot:
    """Complete ZR state at a specific moment."""
    target_date: datetime
    lot: str
    lot_sign: str
    lot_degree: float
    L1: ZRPeriod
    L2: ZRPeriod
    L3: ZRPeriod
    L4: ZRPeriod
    L5: ZRPeriod
    is_loosing_of_bond: bool
    loosing_details: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_date": self.target_date.isoformat(),
            "lot": self.lot,
            "lot_sign": self.lot_sign,
            "lot_degree": round(self.lot_degree, 2),
            "L1": self.L1.to_dict(),
            "L2": self.L2.to_dict(),
            "L3": self.L3.to_dict(),
            "L4": self.L4.to_dict(),
            "L5": self.L5.to_dict(),
            "is_loosing_of_bond": self.is_loosing_of_bond,
            "loosing_details": self.loosing_details,
        }


def get_sign_index(sign: str) -> int:
    return SIGN_ORDER.index(sign)


def get_sign_at_offset(start_sign: str, offset: int) -> str:
    start_idx = get_sign_index(start_sign)
    return SIGN_ORDER[(start_idx + offset) % 12]


def get_ruler(sign: str) -> str:
    rulers = {
        "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
        "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
        "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
        "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
    }
    return rulers[sign]


def is_angular_from(sign: str, lot_sign: str) -> bool:
    """Check if sign is angular (1st, 4th, 7th, 10th) from lot sign."""
    lot_idx = get_sign_index(lot_sign)
    sign_idx = get_sign_index(sign)
    offset = (sign_idx - lot_idx) % 12
    return offset in [0, 3, 6, 9]


def get_peak_type_from_fortune(sign: str, fortune_sign: str) -> Optional[str]:
    """
    Determine peak type based on angularity from Lot of Fortune.
    Peak periods are ALWAYS calculated from Fortune, regardless of which lot is released.
    
    Per Brennan's worksheet:
    - 1st from Fortune (Fortune itself) = Major Peak
    - 10th from Fortune = Major Peak  
    - 7th from Fortune = Moderate Peak
    - 4th from Fortune = Minor Peak
    """
    fortune_idx = get_sign_index(fortune_sign)
    sign_idx = get_sign_index(sign)
    offset = (sign_idx - fortune_idx) % 12
    
    if offset == 0:
        return "Major Peak"    # Fortune itself
    elif offset == 9:
        return "Major Peak"    # 10th from Fortune
    elif offset == 6:
        return "Moderate Peak" # 7th from Fortune
    elif offset == 3:
        return "Minor Peak"    # 4th from Fortune
    else:
        return None


def get_period_days(sign: str, level: int) -> float:
    """Get duration in days for a sign at a given level."""
    years = SIGN_YEARS[sign]
    multiplier = LEVEL_MULTIPLIERS[level]
    return years * multiplier


def find_period_at_level(
    start_sign: str,
    level_start: datetime,
    target_dt: datetime,
    level: int,
    lot_sign: str,
    fortune_sign: str,
) -> ZRPeriod:
    """
    Find which period contains target_dt at given level.
    Cycles through signs starting from start_sign.
    
    lot_sign: the lot being released (for angularity/loosing of bond)
    fortune_sign: Lot of Fortune sign (for peak period calculation — always from Fortune)
    """
    current_dt = level_start
    current_sign = start_sign
    
    # Safety limit for cycles
    max_iterations = 1000
    iterations = 0
    
    while iterations < max_iterations:
        period_days = get_period_days(current_sign, level)
        period_end = current_dt + timedelta(days=period_days)
        
        if current_dt <= target_dt < period_end:
            peak_type = get_peak_type_from_fortune(current_sign, fortune_sign)
            return ZRPeriod(
                sign=current_sign,
                start=current_dt,
                end=period_end,
                level=level,
                is_angular=is_angular_from(current_sign, lot_sign),
                is_peak=peak_type is not None,
                peak_type=peak_type,
                ruler=get_ruler(current_sign),
            )
        
        current_dt = period_end
        current_sign = get_sign_at_offset(current_sign, 1)
        iterations += 1
    
    raise ValueError(f"Could not find period at level {level} for {target_dt}")


def calculate_zr(
    lot_sign: str,
    lot_degree: float,
    birth_dt: datetime,
    target_dt: datetime,
    lot_name: str = "spirit",
    fortune_sign: Optional[str] = None,
) -> ZRSnapshot:
    """
    Calculate complete Zodiacal Releasing snapshot.
    
    Key insight: Each level has fixed period lengths (years/months/days).
    L2 starts from L1 sign, L3 starts from L2 sign, etc.
    
    Peak periods are ALWAYS calculated from Fortune, per Brennan/Valens.
    fortune_sign must be provided for accurate peak marking.
    If not provided, falls back to lot_sign (only correct when releasing from Fortune).
    """
    f_sign = fortune_sign if fortune_sign else lot_sign
    
    # L1: Start from lot sign at birth
    l1 = find_period_at_level(lot_sign, birth_dt, target_dt, 1, lot_sign, f_sign)
    
    # L2: Start from L1 sign at L1 start
    l2 = find_period_at_level(l1.sign, l1.start, target_dt, 2, lot_sign, f_sign)
    
    # L3: Start from L2 sign at L2 start  
    l3 = find_period_at_level(l2.sign, l2.start, target_dt, 3, lot_sign, f_sign)
    
    # L4: Start from L3 sign at L3 start
    l4 = find_period_at_level(l3.sign, l3.start, target_dt, 4, lot_sign, f_sign)
    
    # L5: Start from L4 sign at L4 start
    l5 = find_period_at_level(l4.sign, l4.start, target_dt, 5, lot_sign, f_sign)
    
    # Check Loosing of the Bond
    is_loosing = False
    loosing_details = None
    l1_angular = is_angular_from(l1.sign, lot_sign)
    l2_angular = is_angular_from(l2.sign, lot_sign)
    if l2_angular and not l1_angular:
        is_loosing = True
        loosing_details = f"L2 {l2.sign} (angular) loosing from L1 {l1.sign}"
    
    return ZRSnapshot(
        target_date=target_dt,
        lot=lot_name,
        lot_sign=lot_sign,
        lot_degree=lot_degree,
        L1=l1,
        L2=l2,
        L3=l3,
        L4=l4,
        L5=l5,
        is_loosing_of_bond=is_loosing,
        loosing_details=loosing_details,
    )


def format_zr_summary(snapshot: ZRSnapshot) -> str:
    """Format ZR snapshot as human-readable summary."""
    lines = [
        f"## Zodiacal Releasing from {snapshot.lot.title()} ({snapshot.lot_sign} {snapshot.lot_degree:.0f}°)",
        f"**Target:** {snapshot.target_date.strftime('%Y-%m-%d %H:%M')} ",
        "",
    ]
    
    for level_name, period in [("L1", snapshot.L1), ("L2", snapshot.L2), 
                               ("L3", snapshot.L3), ("L4", snapshot.L4), 
                               ("L5", snapshot.L5)]:
        peak = f" ⭐ {period.peak_type}" if period.is_peak else ""
        lines.append(
            f"**{level_name}:** {period.sign} ({period.ruler}){peak}\n"
            f"    {period.start.strftime('%Y-%m-%d %H:%M')} → "
            f"{period.end.strftime('%Y-%m-%d %H:%M')} ({format_duration(period.duration_days)})"
        )
    
    if snapshot.is_loosing_of_bond:
        lines.append(f"\n⚡ **Loosing of the Bond:** {snapshot.loosing_details}")
    
    return "\n".join(lines)


def format_duration(days: float) -> str:
    """Format duration in human-readable form."""
    if days >= 365:
        return f"{days / 365.25:.1f} years"
    elif days >= 30:
        return f"{days / 30.44:.1f} months"
    elif days >= 1:
        return f"{days:.1f} days"
    else:
        hours = days * 24
        if hours >= 1:
            return f"{hours:.1f} hours"
        else:
            return f"{hours * 60:.1f} minutes"


def zr_for_chart(
    chart_data: Dict[str, Any],
    target_dt: datetime,
    lot: str = "spirit",
) -> ZRSnapshot:
    """Calculate ZR from a Stella chart.
    
    Peak periods are always calculated from Lot of Fortune,
    regardless of which lot is being released (per Brennan/Valens).
    """
    lots = chart_data.get("lots", {})
    birth_data = chart_data.get("birthData", {})
    
    lot_data = lots.get(lot, {})
    lot_sign = lot_data.get("sign")
    lot_degree = float(lot_data.get("degreeInSign", 0))
    
    # Fortune sign is always needed for peak period calculation
    fortune_data = lots.get("fortune", {})
    fortune_sign = fortune_data.get("sign")
    
    birth_date = birth_data.get("date")
    birth_time = birth_data.get("time", "12:00:00")
    birth_dt = datetime.fromisoformat(f"{birth_date}T{birth_time}")
    
    return calculate_zr(lot_sign, lot_degree, birth_dt, target_dt, lot, fortune_sign=fortune_sign)


if __name__ == "__main__":
    # Test with Buckley's chart
    # Lot of Spirit: Scorpio 22.94°, Lot of Fortune: Gemini 8.8°
    # Birth: May 1, 1986, 14:35 Orlando
    birth = datetime(1986, 5, 1, 14, 35)
    target = datetime(2026, 2, 9, 12, 0)
    
    spirit = calculate_zr("Scorpio", 22.94, birth, target, "spirit", fortune_sign="Gemini")
    print(format_zr_summary(spirit))
    print()
    fortune = calculate_zr("Gemini", 8.8, birth, target, "fortune", fortune_sign="Gemini")
    print(format_zr_summary(fortune))
