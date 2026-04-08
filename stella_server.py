#!/usr/bin/env python3
"""
Stella — Unified Astrology & Divination MCP Server

The Moon of Gnosis. Reflects the light of Helios (sweph API) through
the knowledge graph, I Ching divination, and interpretive layers.

Components:
  - Helios bridge: 14+ ephemeris tools via sweph REST API
  - Knowledge graph: 6,160+ chunks across 25 astrological texts
  - I Ching: Hexagram casting with King Wen sequence
  - Resources: Zodiac, planets, houses, aspects, personal charts
  - Prompts: Interpretation templates
"""

import os
import sys
import json
import math
import random
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from openai import OpenAI
from neo4j import GraphDatabase
from mcp.server.fastmcp import FastMCP

# ── Config ──
STELLA_DIR = Path(__file__).parent
SWEPH_API_BASE = os.environ.get("SWEPH_API_BASE", "http://baratie:3000")
TRUST_LABELS = {1: "PRIMARY", 2: "BRIDGE", 3: "REFERENCE", 4: "PERIPHERAL"}

# Neo4j
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "selene_gnosis")

# ── Init ──
mcp = FastMCP("stella")


# ── Helpers ──

_openai_client = None


def get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client:
        return _openai_client
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        config_path = Path.home() / ".clawdbot" / "clawdbot.json"
        if config_path.exists():
            config = json.loads(config_path.read_text())
            skills = config.get("skills", {}).get("entries", {})
            for skill_name in ["openai-image-gen", "openai-whisper-api"]:
                api_key = skills.get(skill_name, {}).get("apiKey")
                if api_key:
                    break
    if not api_key:
        raise ValueError("No OPENAI_API_KEY found")
    _openai_client = OpenAI(api_key=api_key)
    return _openai_client


# ── Neo4j ──

_neo4j_driver = None


def get_neo4j():
    """Get or create Neo4j driver singleton."""
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    return _neo4j_driver


def neo4j_query(cypher: str, **params) -> list[dict]:
    """Run a Cypher query and return results as list of dicts."""
    driver = get_neo4j()
    with driver.session() as session:
        result = session.run(cypher, parameters=params)
        return [dict(record) for record in result]


def load_json(filename: str):
    filepath = STELLA_DIR / filename
    if filepath.exists():
        return json.loads(filepath.read_text())
    return None


async def call_sweph(endpoint: str, method: str = "GET", body: dict = None) -> dict:
    """Call the Helios (sweph) REST API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{SWEPH_API_BASE}{endpoint}"
        if method == "POST":
            resp = await client.post(url, json=body)
        else:
            resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 1: HELIOS BRIDGE — Ephemeris Tools
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
async def get_current_moon() -> str:
    """Get the current moon phase and sign."""
    data = await call_sweph("/moon-now")
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_planet_positions() -> str:
    """Get current positions of all planets."""
    data = await call_sweph("/planets-now")
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_planet_aspects() -> str:
    """Get current aspects between planets."""
    data = await call_sweph("/aspects-now")
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_weekly_moon_phase() -> str:
    """Get this week's major moon phase."""
    data = await call_sweph("/weekly-major-phase")
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_natal_chart(
    year: int,
    month: int,
    day: int,
    latitude: float,
    longitude: float,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> str:
    """Calculate a comprehensive natal chart for a specific birth date, time, and location.

    Returns full chart with planets, asteroids, houses, angles, aspects with
    applying/separating indicators, and calculated points (Part of Fortune/Spirit).

    Args:
        year: Birth year (e.g. 1990)
        month: Birth month (1-12)
        day: Birth day (1-31)
        hour: Birth hour 24h format (0-23), default 0
        minute: Birth minute (0-59), default 0
        second: Birth second (0-59), default 0
        latitude: Birth location latitude (e.g. 40.7128 for New York)
        longitude: Birth location longitude (e.g. -74.0060 for New York)
    """
    params = urlencode({
        "year": year, "month": month, "day": day,
        "hour": hour, "minute": minute, "second": second,
        "latitude": latitude, "longitude": longitude,
    })
    data = await call_sweph(f"/natal-chart?{params}")
    data = _apply_whole_sign_houses(data)
    return json.dumps(data, indent=2)


@mcp.tool()
async def generate_chart(
    name: str,
    year: int,
    month: int,
    day: int,
    latitude: float,
    longitude: float,
    hour: int = 12,
    minute: int = 0,
    timezone: Optional[str] = None,
    save: bool = True,
) -> str:
    """Generate a comprehensive natal chart and optionally save it.

    Returns full chart with planets, houses, dignities, sect, depositors, lots.

    Args:
        name: Name for the chart (used for storage and retrieval)
        year: Birth year (e.g. 1990)
        month: Birth month (1-12)
        day: Birth day (1-31)
        hour: Birth hour 24h format (0-23), default 12
        minute: Birth minute (0-59), default 0
        latitude: Birth location latitude
        longitude: Birth location longitude
        timezone: Timezone string (e.g. 'America/New_York')
        save: Whether to save the chart for future use (default True)
    """
    body = {
        "name": name, "year": year, "month": month, "day": day,
        "hour": hour, "minute": minute,
        "latitude": latitude, "longitude": longitude,
    }
    if timezone:
        body["timezone"] = timezone
    if save is not None:
        body["save"] = save
    data = await call_sweph("/generate-chart", method="POST", body=body)
    if "chart" in data:
        data["chart"] = _apply_whole_sign_houses(data["chart"])
    else:
        data = _apply_whole_sign_houses(data)
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_chart(name: str) -> str:
    """Retrieve a stored natal chart by name.

    Args:
        name: Name of the stored chart
    """
    data = await call_sweph(f"/chart/{name}")
    data = _apply_whole_sign_houses(data)
    return json.dumps(data, indent=2)


@mcp.tool()
async def list_charts() -> str:
    """List all stored natal charts."""
    data = await call_sweph("/charts")
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_profections(name: str, age: Optional[int] = None) -> str:
    """Get annual profections for a stored chart, including lord of year and 12-year timeline.

    Args:
        name: Name of the stored chart
        age: Age to calculate for (optional, defaults to current age)
    """
    query = f"?age={age}" if age is not None else ""
    data = await call_sweph(f"/profections/{name}{query}")
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_zodiacal_releasing(
    name: str,
    lot: Optional[str] = None,
    date: Optional[str] = None,
    time: Optional[str] = None,
) -> str:
    """Get Zodiacal Releasing L1-L5 periods for a stored chart.

    Native calculation - no external API dependency.
    Includes peak periods and loosing of the bond.

    Args:
        name: Name of the stored chart
        lot: 'spirit' or 'fortune' (default: both)
        date: Target date YYYY-MM-DD (default: today)
        time: Target time HH:MM (default: now)
    """
    from datetime import datetime
    from zr import zr_for_chart, format_zr_summary
    
    # Load chart
    chart_json = load_chart(name)
    if not chart_json or "not found" in chart_json.lower():
        return json.dumps({"error": f"Chart not found: {name}"})
    
    chart_data = json.loads(chart_json)
    
    # Parse target datetime
    if date:
        if time:
            target_dt = datetime.fromisoformat(f"{date}T{time}:00")
        else:
            target_dt = datetime.fromisoformat(f"{date}T12:00:00")
    else:
        target_dt = datetime.now()
    
    results = []
    
    lots_to_calc = [lot] if lot else ["spirit", "fortune"]
    
    for lot_name in lots_to_calc:
        try:
            snapshot = zr_for_chart(chart_data, target_dt, lot_name)
            results.append({
                "lot": lot_name,
                "summary": format_zr_summary(snapshot),
                "data": snapshot.to_dict(),
            })
        except Exception as e:
            results.append({
                "lot": lot_name,
                "error": str(e),
            })
    
    return json.dumps(results, indent=2, default=str)


@mcp.tool()
async def get_zr_report(
    name: str,
    date: Optional[str] = None,
    time: Optional[str] = None,
) -> str:
    """Generate comprehensive Zodiacal Releasing report using Brennan worksheet framework.

    Includes: peak periods from Fortune, sect analysis, angular triads,
    planets by phase, current periods, and key observations.

    Args:
        name: Name of the stored chart
        date: Target date YYYY-MM-DD (default: today)
        time: Target time HH:MM (default: now)
    """
    from datetime import datetime
    from zr_report import generate_zr_report
    
    # Load chart
    chart_json = load_chart(name)
    if not chart_json or "not found" in chart_json.lower():
        return json.dumps({"error": f"Chart not found: {name}"})
    
    chart_data = json.loads(chart_json)
    
    # Parse target datetime
    if date:
        if time:
            target_dt = datetime.fromisoformat(f"{date}T{time}:00")
        else:
            target_dt = datetime.fromisoformat(f"{date}T12:00:00")
    else:
        target_dt = datetime.now()
    
    report = generate_zr_report(chart_data, target_dt)
    return report


@mcp.tool()
async def get_ki(
    name: Optional[str] = None,
    date: Optional[str] = None,
    birth_date: Optional[str] = None,
) -> str:
    """Calculate 9 Star Ki numbers for a date.

    Returns the three Ki numbers (year.month.third) using the Lo Shu
    Flying Star method. When a chart name or birth_date is provided,
    includes personal year/month cycle (Lo Shu palace position).

    Args:
        name: Chart name - auto-loads birth date for personal cycle
        date: Target date YYYY-MM-DD (default: today)
        birth_date: Birth date YYYY-MM-DD - for natal Ki profile
    
    Returns global Ki + personal cycle when birth info available.
    """
    from datetime import date as date_type
    from ki import (calculate_ki, calculate_natal_ki, calculate_current_ki,
                    format_ki_report, get_full_profile, KI_TRIGRAMS)
    
    # If name provided, resolve birth date from chart
    if name and not birth_date:
        chart_data = await call_sweph(f"/chart/{name}")
        if isinstance(chart_data, dict) and "error" not in chart_data:
            birth_data = chart_data.get("birthData", {})
            bd = birth_data.get("date") or chart_data.get("birth_date") or chart_data.get("date")
            if bd:
                birth_date = bd
    
    if birth_date:
        # Full personal cycle: natal + where they are now
        bd = date_type.fromisoformat(birth_date)
        td = date_type.fromisoformat(date) if date else None
        profile = get_full_profile(bd, td)
        natal = profile['natal']
        cycle = profile['current_cycle']
        
        lines = []
        lines.append(f"# 9 Star Ki Profile")
        if name:
            lines.append(f"**Chart:** {name}")
        lines.append(f"**Birth Date:** {natal['birth_date']}")
        lines.append("")
        lines.append(f"## Natal Ki: {natal['sequence']}")
        yi = natal['year_info']
        mi = natal['month_info']
        ti = natal['third_info']
        lines.append(f"- Year: **{natal['ki_year']} {yi['trigram']} {yi['name']}** ({yi['element']})")
        lines.append(f"- Month: **{natal['ki_month']} {mi['trigram']} {mi['name']}** ({mi['element']})")
        lines.append(f"- Third: **{natal['ki_third']} {ti['trigram']} {ti['name']}** ({ti['element']})")
        lines.append("")
        lines.append(f"## Current Cycle ({cycle['date']})")
        lines.append(f"**Global:** {cycle['global_year']}.{cycle['global_month']}")
        pyi = cycle['personal_year_info']
        pmi = cycle['personal_month_info']
        lines.append(f"**Personal Year:** {cycle['personal_year']} {pyi['trigram']} {pyi['name']} ({pyi['element']})")
        lines.append(f"**Personal Month:** {cycle['personal_month']} {pmi['trigram']} {pmi['name']} ({pmi['element']})")
        
        return "\n".join(lines)
    elif date:
        # Global Ki for specific date
        d = date_type.fromisoformat(date)
        result = calculate_current_ki(d)
    else:
        # Global Ki for today
        result = calculate_current_ki()
    
    report = format_ki_report(result)
    return report


@mcp.tool()
async def get_ki_cycle(
    birth_date: str,
    target_date: Optional[str] = None,
) -> str:
    """Get full 9 Star Ki profile with current personal cycle.

    Calculates natal Ki and where the person is in their current
    year/month cycle using Flying Star Lo Shu method.

    Args:
        birth_date: Birth date YYYY-MM-DD
        target_date: Target date YYYY-MM-DD (default: today)
    
    Returns natal Ki + personal year + personal month.
    """
    from datetime import date as date_type
    from ki import get_full_profile, KI_TRIGRAMS
    
    bd = date_type.fromisoformat(birth_date)
    td = date_type.fromisoformat(target_date) if target_date else None
    
    profile = get_full_profile(bd, td)
    natal = profile['natal']
    cycle = profile['current_cycle']
    
    lines = []
    lines.append(f"# 9 Star Ki Profile")
    lines.append(f"**Birth Date:** {natal['birth_date']}")
    lines.append("")
    lines.append(f"## Natal Ki: {natal['sequence']}")
    yi = natal['year_info']
    mi = natal['month_info']
    ti = natal['third_info']
    lines.append(f"- Year: **{natal['ki_year']} {yi['trigram']} {yi['name']}** ({yi['element']})")
    lines.append(f"- Month: **{natal['ki_month']} {mi['trigram']} {mi['name']}** ({mi['element']})")
    lines.append(f"- Third: **{natal['ki_third']} {ti['trigram']} {ti['name']}** ({ti['element']})")
    lines.append("")
    lines.append(f"## Current Cycle ({cycle['date']})")
    lines.append(f"**Global:** {cycle['global_year']}.{cycle['global_month']}")
    pyi = cycle['personal_year_info']
    pmi = cycle['personal_month_info']
    lines.append(f"**Personal Year:** {cycle['personal_year']} {pyi['trigram']} {pyi['name']} ({pyi['element']})")
    lines.append(f"**Personal Month:** {cycle['personal_month']} {pmi['trigram']} {pmi['name']} ({pmi['element']})")
    
    return "\n".join(lines)


@mcp.tool()
async def get_ki_reading(
    birth_date: str,
    target_date: Optional[str] = None,
) -> str:
    """Generate combined 9 Star Ki + I Ching reading.

    Calculates natal Ki, personal cycle, derives hexagram from Ki positions,
    and retrieves relevant I Ching wisdom for a synthesized reading.

    The hexagram is derived from Ki (not randomly cast):
    - Lower trigram = Personal Year Ki
    - Upper trigram = Personal Month Ki
    - Transformation shows next month's hexagram
    - Changing lines are the lines that differ between hexagrams

    Args:
        birth_date: Birth date YYYY-MM-DD
        target_date: Target date YYYY-MM-DD (default: today)
    """
    from datetime import date as date_type, timedelta
    from ki import get_full_profile, KI_TRIGRAMS, calculate_personal_cycle
    from ki_reading import (
        format_full_reading, ki_to_hexagram, 
        get_hexagram_lines, find_changing_lines, get_next_month_ki
    )
    import json
    
    bd = date_type.fromisoformat(birth_date)
    td = date_type.fromisoformat(target_date) if target_date else date_type.today()
    
    # Get Ki profile
    profile = get_full_profile(bd, td)
    natal = profile['natal']
    cycle = profile['current_cycle']
    
    # Derive hexagram from Ki positions
    current_hex = ki_to_hexagram(cycle['personal_year'], cycle['personal_month'])
    
    # Get next month Ki and hexagram
    next_month_ki = get_next_month_ki(natal['ki_year'], td)
    next_hex = ki_to_hexagram(cycle['personal_year'], next_month_ki)
    
    # Find changing lines
    changing_lines = []
    if current_hex and next_hex:
        current_lines = get_hexagram_lines(cycle['personal_year'], cycle['personal_month'])
        next_lines = get_hexagram_lines(cycle['personal_year'], next_month_ki)
        if current_lines and next_lines:
            changing_lines = find_changing_lines(current_lines, next_lines)
    
    # Get wisdom from knowledge graph based on derived hexagram AND changing lines
    wisdom_snippets = []
    if current_hex:
        try:
            # Search for the hexagram with line-specific wisdom
            if changing_lines:
                line_terms = " ".join([f"line {l}" for l in changing_lines])
                search_terms = f"hexagram {current_hex} {line_terms}"
            else:
                search_terms = f"hexagram {current_hex}"
            
            wisdom_results = retrieve_wisdom(search_terms, top_k=5)
            if wisdom_results:
                results = json.loads(wisdom_results)
                if isinstance(results, list):
                    for r in results[:4]:
                        if isinstance(r, dict) and 'text' in r:
                            wisdom_snippets.append(r['text'][:500])
        except:
            pass  # Wisdom is optional
    
    # Generate reading (hexagram is derived inside format_full_reading)
    reading = format_full_reading(bd, td, None, wisdom_snippets)
    
    return reading


@mcp.tool()
async def get_daily_ki(
    birth_date: str,
    target_date: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> str:
    """Calculate traditional daily Ki cascade with 4-level global and personal Ki.
    
    This implements the traditional -3 descending pattern from classical 9 Star Ki:
    - Year Ki: Adjusted for Lichun (Sun at 315° / 15° Aquarius)
    - Month Ki: First_sub pattern, counts down by Sun's 30° segments from 315°
    - Day Ki: Day_starts_by_year lookup, counts days since Lichun, descends by 1
    - Hour Ki: First_sub from day Ki, counts down by 2-hour blocks
    
    Personal Ki at each level uses Flying Star method: natal year Ki flying to 
    global Ki positions. Returns both global and personal Ki at all 4 levels.
    
    For traditional personal daily Ki, use this tool.
    For experimental astronomical day Ki (Moon socket crossings), use get_convergence_ki_now.
    
    Args:
        birth_date: Birth date YYYY-MM-DD (required)
        target_date: Target date YYYY-MM-DD (optional, defaults to today)
        lat: Latitude for precise Lichun timing (optional, default: Orlando)
        lon: Longitude for precise Lichun timing (optional, default: Orlando)
    
    Returns:
        Global and personal Ki at year/month/day/hour levels with full cascade details.
    """
    from datetime import date as date_type
    from ki import calculate_daily_ki
    
    # Parse dates
    bd = date_type.fromisoformat(birth_date)
    td = date_type.fromisoformat(target_date) if target_date else None
    
    # Set up kwargs
    kwargs = {"birth_date": bd}
    if td:
        kwargs["target_date"] = td
    if lat is not None:
        kwargs["lat"] = lat
    if lon is not None:
        kwargs["lon"] = lon
    
    # Calculate daily Ki
    result = calculate_daily_ki(**kwargs)
    
    # Format output
    lines = []
    lines.append("# Traditional Daily Ki Cascade")
    lines.append(f"**Target Date:** {result['target_date']}")
    lines.append(f"**Birth Date:** {result['birth_date']}")
    lines.append(f"**Natal Year Ki:** {result['natal_year_ki']}")
    lines.append(f"**Lichun Date:** {result['lichun_date']} ({result['days_since_lichun']} days ago)")
    lines.append(f"**Local Time:** {result['local_time']}")
    lines.append("")
    
    lines.append("## Global Ki (Traditional Cascade)")
    g = result['global']
    lines.append(f"**Sequence:** {result['sequences']['global']}")
    lines.append(f"- **Year:** {g['year']['ki']} {g['year']['info']['trigram']} {g['year']['info']['name']} ({g['year']['info']['element']})")
    lines.append(f"- **Month:** {g['month']['ki']} {g['month']['info']['trigram']} {g['month']['info']['name']} ({g['month']['info']['element']})")
    lines.append(f"- **Day:** {g['day']['ki']} {g['day']['info']['trigram']} {g['day']['info']['name']} ({g['day']['info']['element']})")
    lines.append(f"- **Hour:** {g['hour']['ki']} {g['hour']['info']['trigram']} {g['hour']['info']['name']} ({g['hour']['info']['element']})")
    lines.append("")
    
    lines.append("## Personal Ki (Flying Star Method)")
    p = result['personal']
    lines.append(f"**Sequence:** {result['sequences']['personal']}")
    lines.append(f"- **Year:** {p['year']['ki']} {p['year']['info']['trigram']} {p['year']['info']['name']} ({p['year']['info']['element']})")
    lines.append(f"- **Month:** {p['month']['ki']} {p['month']['info']['trigram']} {p['month']['info']['name']} ({p['month']['info']['element']})")
    lines.append(f"- **Day:** {p['day']['ki']} {p['day']['info']['trigram']} {p['day']['info']['name']} ({p['day']['info']['element']})")
    lines.append(f"- **Hour:** {p['hour']['ki']} {p['hour']['info']['trigram']} {p['hour']['info']['name']} ({p['hour']['info']['element']})")
    
    return "\n".join(lines)


@mcp.tool()
async def get_ki_transition(
    birth_date: str,
    target_date: Optional[str] = None,
) -> str:
    """Show the current Ki transition — what's changing and the new hexagram.

    Identifies whether a Ki boundary is being crossed (Sun at ~15° of a sign)
    and shows the outgoing and incoming personal month Ki with hexagram derivation.

    The hexagram is formed by: incoming month trigram OVER personal year trigram.

    Args:
        birth_date: Birth date YYYY-MM-DD
        target_date: Target date YYYY-MM-DD (default: today)
    """
    from datetime import date as date_type, timedelta
    from ki import (get_full_profile, KI_TRIGRAMS, calculate_personal_cycle,
                    calculate_ki, MONTH_TABLE, _date_in_range)
    from ki_reading import ki_to_hexagram

    bd = date_type.fromisoformat(birth_date)
    td = date_type.fromisoformat(target_date) if target_date else date_type.today()

    profile = get_full_profile(bd, td)
    natal = profile['natal']
    cycle = profile['current_cycle']

    # Check if we're near a Ki boundary (within 2 days of a period edge)
    # Find current period and next period
    m, d = td.month, td.day
    current_period_idx = None
    for i, (start, end, values) in enumerate(MONTH_TABLE):
        if _date_in_range(m, d, start, end):
            current_period_idx = i
            break

    # Get previous and next period personal months
    prev_date = td - timedelta(days=5)
    next_date = td + timedelta(days=5)

    prev_cycle = calculate_personal_cycle(natal['ki_year'], prev_date)
    next_cycle = calculate_personal_cycle(natal['ki_year'], next_date)

    is_transition = (prev_cycle['personal_month'] != cycle['personal_month'] or
                     cycle['personal_month'] != next_cycle['personal_month'])

    # Current hexagram: month over year
    current_hex = ki_to_hexagram(cycle['personal_year'], cycle['personal_month'])
    next_hex = ki_to_hexagram(cycle['personal_year'], next_cycle['personal_month'])

    pm = cycle['personal_month']
    pm_info = KI_TRIGRAMS[pm]
    py = cycle['personal_year']
    py_info = KI_TRIGRAMS[py]
    npm = next_cycle['personal_month']
    npm_info = KI_TRIGRAMS[npm]
    ppm = prev_cycle['personal_month']
    ppm_info = KI_TRIGRAMS[ppm]

    lines = []
    lines.append("# 9 Star Ki Transition Report")
    lines.append(f"**Date:** {td.isoformat()}")
    lines.append(f"**Natal Ki:** {natal['sequence']} ({natal['ki_year']} {KI_TRIGRAMS[natal['ki_year']]['name']})")
    lines.append(f"**Personal Year:** {py} {py_info['trigram']} {py_info['name']} ({py_info['chinese']})")
    lines.append("")

    if is_transition and ppm != pm:
        lines.append(f"## ⚡ Ki Transition Active")
        lines.append(f"**Outgoing Month:** {ppm} {ppm_info['trigram']} {ppm_info['name']} ({ppm_info['chinese']})")
        lines.append(f"**Incoming Month:** {pm} {pm_info['trigram']} {pm_info['name']} ({pm_info['chinese']})")
        lines.append("")
        lines.append(f"### Previous Hexagram")
        prev_hex = ki_to_hexagram(py, ppm)
        lines.append(f"**{ppm_info['trigram']} {ppm_info['name']} over {py_info['trigram']} {py_info['name']} → Hexagram {prev_hex}**")
        lines.append("")
        lines.append(f"### New Hexagram")
        lines.append(f"**{pm_info['trigram']} {pm_info['name']} over {py_info['trigram']} {py_info['name']} → Hexagram {current_hex}**")
    elif is_transition and pm != npm:
        lines.append(f"## ⚡ Ki Transition Approaching")
        lines.append(f"**Current Month:** {pm} {pm_info['trigram']} {pm_info['name']} ({pm_info['chinese']})")
        lines.append(f"**Incoming Month:** {npm} {npm_info['trigram']} {npm_info['name']} ({npm_info['chinese']})")
        lines.append("")
        lines.append(f"### Current Hexagram")
        lines.append(f"**{pm_info['trigram']} {pm_info['name']} over {py_info['trigram']} {py_info['name']} → Hexagram {current_hex}**")
        lines.append("")
        lines.append(f"### Next Hexagram")
        lines.append(f"**{npm_info['trigram']} {npm_info['name']} over {py_info['trigram']} {py_info['name']} → Hexagram {next_hex}**")
    else:
        lines.append(f"## Current Ki Period (no transition)")
        lines.append(f"**Personal Month:** {pm} {pm_info['trigram']} {pm_info['name']} ({pm_info['chinese']})")
        lines.append(f"**Hexagram:** {pm_info['trigram']} {pm_info['name']} over {py_info['trigram']} {py_info['name']} → Hexagram {current_hex}")

    # Find the current period boundaries
    if current_period_idx is not None:
        start, end, _ = MONTH_TABLE[current_period_idx]
        lines.append("")
        lines.append(f"**Period:** {start[0]}/{start[1]} – {end[0]}/{end[1]}")

    lines.append("")
    lines.append("---")
    lines.append(f"*Hexagram = incoming month trigram over personal year trigram*")
    lines.append(f"*Ki boundaries align with Sun crossing ~15° of each sign*")

    return "\n".join(lines)


@mcp.tool()
async def get_convergence_ki_now(
    target_date: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    birth_date: Optional[str] = None,
) -> str:
    """Get the full 7-level Ki stack using convergence socket theory.

    **EXPERIMENTAL ASTRONOMICAL MODEL** — This day Ki calculation (Socket Period)
    uses Moon crossings of convergence sockets (~9 days) instead of the traditional
    daily cascade. This is a modern astronomical interpretation, not classical
    9 Star Ki practice.

    For traditional personal daily Ki, use `get_daily_ki` instead.

    Three bodies cross the same 12 mid-sign gates (15° of each sign) at three speeds.
    Same grid, same 12, same 15°, same 9 Ki, same remainder 3, same triad lock.
    One relationship, three octaves.

    The 7 levels:
    ☉ SOLAR:
      1. Year Ki — Sun completes orbit, ticks at Lichun (15° Aquarius)
      2. Month Ki — Sun crosses 15° of each sign (~30 days)
    ☽ LUNAR:
      3. Lunar Gate — Moon crosses 15° of each sign (~2.3 days, 12 per sidereal month)
      4. Socket Period (Day Ki) — Moon crosses convergence sockets (~9 days)
    ⊕ TERRESTRIAL:
      5. Mid-Sign Hour — Ascendant crosses 15° of each sign (~2 hrs)
      6. Gate Ki — Ascendant crosses any 15° gate (~60 min)
      7. Minute Ki — 1/9th subdivision of gate crossing (~6.7 min)

    12-fold layers (year→month, sidereal month→lunar gate, sidereal day→mid-sign hour)
    have remainder 3 → triad-locked, 3 unique sequences.
    9-fold layers (socket period, gate/minute) have all 9 numbers once.

    If birth_date is provided, also returns personal Ki (year/month/day) with
    full audit trail showing global vs personal Ki at each socket crossing.

    Args:
        target_date: ISO date YYYY-MM-DD (default: today)
        lat: Latitude for hour Ki (default: 28.5383 / Orlando)
        lon: Longitude for hour Ki (default: -81.3792 / Orlando)
        birth_date: Birth date YYYY-MM-DD for personal Ki calculation
    """
    from convergence_ki import get_convergence_ki
    kwargs = {}
    if target_date:
        kwargs["target_date"] = target_date
    if lat is not None:
        kwargs["lat"] = lat
    if lon is not None:
        kwargs["lon"] = lon
    if birth_date:
        kwargs["birth_date"] = birth_date
    result = get_convergence_ki(**kwargs)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def get_synodic_gate_now(
    target_date: Optional[str] = None,
    birth_date: Optional[str] = None,
) -> str:
    """Get the Synodic Gate Ki — the ~12-year Jupiter cycle (5th level of Ki stack).

    The Sun orbits the solar system's barycenter with a dominant period of
    ~11.86 years (Jupiter's orbital period). Jupiter's perihelion marks the
    peak gravitational coupling — the Sun and Jupiter at maximum pull.

    The synodic gate starts at the Lichun preceding perihelion, following
    the same pattern as all other Ki levels: the gate before the event.

    12 years per gate, 9 Ki count, remainder 3 → triad-locked.
    At each gate boundary, year Ki is always Earth (2, 5, 8).
    9 synodic gates = ~108 years (a sacred number: 12 × 9).

    Full stack: Synodic.Year.Month.Day.Hour

    Args:
        target_date: ISO date YYYY-MM-DD (default: today)
        birth_date: Birth date YYYY-MM-DD for personal synodic Ki
    """
    from convergence_ki import get_synodic_gate
    kwargs = {}
    if target_date:
        kwargs["target_date"] = target_date
    if birth_date:
        kwargs["birth_date"] = birth_date
    result = get_synodic_gate(**kwargs)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def get_natal_gates(name: str) -> str:
    """Map a natal chart's planets to their 15° gates and permanent San Cai triads.

    Shows which gate each planet falls in, its locked triad (Man/Earth/Heaven),
    possible Ki numbers, and whether it sits on a convergence socket.

    The 24 gates (every 15° of the ecliptic) each permanently belong to one triad.
    This mapping is structural — it doesn't change with time or location.

    Args:
        name: Chart name (e.g., 'chris', 'lisa', 'betsy')
    """
    from convergence_ki import get_natal_gates as _get_natal_gates
    result = _get_natal_gates(name)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def get_transits_now(
    name: str,
    major: Optional[bool] = None,
    orb: Optional[float] = None,
) -> str:
    """Get all current transits to a stored natal chart, sorted by orb.

    Includes profection context.

    Args:
        name: Name of the stored chart
        major: Only major aspects
        orb: Max orb in degrees
    """
    parts = []
    if major:
        parts.append("major=true")
    if orb is not None:
        parts.append(f"orb={orb}")
    query = f"?{'&'.join(parts)}" if parts else ""
    data = await call_sweph(f"/transits/{name}/now{query}")
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_transit_summary(name: str) -> str:
    """Get high-level summary of major outer planet transits with timing context (profections + ZR).

    Args:
        name: Name of the stored chart
    """
    data = await call_sweph(f"/transits/{name}/summary")
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_dignity_score(
    planet: str,
    sign: Optional[str] = None,
    degree: Optional[float] = None,
    longitude: Optional[float] = None,
    isDaySect: Optional[bool] = None,
) -> str:
    """Calculate essential dignity score for any planet at any position.

    Returns all 5 dignities plus debilities.

    Args:
        planet: Planet name (e.g. 'mars', 'venus')
        sign: Zodiac sign (if not using longitude)
        degree: Degree 0-30 within sign
        longitude: Ecliptic longitude 0-360 (alternative to sign+degree)
        isDaySect: Is this a day chart?
    """
    parts = [f"planet={planet}"]
    if longitude is not None:
        parts.append(f"longitude={longitude}")
    else:
        if sign:
            parts.append(f"sign={sign}")
            # API requires both sign AND degree; default to 15 (middle of sign)
            parts.append(f"degree={degree if degree is not None else 15}")
        elif degree is not None:
            parts.append(f"degree={degree}")
    if isDaySect is not None:
        parts.append(f"isDaySect={'true' if isDaySect else 'false'}")
    data = await call_sweph(f"/dignity-score?{'&'.join(parts)}")
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_current_dignities(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> str:
    """Get dignity scores for all planets at their current positions, including sect status.

    Args:
        lat: Latitude (for sect calculation)
        lon: Longitude (for sect calculation)
    """
    parts = []
    if lat is not None:
        parts.append(f"lat={lat}")
    if lon is not None:
        parts.append(f"lon={lon}")
    query = f"?{'&'.join(parts)}" if parts else ""
    data = await call_sweph(f"/current-dignities{query}")
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_void_of_course_moons(
    timeframe: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """Get Void of Course Moon periods.

    Uses Ptolemaic aspects (conjunction, sextile, square, trine, opposition)
    to all major planets (Sun through Pluto) to determine when the Moon
    makes its last major aspect before changing signs.

    Native calculation via pyswisseph — no Helios dependency.

    Three ways to specify the period:
    1. timeframe: 'day', 'week', or 'month' (relative to today)
    2. start_date + end_date: Custom date range (YYYY-MM-DD format)
    3. Neither: defaults to 'week'

    Args:
        timeframe: 'day' | 'week' | 'month' — relative period from today
        start_date: Start of custom range (YYYY-MM-DD), requires end_date
        end_date: End of custom range (YYYY-MM-DD), requires start_date

    Returns:
        JSON array of VOC periods with:
        - start: When Moon goes VOC (last Ptolemaic aspect perfects)
        - end: When Moon enters the next sign
        - duration: Human-readable duration
        - lastAspect: The final aspect before VOC
        - previousSign: Sign Moon is leaving
        - newSign: Sign Moon is entering
    """
    from datetime import date, timedelta
    from voc import calculate_voc

    today = date.today()

    if start_date and end_date:
        s, e = start_date, end_date
    elif timeframe:
        tf = timeframe.lower()
        if tf not in ("day", "week", "month"):
            return json.dumps({
                "error": f"Invalid timeframe '{timeframe}'. Use 'day', 'week', or 'month'."
            })
        s = today.isoformat()
        if tf == "day":
            e = today.isoformat()
        elif tf == "week":
            e = (today + timedelta(days=7)).isoformat()
        else:  # month
            e = (today + timedelta(days=30)).isoformat()
    else:
        # Default: this week
        s = today.isoformat()
        e = (today + timedelta(days=7)).isoformat()

    try:
        periods = calculate_voc(s, e)
        return json.dumps({
            "dateRange": {"start": s, "end": e},
            "timezone": "America/New_York",
            "voidOfCourseMoons": periods,
        }, indent=2)
    except Exception as ex:
        return json.dumps({"error": str(ex)})


# ── Ephemeris tools (pyswisseph native) ──

import ephemeris as eph


@mcp.tool()
async def transit_timing(
    name: str,
    transit_planet: str,
    natal_planet: str,
    aspect: str,
    orb: float = 3.0,
) -> str:
    """Find when a specific transit enters orb, perfects, and leaves orb.

    Args:
        name: Chart name (e.g. 'chris')
        transit_planet: Transiting planet (e.g. 'Saturn')
        natal_planet: Natal planet or point (e.g. 'Sun')
        aspect: Aspect type (conjunction, sextile, square, trine, opposition)
        orb: Orb in degrees (default 3.0)
    """
    try:
        result = eph.transit_timing(name, transit_planet, natal_planet, aspect, orb)
        return json.dumps(result, indent=2)
    except Exception as ex:
        return json.dumps({"error": str(ex)})


@mcp.tool()
async def search_next_transit(
    name: str,
    transit_planet: Optional[str] = None,
    natal_planet: Optional[str] = None,
    aspect: Optional[str] = None,
    days: int = 90,
) -> str:
    """Search for upcoming transits to a natal chart.

    Args:
        name: Chart name (e.g. 'chris')
        transit_planet: Filter by transiting planet (optional)
        natal_planet: Filter by natal planet (optional)
        aspect: Filter by aspect type (optional)
        days: Number of days to search (default 90)
    """
    try:
        result = eph.search_next_transit(name, transit_planet, natal_planet, aspect, days)
        return json.dumps(result, indent=2)
    except Exception as ex:
        return json.dumps({"error": str(ex)})


@mcp.tool()
async def lunar_return(
    name: str,
    target_date: Optional[str] = None,
) -> str:
    """Calculate the next lunar return chart.

    Args:
        name: Chart name (e.g. 'chris')
        target_date: Start searching from this date, YYYY-MM-DD (default: today)
    """
    try:
        result = eph.lunar_return(name, target_date)
        return json.dumps(result, indent=2)
    except Exception as ex:
        return json.dumps({"error": str(ex)})


@mcp.tool()
async def solar_return(
    name: str,
    year: Optional[int] = None,
) -> str:
    """Calculate solar return chart for a given year.

    Args:
        name: Chart name (e.g. 'chris')
        year: Year for the solar return (default: current year)
    """
    try:
        result = eph.solar_return(name, year)
        return json.dumps(result, indent=2)
    except Exception as ex:
        return json.dumps({"error": str(ex)})


@mcp.tool()
async def secondary_progressions(
    name: str,
    target_date: Optional[str] = None,
) -> str:
    """Calculate secondary progressed chart (1 day = 1 year).

    Args:
        name: Chart name (e.g. 'chris')
        target_date: Date to progress to, YYYY-MM-DD (default: today)
    """
    try:
        result = eph.progressions(name, target_date)
        return json.dumps(result, indent=2)
    except Exception as ex:
        return json.dumps({"error": str(ex)})


@mcp.tool()
async def find_elections(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    lat: float = 28.5383,
    lon: float = -81.3792,
    moon_signs: Optional[str] = None,
) -> str:
    """Find favorable electional windows based on Moon condition and benefic aspects.

    Args:
        start_date: YYYY-MM-DD (default: today)
        end_date: YYYY-MM-DD (default: 7 days from start)
        lat: Latitude (default: Orlando FL)
        lon: Longitude (default: Orlando FL)
        moon_signs: Comma-separated preferred Moon signs (optional)
    """
    try:
        criteria = {}
        if moon_signs:
            criteria["moon_signs"] = [s.strip() for s in moon_signs.split(",")]
        result = eph.elections(criteria, start_date, end_date, lat, lon)
        return json.dumps(result, indent=2)
    except Exception as ex:
        return json.dumps({"error": str(ex)})


@mcp.tool()
async def find_eclipses(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    name: Optional[str] = None,
) -> str:
    """Find upcoming solar and lunar eclipses, optionally checking natal contacts.

    Args:
        start_date: YYYY-MM-DD (default: today)
        end_date: YYYY-MM-DD (default: 1 year from start)
        name: Chart name to check natal contacts (optional)
    """
    try:
        result = eph.eclipses(start_date, end_date, name)
        return json.dumps(result, indent=2)
    except Exception as ex:
        return json.dumps({"error": str(ex)})


@mcp.tool()
async def get_exact_ingresses(
    planet: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """Get precise sign ingress times for any planet.

    Args:
        planet: Planet name (default: Moon)
        start_date: YYYY-MM-DD (default: today)
        end_date: YYYY-MM-DD (default: 30 days from start)
    """
    try:
        result = eph.exact_ingresses(planet, start_date, end_date)
        return json.dumps(result, indent=2)
    except Exception as ex:
        return json.dumps({"error": str(ex)})


@mcp.tool()
async def get_planetary_hours(
    date: Optional[str] = None,
    lat: float = 28.5383,
    lon: float = -81.3792,
) -> str:
    """Calculate planetary hours for a date at a location.

    Args:
        date: YYYY-MM-DD (default: today)
        lat: Latitude (default: Orlando FL)
        lon: Longitude (default: Orlando FL)
    """
    try:
        result = eph.planetary_hours(date, lat, lon)
        return json.dumps(result, indent=2)
    except Exception as ex:
        return json.dumps({"error": str(ex)})


# ── Auto-discover additional sweph endpoints ──

async def discover_and_register():
    """Discover additional endpoints from the sweph API and register them."""
    core_endpoints = {
        "/moon-now", "/planets-now", "/aspects-now", "/weekly-major-phase",
        "/natal-chart", "/generate-chart", "/charts", "/dignity-score",
        "/current-dignities", "/api-info", "/void-of-course-moons",
    }
    core_prefixes = ["/chart/", "/profections/", "/zr/", "/transits/"]

    try:
        data = await call_sweph("/api-info")
        endpoints = data.get("endpoints", []) if isinstance(data, dict) else []
        registered = 0

        for ep in endpoints:
            if not isinstance(ep, dict):
                continue
            path = ep.get("path", "")
            if not path or path in core_endpoints:
                continue
            if any(path.startswith(p) for p in core_prefixes):
                continue
            # Skip parameterized paths like /chart/:name
            if ":" in path:
                continue

            tool_name = f"sweph_{path.strip('/').replace('/', '_').replace('-', '_')}"
            description = ep.get("description", f"Access the {path} sweph endpoint")

            # Create closure with captured variables
            def _make_tool(p, d):
                async def _dynamic_tool() -> str:
                    result = await call_sweph(p)
                    return json.dumps(result, indent=2)
                _dynamic_tool.__name__ = tool_name
                _dynamic_tool.__doc__ = d
                return _dynamic_tool

            mcp.tool()(_make_tool(path, description))
            registered += 1
            print(f"[stella] Registered: {tool_name} → {path}", file=sys.stderr)

        print(f"[stella] {registered} dynamic endpoints registered", file=sys.stderr)
    except Exception as e:
        print(f"[stella] Endpoint discovery skipped: {e}", file=sys.stderr)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 1b: CHART STORAGE — Stella-managed chart persistence
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CHARTS_DIR = STELLA_DIR / "charts"
CHARTS_DIR.mkdir(exist_ok=True)
MEMORY_DIR = CHARTS_DIR / "memory"
MEMORY_DIR.mkdir(exist_ok=True)


def _load_local_chart(name: str) -> dict | None:
    """Load a chart from Stella's local storage."""
    path = CHARTS_DIR / f"{name.lower()}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def _save_local_chart(name: str, data: dict):
    """Save a chart to Stella's local storage."""
    path = CHARTS_DIR / f"{name.lower()}.json"
    path.write_text(json.dumps(data, indent=2))


def _list_local_charts() -> list[str]:
    """List all locally stored chart names."""
    return sorted([
        f.stem for f in CHARTS_DIR.glob("*.json")
    ])


@mcp.tool()
def store_chart(name: str, chart_data: str) -> str:
    """Store a natal chart in Stella's local storage.
    
    Use this to persist chart data that was calculated via get_natal_chart or generate_chart.
    Charts stored here survive container rebuilds and are the source of truth.
    
    Args:
        name: Name for the chart (e.g. 'buckley', 'katy')
        chart_data: JSON string of the full chart data
    """
    try:
        data = json.loads(chart_data)
    except json.JSONDecodeError:
        return "Error: chart_data must be valid JSON"
    
    _save_local_chart(name, data)
    return f"Chart '{name}' saved to Stella storage. {len(json.dumps(data))} bytes."


@mcp.tool()
def load_chart(name: str) -> str:
    """Load a natal chart from Stella's local storage.
    
    Checks Stella's local storage first, then falls back to the Helios (sweph) API.
    
    Args:
        name: Name of the chart to load
    """
    # Try local first
    data = _load_local_chart(name)
    if data:
        return json.dumps(data, indent=2)
    
    # Fall back to sweph API
    return f"Chart '{name}' not found in Stella storage. Use get_chart(name) to fetch from Helios, then store_chart() to save locally."


@mcp.tool()
def list_stored_charts() -> str:
    """List all charts stored in Stella's local storage."""
    charts = _list_local_charts()
    return json.dumps({
        "source": "stella_local",
        "count": len(charts),
        "charts": charts,
    }, indent=2)


@mcp.tool()
def delete_chart(name: str) -> str:
    """Delete a chart from Stella's local storage.
    
    Args:
        name: Name of the chart to delete
    """
    path = CHARTS_DIR / f"{name.lower()}.json"
    if path.exists():
        path.unlink()
        return f"Chart '{name}' deleted from Stella storage."
    return f"Chart '{name}' not found in Stella storage."


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 2: KNOWLEDGE GRAPH — Search & Interpretation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _knowledge_query_neo4j(
    query: str = "",
    layer: Optional[str] = None,
    trust_tier: Optional[int] = None,
    planet: Optional[str] = None,
    sign: Optional[str] = None,
    house: Optional[str] = None,
    aspect: Optional[str] = None,
    technique: Optional[str] = None,
    tradition: Optional[str] = None,
    author: Optional[str] = None,
    top: int = 5,
) -> list[dict]:
    """Internal: query Interpretation nodes from Neo4j using structural edges and filters."""
    # Build dynamic Cypher with optional MATCH clauses and WHERE filters
    match_clauses = ["MATCH (i:Interpretation)"]
    where_clauses = []
    params: dict = {"limit": top}

    # Structural edge filters
    if planet and sign:
        # Full-text search scoped to planet+sign via DESCRIBES edges
        # Build a full-text query that requires both terms
        ft_query = f"{planet.capitalize()} AND {sign.capitalize()}"
        try:
            results = neo4j_query("""
                CALL db.index.fulltext.queryNodes('interpretation_text', $ft_query) YIELD node AS i, score
                MATCH (i)-[:DESCRIBES]->(p:Planet)
                MATCH (i)-[:DESCRIBES]->(s:Sign)
                WHERE toLower(p.id) = $planet AND toLower(s.id) = $sign
                OPTIONAL MATCH (i)-[:AUTHORED_BY]->(auth:Author)
                OPTIONAL MATCH (i)-[:IN_LAYER]->(ly:Layer)
                RETURN i.text AS text, auth.name AS author, i.source_title AS title,
                       i.trust_tier AS tier, ly.id AS layer, i.tradition AS tradition,
                       i.tags AS tags, score
                ORDER BY score DESC
                LIMIT $limit
            """, ft_query=ft_query, planet=planet.lower(), sign=sign.lower(), limit=top)
            if results:
                return results
        except Exception:
            pass
        # Fallback: DESCRIBES edges + text contains
        match_clauses.append("MATCH (i)-[:DESCRIBES]->(p:Planet)")
        match_clauses.append("MATCH (i)-[:DESCRIBES]->(s:Sign)")
        where_clauses.append("toLower(p.id) = $planet AND toLower(s.id) = $sign")
        where_clauses.append("toLower(i.text) CONTAINS $sign")
        params["planet"] = planet.lower()
        params["sign"] = sign.lower()
    elif planet:
        match_clauses.append("MATCH (i)-[:DESCRIBES]->(p:Planet)")
        where_clauses.append("toLower(p.id) = $planet")
        params["planet"] = planet.lower()
    elif sign:
        match_clauses.append("MATCH (i)-[:DESCRIBES]->(s:Sign)")
        where_clauses.append("toLower(s.id) = $sign")
        params["sign"] = sign.lower()

    if house:
        match_clauses.append("MATCH (i)-[:INTERPRETS_HOUSE]->(h:House)")
        where_clauses.append("h.number = $house")
        params["house"] = int(house) if isinstance(house, str) and house.isdigit() else house

    if aspect:
        where_clauses.append("i.tags CONTAINS $aspect")
        params["aspect"] = aspect.lower()

    if layer:
        match_clauses.append("MATCH (i)-[:IN_LAYER]->(l:Layer)")
        where_clauses.append("l.id = $layer")
        params["layer"] = layer.lower()

    if trust_tier is not None:
        where_clauses.append("i.trust_tier = $trust_tier")
        params["trust_tier"] = trust_tier

    if tradition:
        where_clauses.append("i.tradition = $tradition")
        params["tradition"] = tradition.lower()

    if author:
        match_clauses.append("MATCH (i)-[:AUTHORED_BY]->(a:Author)")
        where_clauses.append("toLower(a.name) CONTAINS $author")
        params["author"] = author.lower()

    if technique:
        where_clauses.append("i.tags CONTAINS $technique")
        params["technique"] = technique.lower().replace("_", " ")

    # Free-text search via full-text index or CONTAINS fallback
    if query and not (planet or sign or house or aspect):
        # Try full-text index first; fall back to CONTAINS
        try:
            ft_cypher = "CALL db.index.fulltext.queryNodes('interpretation_text', $query) YIELD node, score "
            ft_cypher += " ".join(match_clauses[1:]).replace("(i)", "(node)").replace("i.", "node.").replace("(i)-", "(node)-") if len(match_clauses) > 1 else ""
            # Simpler approach: use full-text as primary filter
            ft_match = ["CALL db.index.fulltext.queryNodes('interpretation_text', $query) YIELD node AS i, score"]
            ft_match.extend(match_clauses[1:])
            ft_where = " AND ".join(where_clauses) if where_clauses else ""
            ft_query = " ".join(ft_match)
            if ft_where:
                ft_query += f" WHERE {ft_where}"
            ft_query += """
                OPTIONAL MATCH (i)-[:AUTHORED_BY]->(auth:Author)
                OPTIONAL MATCH (i)-[:IN_LAYER]->(ly:Layer)
                RETURN i.text AS text, auth.name AS author, i.source_title AS title,
                       i.trust_tier AS tier, ly.id AS layer, i.tradition AS tradition,
                       i.tags AS tags, score
                ORDER BY score DESC
                LIMIT $limit
            """
            params["query"] = query
            results = neo4j_query(ft_query, **params)
            if results:
                return results
        except Exception:
            pass
        # CONTAINS fallback
        where_clauses.append("toLower(i.text) CONTAINS $query_lower")
        params["query_lower"] = query.lower()

    cypher = " ".join(match_clauses)
    if where_clauses:
        cypher += " WHERE " + " AND ".join(where_clauses)
    cypher += """
        OPTIONAL MATCH (i)-[:AUTHORED_BY]->(auth:Author)
        OPTIONAL MATCH (i)-[:IN_LAYER]->(ly:Layer)
        RETURN i.text AS text, auth.name AS author, i.source_title AS title,
               i.trust_tier AS tier, ly.id AS layer, i.tradition AS tradition,
               i.tags AS tags
        ORDER BY i.trust_tier ASC
        LIMIT $limit
    """
    return neo4j_query(cypher, **params)


@mcp.tool()
def knowledge_search(
    query: str,
    layer: Optional[str] = None,
    trust_tier: Optional[int] = None,
    planet: Optional[str] = None,
    sign: Optional[str] = None,
    house: Optional[str] = None,
    aspect: Optional[str] = None,
    technique: Optional[str] = None,
    tradition: Optional[str] = None,
    author: Optional[str] = None,
    top: int = 5,
) -> str:
    """Search the astrology knowledge graph (Neo4j) with structural and text matching.

    Queries 8,900+ Interpretation nodes from 36 curated texts linked via
    INTERPRETS_PLACEMENT, INTERPRETS_HOUSE, INTERPRETS_ASPECT edges.

    Filters:
    - layer: technical | psychological | archetypal | philosophical | reference
    - trust_tier: 1 (primary) | 2 (bridge) | 3 (reference) | 4 (peripheral)
    - planet: sun, moon, mercury, venus, mars, jupiter, saturn, uranus, neptune, pluto, north_node, south_node, lot_fortune, lot_spirit
    - sign: aries through pisces
    - house: 1-12
    - aspect: conjunction, sextile, square, trine, opposition
    - technique: essential_dignities, sect, zodiacal_releasing, profections, lots, transits, synastry, houses
    - tradition: hellenistic, modern, evolutionary, archetypal, jungian, iching, stoic
    - author: filter by author name
    - top: number of results (default 5)
    """
    results = _knowledge_query_neo4j(
        query=query, layer=layer, trust_tier=trust_tier, planet=planet,
        sign=sign, house=house, aspect=aspect, technique=technique,
        tradition=tradition, author=author, top=top,
    )

    if not results:
        return "No results found."

    output_parts = [f'Results for: "{query}" (Neo4j knowledge graph)\n']

    for i, r in enumerate(results):
        tier = r.get("tier", 4)
        tier_label = TRUST_LABELS.get(tier, "?")
        lyr = (r.get("layer") or "?").upper()

        header = f"[{i+1}] [{lyr}] [{tier_label}] — {r.get('author', '?')}: {r.get('title', '?')}"

        tags = r.get("tags") or ""
        text = r.get("text", "")
        text = text[:800] + "..." if len(text) > 800 else text

        output_parts.append(header)
        if tags:
            output_parts.append(f"Tags: {tags}")
        output_parts.append(f"\n{text}\n")
        output_parts.append("─" * 60)

    return "\n".join(output_parts)


@mcp.tool()
def knowledge_search_json(
    query: str,
    layer: Optional[str] = None,
    trust_tier: Optional[int] = None,
    planet: Optional[str] = None,
    sign: Optional[str] = None,
    house: Optional[str] = None,
    technique: Optional[str] = None,
    tradition: Optional[str] = None,
    author: Optional[str] = None,
    top: int = 5,
) -> str:
    """Search the knowledge graph and return structured JSON results.

    Same parameters as knowledge_search(). Uses Neo4j graph queries.
    """
    results = _knowledge_query_neo4j(
        query=query, layer=layer, trust_tier=trust_tier, planet=planet,
        sign=sign, house=house, technique=technique,
        tradition=tradition, author=author, top=top,
    )

    output = []
    for r in results:
        tags = r.get("tags") or ""
        output.append({
            "text": r.get("text", ""),
            "author": r.get("author"),
            "title": r.get("title"),
            "layer": r.get("layer"),
            "trust_tier": r.get("tier"),
            "tradition": r.get("tradition"),
            "tags": tags,
        })

    return json.dumps(output, indent=2)


@mcp.tool()
def knowledge_stats() -> str:
    """Get statistics about the knowledge graph (Neo4j).

    Shows total interpretation nodes, distribution by layer, trust tier, author, and tradition.
    """
    count_result = neo4j_query("MATCH (i:Interpretation) RETURN count(i) AS count")
    count = count_result[0]["count"] if count_result else 0

    layers_result = neo4j_query("""
        MATCH (i:Interpretation)-[:IN_LAYER]->(l:Layer)
        RETURN l.id AS layer, count(i) AS count ORDER BY count DESC
    """)
    tiers_result = neo4j_query("""
        MATCH (i:Interpretation)
        RETURN i.trust_tier AS tier, count(i) AS count ORDER BY count DESC
    """)
    authors_result = neo4j_query("""
        MATCH (i:Interpretation)-[:AUTHORED_BY]->(a:Author)
        RETURN a.name AS author, count(i) AS count ORDER BY count DESC
    """)
    traditions_result = neo4j_query("""
        MATCH (i:Interpretation)
        WHERE i.tradition IS NOT NULL
        RETURN i.tradition AS tradition, count(i) AS count ORDER BY count DESC
    """)

    lines = [f"Astrology Knowledge Graph — {count} interpretation nodes (Neo4j)\n"]
    lines.append("By Layer:")
    for r in layers_result:
        lines.append(f"  {r['layer']}: {r['count']}")
    lines.append("\nBy Trust Tier:")
    for r in tiers_result:
        tier_label = TRUST_LABELS.get(r["tier"], "?")
        lines.append(f"  {tier_label} (tier {r['tier']}): {r['count']}")
    lines.append("\nBy Author:")
    for r in authors_result:
        lines.append(f"  {r['author']}: {r['count']}")
    lines.append("\nBy Tradition:")
    for r in traditions_result:
        lines.append(f"  {r['tradition']}: {r['count']}")
    return "\n".join(lines)


@mcp.tool()
def interpret_placement(
    planet: str,
    sign: Optional[str] = None,
    house: Optional[str] = None,
    aspect_planet: Optional[str] = None,
    aspect_type: Optional[str] = None,
) -> str:
    """Get a multi-layered interpretation for a specific astrological placement.

    Uses Neo4j structural edges (INTERPRETS_PLACEMENT, INTERPRETS_HOUSE,
    INTERPRETS_ASPECT) to find relevant interpretations across all layers.

    Args:
        planet: The planet (sun, moon, mercury, venus, mars, jupiter, saturn, uranus, neptune, pluto)
        sign: Optional zodiac sign
        house: Optional house number (1-12)
        aspect_planet: Optional second planet for aspect interpretation
        aspect_type: Optional aspect type (conjunction, sextile, square, trine, opposition)
    """
    query_parts = [planet.title()]
    if sign:
        query_parts.append(f"in {sign.title()}")
    if house:
        query_parts.append(f"in the {house}th house")
    if aspect_planet and aspect_type:
        query_parts.append(f"{aspect_type} {aspect_planet.title()}")

    query_text = " ".join(query_parts)

    layers_to_query = ["technical", "psychological", "reference", "archetypal"]
    output_parts = [f"Multi-layered interpretation: {query_text}\n"]

    for layer_name in layers_to_query:
        try:
            results = _knowledge_query_neo4j(
                planet=planet, sign=sign, house=house,
                aspect=aspect_type if aspect_planet else None,
                layer=layer_name, top=2,
            )
            if results:
                output_parts.append(f"\n{'═' * 40}")
                output_parts.append(f"[{layer_name.upper()}]")
                output_parts.append(f"{'═' * 40}")
                for r in results:
                    a = r.get("author", "?")
                    text = r.get("text", "")
                    text = text[:600] + "..." if len(text) > 600 else text
                    output_parts.append(f"\n— {a}:")
                    output_parts.append(text)
        except Exception:
            pass

    return "\n".join(output_parts)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 3: I CHING — Divination
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# King Wen sequence: KING_WEN[upper_trigram][lower_trigram] → hexagram number
# Verified against standard I Ching reference tables.
# Trigram order: 0=Qian(Heaven), 1=Dui(Lake), 2=Li(Fire), 3=Zhen(Thunder),
#                4=Xun(Wind), 5=Kan(Water), 6=Gen(Mountain), 7=Kun(Earth)
KING_WEN = [
    # Lower→  Qian  Dui   Li  Zhen  Xun   Kan  Gen   Kun
    [ 1, 10, 13, 25, 44,  6, 33, 12],   # Upper: Qian ☰ (Heaven)
    [43, 58, 49, 17, 28, 47, 31, 45],   # Upper: Dui  ☱ (Lake)
    [14, 38, 30, 21, 50, 64, 56, 35],   # Upper: Li   ☲ (Fire)
    [34, 54, 55, 51, 32, 40, 62, 16],   # Upper: Zhen ☳ (Thunder)
    [ 9, 61, 37, 42, 57, 59, 53, 20],   # Upper: Xun  ☴ (Wind)
    [ 5, 60, 63,  3, 48, 29, 39,  8],   # Upper: Kan  ☵ (Water)
    [26, 41, 22, 27, 18,  4, 52, 23],   # Upper: Gen  ☶ (Mountain)
    [11, 19, 36, 24, 46,  7, 15,  2],   # Upper: Kun  ☷ (Earth)
]

# Map binary trigram value → King Wen trigram index
# Binary = line1 + line2*2 + line3*4 (bottom-to-top)
# Trigram lines (bottom-to-top):
#   Qian(Heaven)=111=7, Dui(Lake)=110=3(?), Li(Fire)=101=5, Zhen(Thunder)=100=1
#   Xun(Wind)=011=6,    Kan(Water)=010=2,   Gen(Mountain)=001=4, Kun(Earth)=000=0
#
# Wait — Dui(Lake) bottom-to-top is yang,yang,yin → 1,1,0 → 1+2+0=3
# And Xun(Wind) bottom-to-top is yin,yang,yang → 0,1,1 → 0+2+4=6
TRIGRAM_MAP = {
    0: 7,  # 000 → Kun (Earth)       ☷
    1: 3,  # 001 → Zhen (Thunder)    ☳
    2: 5,  # 010 → Kan (Water)       ☵
    3: 1,  # 011 → Dui (Lake)        ☱
    4: 6,  # 100 → Gen (Mountain)    ☶
    5: 2,  # 101 → Li (Fire)         ☲
    6: 4,  # 110 → Xun (Wind)        ☴
    7: 0,  # 111 → Qian (Heaven)     ☰
}

TRIGRAM_NAMES = {
    0: "☰ Heaven (Qian)",
    1: "☱ Lake (Dui)",
    2: "☲ Fire (Li)",
    3: "☳ Thunder (Zhen)",
    4: "☴ Wind (Xun)",
    5: "☵ Water (Kan)",
    6: "☶ Mountain (Gen)",
    7: "☷ Earth (Kun)",
}


def _cast_coin_line():
    """Traditional three-coin method. Heads=3, Tails=2."""
    coins = [random.choice([2, 3]) for _ in range(3)]
    total = sum(coins)
    return {6: (0, True), 7: (1, False), 8: (0, False), 9: (1, True)}[total]


def _cast_yarrow_line():
    """Simplified yarrow-stalk probabilities: 6=1/16, 7=5/16, 8=7/16, 9=3/16."""
    r = random.random()
    if r < 1 / 16:
        return (0, True)     # Old Yin (6)
    elif r < 6 / 16:
        return (1, False)    # Young Yang (7)
    elif r < 13 / 16:
        return (0, False)    # Young Yin (8)
    else:
        return (1, True)     # Old Yang (9)


def _lines_to_trigram(lines):
    """Convert 3 binary lines (bottom-to-top) to a trigram index."""
    value = lines[0] + (lines[1] * 2) + (lines[2] * 4)
    return TRIGRAM_MAP[value]


def _hexagram_number(lines):
    """Given 6 binary lines (bottom-to-top), return King Wen hexagram number."""
    lower = _lines_to_trigram(lines[:3])
    upper = _lines_to_trigram(lines[3:])
    return KING_WEN[upper][lower]


@mcp.tool()
def cast_hexagram(
    question: str,
    method: str = "coins",
) -> str:
    """Cast an I Ching hexagram for divination.

    Uses traditional casting methods (coins or yarrow stalks) with authentic
    King Wen sequence. Returns primary hexagram, changing lines, and
    transformed hexagram with full interpretive text.

    Args:
        question: The question for divination
        method: 'coins' (default) or 'yarrow'
    """
    hexagrams = load_json("hexagrams.json")
    cast_fn = _cast_yarrow_line if method == "yarrow" else _cast_coin_line

    lines = []
    changing = []
    for i in range(6):
        value, is_changing = cast_fn()
        lines.append(value)
        if is_changing:
            changing.append(i)

    number = _hexagram_number(lines)

    transformed_number = None
    if changing:
        t_lines = list(lines)
        for idx in changing:
            t_lines[idx] = 1 - t_lines[idx]
        transformed_number = _hexagram_number(t_lines)

    # Build response
    result = {
        "question": question,
        "method": method,
        "primary": {
            "number": number,
            "lines": lines,
            "line_types": [
                "old yin (changing)" if lines[i] == 0 and i in changing
                else "old yang (changing)" if lines[i] == 1 and i in changing
                else "young yin" if lines[i] == 0
                else "young yang"
                for i in range(6)
            ],
        },
        "changing_lines": [i + 1 for i in changing],
    }

    # Add trigram info
    lower_tri = _lines_to_trigram(lines[:3])
    upper_tri = _lines_to_trigram(lines[3:])
    result["primary"]["lower_trigram"] = TRIGRAM_NAMES.get(lower_tri, "?")
    result["primary"]["upper_trigram"] = TRIGRAM_NAMES.get(upper_tri, "?")

    # Add hexagram data if available
    if hexagrams:
        hex_data = hexagrams.get(str(number))
        if hex_data:
            result["primary"]["name"] = hex_data.get("name", f"Hexagram {number}")
            meaning = hex_data.get("meaning", "")
            if meaning and meaning != "The wisdom of this hexagram awaits discovery in the eternal gnosis...":
                result["primary"]["meaning"] = meaning[:2000]
            result["primary"]["concepts"] = hex_data.get("concepts", [])

            # Add changing line texts if present
            if changing and "lines" in hex_data:
                result["changing_line_texts"] = {}
                for idx in changing:
                    line_key = str(idx + 1)
                    if line_key in hex_data.get("lines", {}):
                        result["changing_line_texts"][f"line_{idx+1}"] = hex_data["lines"][line_key]

        if transformed_number:
            result["transformed"] = {"number": transformed_number}
            t_data = hexagrams.get(str(transformed_number))
            if t_data:
                result["transformed"]["name"] = t_data.get("name", f"Hexagram {transformed_number}")
                t_meaning = t_data.get("meaning", "")
                if t_meaning and t_meaning != "The wisdom of this hexagram awaits discovery in the eternal gnosis...":
                    result["transformed"]["meaning"] = t_meaning[:2000]
                result["transformed"]["concepts"] = t_data.get("concepts", [])

            # Add transformed trigram info
            t_lower = _lines_to_trigram([1 - l if i in changing else l for i, l in enumerate(lines[:3])])
            t_upper = _lines_to_trigram([1 - l if (i + 3) in changing else l for i, l in enumerate(lines[3:])])
            result["transformed"]["lower_trigram"] = TRIGRAM_NAMES.get(t_lower, "?")
            result["transformed"]["upper_trigram"] = TRIGRAM_NAMES.get(t_upper, "?")

    return json.dumps(result, indent=2)


@mcp.tool()
def retrieve_wisdom(
    query: str,
    top_k: int = 5,
) -> str:
    """Search the Gnostic Book of Changes and I Ching wisdom texts.

    Searches the knowledge graph filtered to I Ching tradition for
    relevant passages from the Gnostic Book of Changes.

    Args:
        query: Search query about I Ching concepts, hexagrams, or wisdom
        top_k: Number of results to return (default 5)
    """
    results = _knowledge_query_neo4j(query=query, tradition="iching", top=top_k)

    if not results:
        return "No wisdom passages found."

    output = []
    for r in results:
        output.append({
            "text": (r.get("text") or "")[:1000],
            "source": r.get("title", "Unknown"),
            "author": r.get("author", "Unknown"),
        })

    return json.dumps(output, indent=2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 4: RESOURCES — Static Astrological Data
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.resource("astrology://zodiac-signs")
def resource_zodiac_signs() -> str:
    """Complete zodiac sign reference."""
    data = load_json("zodiac_data.json")
    return json.dumps(data, indent=2) if data else "Zodiac data not found"


@mcp.resource("astrology://planets")
def resource_planets() -> str:
    """Complete planetary reference."""
    data = load_json("planets_data.json")
    return json.dumps(data, indent=2) if data else "Planets data not found"


@mcp.resource("astrology://houses")
def resource_houses() -> str:
    """Complete house reference."""
    data = load_json("houses_data.json")
    return json.dumps(data, indent=2) if data else "Houses data not found"


@mcp.resource("astrology://aspects")
def resource_aspects() -> str:
    """Complete aspects reference."""
    data = load_json("aspects_data.json")
    return json.dumps(data, indent=2) if data else "Aspects data not found"


@mcp.resource("astrology://traditional-astrology")
def resource_traditional_astrology() -> str:
    """Traditional astrology reference: Hellenistic techniques, dignities, sect, time lords."""
    data = load_json("traditional_astrology_data.json")
    return json.dumps(data, indent=2) if data else "Traditional astrology data not found"


@mcp.resource("astrology://natal-chart")
def resource_natal_chart() -> str:
    """Chandra's natal chart data."""
    data = load_json("natal_chart_chandra.json")
    return json.dumps(data, indent=2) if data else "Natal chart data not found"


# Personal chart resources — pull from sweph API
CHART_NAMES = ["chris", "katy", "micheal", "betsy", "megan", "kelsea", "lisa"]

for _name in CHART_NAMES:
    def _make_chart_resource(chart_name):
        @mcp.resource(f"astrology://natal-chart/{chart_name}")
        async def _resource() -> str:
            try:
                data = await call_sweph(f"/chart/{chart_name}")
                return json.dumps(data, indent=2)
            except Exception as e:
                return f"Error loading chart for {chart_name}: {e}"
        _resource.__name__ = f"resource_chart_{chart_name}"
        _resource.__doc__ = f"Natal chart for {chart_name.title()}."
        return _resource
    _make_chart_resource(_name)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 5: PROMPTS — Interpretation Templates (11 total)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.prompt()
def narrative_weekly_forecast() -> str:
    """Create a narrative weekly astrological forecast weaving natal chart with current transits, expressed as an unfolding story."""
    return """Create a weekly astrological forecast in narrative form for [Date Range].
The forecast should read like a sacred beautifully written text, weaving the client's natal chart with current transits.
Do not list predictions—frame them as destiny unfolding.

## Structural Framework

### Title Format
"[Poetic Theme]: [Specific Personal Journey Reference]"
*[Date Range]*

Examples:
- "Celestial Symphony: The Eclipse at Your Partnership Gateway"
- "Cosmic Crescendo: Your Saturn Return's Final Act"
- "The Alchemical Week: Venus Dances with Your Destiny"

### Section Architecture
1. **Opening Movement - "The Cosmic Choreography/Orchestra/Stage"**
   - Begin with the week's most powerful transit/aspect
   - Connect it immediately to a specific natal placement
   - Use exact degrees and orbs
   - Frame as destiny unfolding

2. **The Major Transit Spotlight - "[Planet/Eclipse Name]: Your [Archetypal Theme]"**
   - Deep dive into the headline transit
   - Show exact aspects and orbs
   - Reveal activated houses and rulers
   - Connect to larger life narrative

3. **The Supporting Cast - "[Secondary Transit's Poetic Name]"**
   - 2-3 secondary transits
   - Show harmonies/tensions with main theme
   - Reference natal aspects
   - Build weekly "plot"

4. **The Natal Chart Callback - "Your Essential [Pattern] Illuminated"**
   - Reference natal configurations activated
   - Show fulfillment/challenge of birth promise
   - Interweave multiple natal placements

5. **The Sacred Geometry - "The Week's [Cosmic Pattern]"**
   - Identify aspect patterns (trines, T-squares, etc.)
   - Include transits + natal planets
   - Explain energetic flow

6. **The Oracle/Whisper/Declaration**
   - End with italicized cosmic guidance
   - Synthesize into poetic wisdom

## Tone & Style Guidelines
- Use sacred/mystical vocabulary ("cosmic amphitheater," "divine orchestration")
- Blend technical with poetic
- Personify planets ("Saturn whispers," "Venus demands")
- Always include: exact degrees, natal placements, orbs, house activations, rulers, timing, larger cycle context
- Favor poetic invitation over prediction
- Use second person voice and present tense
- Frame transits as revelations, journeys, thresholds, paradoxes, and echoes of natal patterns

## Content Requirements
- Exact degrees, orbs, natal placements, house activations, ruler connections
- Cycle context (retrogrades, eclipses, returns)
- Natal-transit dialogue, historical callbacks, future seeding, multivalent meanings"""


@mcp.prompt()
def interpret_traditional_chart() -> str:
    """Get a traditional astrological interpretation based on natal chart."""
    return """Please analyze my natal chart from the natal-chart resource using traditional astrological principles from the traditional-astrology resource. Focus on house rulerships in the style of Chris Brennan, with special attention to:

1. The ruler of my Ascendant and its placement
2. Planetary sect and dignity
3. Annual profections for my current age
4. Time lord techniques
5. Holistic synthesis in the style of Richard Tarnas

Please provide a thorough interpretation focusing on life direction, career, relationships, and spiritual development."""


@mcp.prompt()
def hellenistic_chart_analysis() -> str:
    """Get a Hellenistic astrology analysis of natal chart."""
    return """Please analyze my natal chart from the natal-chart resource using Hellenistic astrological techniques from the traditional-astrology resource. Focus on:

1. Whole sign house placements
2. The Ascendant ruler's condition by sign, house, dignity, and aspects
3. Sect analysis (day/night distinction)
4. Planetary joys and triplicities
5. Lots/Arabic Parts (especially Fortune and Spirit)
6. Time lord systems (annual profections and zodiacal releasing)

Provide a comprehensive reading in the style of Chris Brennan's approach to Hellenistic astrology."""


@mcp.prompt()
def archetypal_chart_analysis() -> str:
    """Get an archetypal astrology analysis of natal chart."""
    return """Please analyze my natal chart from the natal-chart resource using the archetypal astrology approach of Richard Tarnas from the traditional-astrology resource. Focus on:

1. The major planetary archetypes and their complex interactions in my chart
2. Significant aspect patterns and their archetypal meanings
3. The current transits to my natal chart and their archetypal significance
4. How these archetypal patterns might manifest in my personal life and consciousness
5. The deeper philosophical and spiritual implications of these archetypal dynamics

Provide a rich, nuanced interpretation that captures the multivalent symbolism and psychological depth of the Tarnas approach to archetypal astrology."""


@mcp.prompt()
def profection_year_analysis() -> str:
    """Get an analysis of your current annual profection."""
    return """Based on my natal chart from the natal-chart resource and traditional techniques from the traditional-astrology resource, please analyze my current annual profection year. Calculate which house and planet is activated this year based on my age, and provide a detailed interpretation of what this means for me. Include:

1. The activated house and its lord
2. The condition of that lord in my natal chart
3. Current transits to that lord and house
4. Key themes and focus areas for this profection year
5. Practical guidance for working with this year's energies

Please use the Chris Brennan approach to annual profections."""


@mcp.prompt()
def traditional_transits_analysis() -> str:
    """Get a traditional analysis of current transits to natal chart."""
    return """Please use the get-planet-positions and get-planet-aspects tools to compare current planetary positions with my natal chart from the natal-chart resource. Then provide a traditional analysis using frameworks from the traditional-astrology resource. Focus on:

1. Transits to my Ascendant ruler and its significance
2. Traditional interpretations of outer planet transits to natal positions
3. Current transits through my whole sign houses and their meanings
4. The relationship between current transits and my annual profection
5. Practical timing insights based on these traditional techniques

Please blend traditional timing techniques with practical guidance for navigating the current astrological weather."""


@mcp.prompt()
def interpret_natal_chart() -> str:
    """Get a personalized natal chart interpretation with focus on house rulership."""
    return """Please analyze my natal chart from the natal-chart resource with a focus on traditional house rulership. For each planet, analyze:

1. Its condition by sign placement (dignity, debility, mutual reception)
2. The house(s) it rules and how its condition affects those life areas
3. Its house placement and how it expresses its energy there
4. Important aspects it makes to other planets and how those modify its expression

Pay special attention to the ruler of the Ascendant as the chart ruler, and how its condition shapes my overall life direction. Include information about any mutual receptions between planets and what that signifies. Conclude with my key strengths, challenges, and potential life direction based on this traditional house rulership analysis."""


@mcp.prompt()
def analyze_current_transits() -> str:
    """Get analysis of current transits to natal chart with emphasis on house rulership."""
    return """Please use the get-planet-positions and get-planet-aspects tools to compare current planetary positions with my natal chart from the natal-chart resource. Focus your analysis on:

1. Transiting planets through natal houses and what areas of life they're activating
2. Transits to natal planets, especially rulers of important houses
3. How transiting planets in their current condition (dignity, debility, retrograde) are affecting the houses they rule in my natal chart
4. The houses currently being activated by transits to their rulers
5. Any temporary mutual receptions between transiting planets and how those might ease or complicate matters

Identify the most significant current transits based on house rulership considerations and provide practical guidance on how to work with these energies."""


@mcp.prompt()
def interpret_planets() -> str:
    """Interpret current planetary positions with house rulership analysis."""
    return """Please use the get-planet-positions and get-planet-aspects tools to analyze the current planetary positions. Then provide an astrological interpretation focusing on:

1. Each planet's current condition (sign dignity/debility, retrograde status)
2. Which houses each planet rules in a natural chart (Aries rising) and how its current condition affects those areas of life collectively
3. Current mutual receptions between planets and their significance
4. The most significant aspects between planets currently forming and how they modify planetary expressions
5. Which life areas (houses) are most supported or challenged right now based on their rulers' conditions and aspects

Provide practical guidance on how to best work with the current cosmic energies in different life domains, based on house rulership considerations."""


@mcp.prompt()
def moon_energy() -> str:
    """Explain the current moon phase and its influence with house rulership context."""
    return """Use the get-current-moon tool to check the current moon phase and sign. Then provide an analysis that includes:

1. The current lunar phase and its general meaning in the lunar cycle
2. The Moon's current sign placement, its dignity/debility status there, and any mutual receptions
3. Which house the Moon would rule (Cancer) in a natural chart and how its current condition affects those matters collectively
4. The house naturally ruled by the sign the Moon is currently in, and how the Moon's presence there affects those matters
5. Activities that are supported or challenged during this lunar phase and sign combination, with house rulership considerations
6. Practical guidance for working with today's lunar energy in different life domains"""


@mcp.prompt()
def weekly_planning() -> str:
    """Create a comprehensive weekly plan based on astrological influences including house rulership."""
    return """Create a comprehensive weekly astrological planning guide by combining multiple celestial influences including house rulership considerations. Use the following tools to gather all relevant astrological data:

1. First, check the get-weekly-moon-phase tool to find the major moon phase this week.
2. Use the void-of-course-moons tool to identify periods when the moon is void of course.
3. Review planetary-ingresses?timeframe=week to see which planets are changing signs and therefore changing their dignity/debility status and rulership effectiveness.
4. Check planetary-stations?timeframe=week to find any planets turning retrograde or direct and how that affects the houses they rule.
5. Analyze important-transits?timeframe=week to identify significant planetary aspects.

For each day of the week, provide:
- The sign and phase of the Moon, its dignity status, and which life areas (houses) are affected by its placement
- Void of course moon periods and what activities to avoid during these times
- Planets changing signs, their new dignity status, and how this affects the houses they rule
- Planets changing direction and how this impacts their ruled houses
- Major aspects forming and which houses/life areas are affected through rulership
- Practical recommendations for each day based on these combined influences

Include a section on which life areas (houses) are most activated this week based on planetary activity of their rulers, and what that means for personal planning. Present this as a practical guide that incorporates house rulership principles while remaining accessible to those with limited astrological knowledge."""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 5b: GRAPH QUERIES — Direct Neo4j knowledge traversals
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
def graph_query(
    planet: Optional[str] = None,
    sign: Optional[str] = None,
    house: Optional[int] = None,
    layer: Optional[str] = None,
    author: Optional[str] = None,
    technique: Optional[str] = None,
    limit: int = 5,
) -> str:
    """Query the Neo4j knowledge graph with structured filters. No embeddings needed.

    This is a direct graph traversal — instant results. Use for structured lookups
    like "what does Brennan say about Mars in Aries" or "all psychological
    interpretations of the 12th house."

    Args:
        planet: Planet id (sun, moon, mercury, venus, mars, jupiter, saturn, etc.)
        sign: Sign id (aries, taurus, gemini, etc.)
        house: House number (1-12)
        layer: Interpretive layer (technical, psychological, archetypal, philosophical, reference)
        author: Author name (e.g. 'Chris Brennan', 'Richard Tarnas')
        technique: Technique id (essential_dignities, sect, profections, zodiacal_releasing, etc.)
        limit: Max results (default 5)
    """
    # Build dynamic Cypher query
    matches = ["(i:Interpretation)"]
    wheres = []

    if planet:
        matches.append("(i)-[:DESCRIBES]->(p:Planet {id: $planet})")
    if sign:
        matches.append("(i)-[:DESCRIBES]->(s:Sign {id: $sign})")
    if house is not None:
        matches.append("(i)-[:DESCRIBES]->(h:House {number: $house})")
    if layer:
        matches.append("(i)-[:IN_LAYER]->(l:Layer {id: $layer})")
    if author:
        matches.append("(i)-[:AUTHORED_BY]->(a:Author {name: $author})")
    else:
        matches.append("(i)-[:AUTHORED_BY]->(a:Author)")
    if technique:
        matches.append("(i)-[:DESCRIBES]->(t:Technique {id: $technique})")

    cypher = f"""
        MATCH {', '.join(matches)}
        RETURN i.text AS text, a.name AS author, i.source_title AS title,
               i.trust_tier AS tier
        ORDER BY i.trust_tier ASC
        LIMIT $limit
    """

    params = {"limit": limit}
    if planet: params["planet"] = planet
    if sign: params["sign"] = sign
    if house is not None: params["house"] = house
    if layer: params["layer"] = layer
    if author: params["author"] = author
    if technique: params["technique"] = technique

    results = neo4j_query(cypher, **params)

    if not results:
        return "No results found for this combination."

    # Format output
    parts = [f"Found {len(results)} results:\n"]
    for i, r in enumerate(results):
        text = r["text"][:600] + "..." if len(r["text"]) > 600 else r["text"]
        parts.append(f"[{i+1}] [{r['author']}] (Tier {r['tier']})")
        parts.append(f"    {r['title']}")
        parts.append(f"    {text}\n")

    return "\n".join(parts)


@mcp.tool()
def graph_rulership_web(sign: str) -> str:
    """Get the complete rulership web for a sign from the graph.

    Returns which planet rules it, is exalted in it, in detriment, in fall,
    and the triplicity rulers. Pure graph traversal, instant.

    Args:
        sign: Sign id (aries, taurus, gemini, etc.)
    """
    results = neo4j_query("""
        MATCH (s:Sign {id: $sign})
        OPTIONAL MATCH (ruler:Planet)-[:RULES]->(s)
        OPTIONAL MATCH (exalted:Planet)-[:EXALTED_IN]->(s)
        OPTIONAL MATCH (detriment:Planet)-[:DETRIMENT_IN]->(s)
        OPTIONAL MATCH (fall:Planet)-[:FALL_IN]->(s)
        OPTIONAL MATCH (trip_day:Planet)-[:TRIPLICITY_RULER {sect: 'day'}]->(s)
        OPTIONAL MATCH (trip_night:Planet)-[:TRIPLICITY_RULER {sect: 'night'}]->(s)
        OPTIONAL MATCH (trip_part:Planet)-[:TRIPLICITY_RULER {sect: 'participating'}]->(s)
        OPTIONAL MATCH (s)-[:OF_ELEMENT]->(e:Element)
        OPTIONAL MATCH (s)-[:OF_MODALITY]->(m:Modality)
        OPTIONAL MATCH (s)-[:NATURAL_HOUSE]->(h:House)
        OPTIONAL MATCH (opp:Sign)<-[:OPPOSES]-(s)
        RETURN s.name AS sign, s.symbol AS symbol,
               e.name AS element, m.name AS modality,
               h.number AS natural_house, h.topics AS house_topics,
               ruler.name AS ruler, exalted.name AS exalted,
               collect(DISTINCT detriment.name) AS detriments,
               collect(DISTINCT fall.name) AS falls,
               trip_day.name AS triplicity_day,
               trip_night.name AS triplicity_night,
               trip_part.name AS triplicity_participating,
               opp.name AS opposite_sign
    """, sign=sign.lower())

    if not results:
        return f"Sign '{sign}' not found."

    return json.dumps(results[0], indent=2, default=str)


@mcp.tool()
def graph_planet_condition(planet: str, sign: str) -> str:
    """Get a planet's full condition in a given sign from the graph.

    Returns all dignity relationships plus relevant interpretations
    from the knowledge graph. No embeddings needed.

    Args:
        planet: Planet id (sun, moon, mercury, etc.)
        sign: Sign id (aries, taurus, etc.)
    """
    # Structural dignities
    dignities = neo4j_query("""
        MATCH (p:Planet {id: $planet})
        OPTIONAL MATCH (p)-[r:RULES]->(s:Sign {id: $sign})
        OPTIONAL MATCH (p)-[e:EXALTED_IN]->(s2:Sign {id: $sign})
        OPTIONAL MATCH (p)-[d:DETRIMENT_IN]->(s3:Sign {id: $sign})
        OPTIONAL MATCH (p)-[f:FALL_IN]->(s4:Sign {id: $sign})
        OPTIONAL MATCH (p)-[t:TRIPLICITY_RULER]->(s5:Sign {id: $sign})
        RETURN p.name AS planet, p.sect AS sect, p.type AS type,
               r IS NOT NULL AS domicile,
               e IS NOT NULL AS exaltation,
               d IS NOT NULL AS detriment,
               f IS NOT NULL AS fall,
               t IS NOT NULL AS triplicity
    """, planet=planet.lower(), sign=sign.lower())

    # Top interpretations from each layer
    interpretations = neo4j_query("""
        MATCH (i:Interpretation)-[:DESCRIBES]->(p:Planet {id: $planet}),
              (i)-[:DESCRIBES]->(s:Sign {id: $sign}),
              (i)-[:IN_LAYER]->(l:Layer),
              (i)-[:AUTHORED_BY]->(a:Author)
        RETURN l.id AS layer, a.name AS author, left(i.text, 300) AS excerpt,
               i.trust_tier AS tier
        ORDER BY l.id, i.trust_tier ASC
        LIMIT 10
    """, planet=planet.lower(), sign=sign.lower())

    output = {
        "condition": dignities[0] if dignities else {},
        "interpretations_by_layer": {},
    }

    for interp in interpretations:
        layer = interp["layer"]
        if layer not in output["interpretations_by_layer"]:
            output["interpretations_by_layer"][layer] = []
        output["interpretations_by_layer"][layer].append({
            "author": interp["author"],
            "excerpt": interp["excerpt"],
            "tier": interp["tier"],
        })

    return json.dumps(output, indent=2)


@mcp.tool()
def graph_stats() -> str:
    """Get statistics about the Neo4j knowledge graph."""
    stats = {}

    counts = neo4j_query("""
        MATCH (i:Interpretation) WITH count(i) AS interps
        MATCH (p:Planet) WITH interps, count(p) AS planets
        MATCH (s:Sign) WITH interps, planets, count(s) AS signs
        MATCH (h:House) WITH interps, planets, signs, count(h) AS houses
        MATCH (a:Author) WITH interps, planets, signs, houses, count(a) AS authors
        MATCH ()-[r:DESCRIBES]->() WITH interps, planets, signs, houses, authors, count(r) AS describes
        MATCH ()-[r2:RULES]->() WITH interps, planets, signs, houses, authors, describes, count(r2) AS rules
        RETURN interps, planets, signs, houses, authors, describes, rules
    """)

    if counts:
        c = counts[0]
        stats = {
            "interpretations": c["interps"],
            "planets": c["planets"],
            "signs": c["signs"],
            "houses": c["houses"],
            "authors": c["authors"],
            "describes_relationships": c["describes"],
            "rules_relationships": c["rules"],
        }

    # Author breakdown
    authors = neo4j_query("""
        MATCH (i:Interpretation)-[:AUTHORED_BY]->(a:Author)
        RETURN a.name AS author, count(i) AS chunks
        ORDER BY chunks DESC
    """)
    stats["authors_detail"] = {a["author"]: a["chunks"] for a in authors}

    # Layer breakdown
    layers = neo4j_query("""
        MATCH (i:Interpretation)-[:IN_LAYER]->(l:Layer)
        RETURN l.id AS layer, count(i) AS chunks
        ORDER BY chunks DESC
    """)
    stats["layers"] = {l["layer"]: l["chunks"] for l in layers}

    return json.dumps(stats, indent=2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 6: CHART READING — Full Computation + Knowledge-Grounded Narrative
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# The chart reading pipeline:
#   1. full_chart_computation(name) — gathers ALL data from Helios into one payload
#   2. _gather_knowledge(chart_data) — queries knowledge graph for every placement
#   3. chart_reading(name, size, perspective) — returns computation + knowledge + narrative prompt
#
# The LLM receives everything it needs to write the interpretation.
# Stella provides data + sources + guidelines. The LLM synthesizes.


# ── Size definitions ──

CHART_SIZES = {
    "xs": {
        "label": "XS — The Glance",
        "target_length": "3-5 sentences",
        "depth": """Distilled portrait. Every lens touched in a phrase or sentence.
Who this person is at their core, their dominant strength, their central tension,
where they are right now in life. Like a therapist's first-session impression.
No astrology language — pure human insight, compressed to its essence.

CLOSING: End with ONE quote from the knowledge graph (only if it specifically
supports the reading) OR one composed aphorism. Not both.""",
        "knowledge_results": 1,  # per query
    },
    "s": {
        "label": "S — Key Themes",
        "target_length": "2-3 paragraphs",
        "depth": """Portrait plus the 2-3 most dominant life themes fleshed out.
What drives this person, what holds them back, how they relate to others.
The central psychological tension and the primary coping strategy.
Where they are in their life's arc right now and why it matters.
Written as insight, not analysis. Like a letter from someone who understands.

CLOSING: End with ONE quote from the knowledge graph (only if directly
relevant) OR one composed aphorism. Not both.""",
        "knowledge_results": 2,
    },
    "m": {
        "label": "M — Working Reading",
        "target_length": "1-2 pages",
        "depth": """All interpretive lenses addressed with moderate depth.

NARRATIVE RULES:
- Write in SECOND PERSON ("you may find..." not "she is...")
- NO astro jargon in the narrative — pure human experience language
- Use INVITATIONAL language: "suggests," "may," "the potential here is"
- Rigorous technique → illuminated possibility → space for agency
- Technical summary goes in APPENDIX at end, not in narrative
- Include outer planet archetypes as psychological themes (for Psychological framework)

CONTENT:
How you present to the world vs. who you are inside. Emotional patterns —
what feels safe, what triggers defense, how you process experience.
What you attract in relationships and why. How early life shaped coping.
Natural gifts and where you overcompensate. How motivation and purpose
flow through life. The current chapter and what it's asking of you.

Written as a continuous narrative — warm, direct, invitational.
Knowledge graph material absorbed and synthesized, never cited as astrology.

SECTION QUOTES: 1-2 key sections get ONE quote. End with one that captures the whole. Restraint.""",
        "knowledge_results": 3,
    },
    "l": {
        "label": "L — Full Narrative",
        "target_length": "3-5 pages",
        "depth": """Full narrative interpretation across all lenses.

NARRATIVE RULES:
- Write in SECOND PERSON ("you may find..." not "she is...")
- NO astro jargon in the narrative — pure human experience language
- Use INVITATIONAL language: "suggests," "may," "the potential here is"
- Rigorous technique → illuminated possibility → space for agency
- Technical summary goes in APPENDIX at end
- Include outer planet archetypes as psychological themes (for Psychological framework)

CONTENT:
How the face you show the world differs from who you are when alone.
The emotional interior — how you take in experience, what soothes you,
what overwhelms you. What you attract in relationships and why — the
feedback loop between self and other. How early life conditions shaped
coping strategies, attachment patterns, and sense of safety. What operates
below awareness — patterns you can't see but others can.

Strengths described not as gifts but as *developed capacities* — things
built through effort. Challenges described not as flaws but as friction
points where growth is available. The internal logic of how motivation,
energy, and purpose flow through life.

Psychological frameworks woven throughout: attachment theory, Jungian
individuation, shadow work, internal family systems, developmental stages.
The current life chapter given biographical weight — where have you been,
where are you now, what's being asked of you.

SECTION QUOTES: 2-3 total across the whole reading. Restraint over decoration.""",
        "knowledge_results": 4,
    },
    "xl": {
        "label": "XL — The Deep Dive",
        "target_length": "5-10+ pages",
        "depth": """Exhaustive meaning-making. The full operating system of a person.

Every lens explored in full depth, expressed entirely as human experience:

- The face and the interior: How the identity they project interacts with
  who they actually feel themselves to be. Where these align, where they
  create tension, where one compensates for the other.
- The emotional body: How this person receives and processes experience.
  What feels safe. What triggers defense. What they do with difficult
  feelings — intellectualize, somatize, project, suppress, act out.
  The attachment style implied by their emotional patterning.
- The mirror: What this person attracts in others. What gets projected
  outward. The feedback loop between how they see themselves and how
  the world reflects them back. Relationship patterns.
- Formative imprints: What childhood and early family conditions likely
  shaped their coping strategies. Not deterministic — but the soil the
  seed grew in. The internalized parent. The wound that became a skill.
- The conscious and the unconscious: What this person manages deliberately
  vs. what operates below awareness. The blind spots. The shadow material.
  What they've exiled from identity that still runs the show.
- Private and public: Where the weight of their life falls — inward builder
  or outward performer? Where do they invest energy that nobody sees?
- Strengths and overcompensation: Natural capacities — and the places
  where strength becomes rigidity, where a gift gets overused because
  the alternative feels too vulnerable.
- The internal economy: How motivation, energy, and purpose flow through
  their life. Where it pools (obsession, hyperfocus). Where it leaks
  (avoidance, scattered attention, chronic depletion).
- The current chapter: Where are they in the larger arc? What season of
  life is this? What's ending, what's beginning, what's being demanded?

The knowledge graph provides the scholarly depth. Absorb it completely.
Express it as human truth. The reader should feel *seen* — not analyzed.

Actionable synthesis: What does this person need to understand about
themselves right now? Where are the growth edges? What's the invitation?
What would a wise friend who could see everything say to them?

SECTION QUOTES — EXPLICIT RULES:
Each section gets at most ONE of these two options. Never both. Many sections
may get neither — only use one when it truly earns its place.

OPTION A — OPENING QUOTE: A direct quote from the knowledge graph excerpts
that SPECIFICALLY supports the narrative that follows. It must be directly
relevant to the content of THAT section — not decorative, not thematic,
not loosely related. If no knowledge graph passage specifically supports
the section's content, DO NOT force one. Place at the TOP, italicized,
attributed. The quote earns its place by illuminating what comes next.

OPTION B — CLOSING APHORISM: A composed one-sentence aphorism at the END
of the section. In the spirit of the Stoics, Jung, or Alan Watts. Must be
specific to THIS section's insight — never generic wisdom. Only use when
the section earns a closing that crystallizes its meaning.

Most sections should use ONE or NEITHER. Never both. A reading with 3-4
quotes/aphorisms total is better than one with 9. Restraint is the rule.""",
        "knowledge_results": 5,
    },
}


# ── Perspectives ──

# ── Report Types (the medium — HOW the reading is delivered) ──
# Named after Venus — the planet of art, beauty, and form.

REPORT_TYPES = {
    "technical": {
        "label": "Technical",
        "description": "Data-forward. Astrological language preserved. For practitioners.",
        "instructions": """REPORT TYPE: TECHNICAL
This reading is for someone who KNOWS astrology. Use proper terminology:
planet names, sign placements, house numbers, aspect names, dignity scores.

Structure: Lead with data, follow with interpretation.
For each major placement, give: position → dignity → aspects → interpretation.
Include the derivative house relationships explicitly.
Knowledge graph citations welcome — name authors and traditions.

The math goes in the body. The appendix contains raw computation tables.

Voice: Precise, authoritative, collegial. Like a senior astrologer presenting
to peers. Show your work.""",
    },
    "narrative": {
        "label": "Narrative",
        "description": "Human-first portrait. No jargon. Math in appendix only.",
        "instructions": """REPORT TYPE: NARRATIVE
This reading is for a HUMAN who may not know astrology. Translate everything
into lived experience, psychology, and felt human reality.

- Do NOT name planets, signs, houses, or aspects in the narrative body.
- "You lead with analytical precision and a restless need to solve things"
  rather than "Mercury in Aries in the 8th."
- The astrological data is your SOURCE MATERIAL, not your output.
- Like a doctor who reads bloodwork but tells the patient "you need more rest"
  — not "your cortisol is 22 µg/dL."
- Knowledge graph insights absorbed and expressed in everyday language.

The narrative is the reading. A technical appendix follows with all
astrological data, dignities, and computation results for those who want it.

Voice: Warm, direct, insightful. Like a brilliant therapist who also happens
to understand your whole life structure. Speak to the person. Second person.""",
    },
    "poem": {
        "label": "Poem",
        "description": "Artistic distillation. Verse or lyric prose. Math in appendix.",
        "instructions": """REPORT TYPE: POEM
Distill the chart into verse, lyric prose, or mythological narrative.
The chart becomes a story, a myth, a prayer, a letter from the cosmos.

No astrological jargon in the poem itself. The images carry the meaning.
Mars exalted in the 5th becomes "a warrior who builds cathedrals from play."
Moon in Aquarius in the 6th becomes "feelings that arrive as equations,
the heart's algebra computed through the body's honest labor."

Structure options (choose what fits the chart):
- Free verse poem with stanzas for each life domain
- A mythological narrative (the hero's journey of this chart)
- A letter addressed to the person from their chart itself
- A series of short lyrics, each capturing a placement

A technical appendix follows with full computation data.

Voice: Evocative, precise in its images, emotionally resonant.
Beauty is not decoration — it's compression of truth.""",
    },
}


# ── Frameworks (the lens — WHAT interpretive tradition shapes the reading) ──
# Named after Mercury — the planet of thought, interpretation, and meaning-making.

## ── Baseline ──
# Hellenistic + Whole Sign Houses is the backbone of ALL readings.
# Sect, dignity, lots, depositors, timing techniques. This isn't a framework
# choice — it's how we do astrology. All frameworks layer ON TOP of this.

FRAMEWORKS = {
    "psychological": {
        "label": "Psychological",
        "description": "Modern depth psychology. Attachment, shadow, individuation. Outer planet archetypes.",
        "instructions": """FRAMEWORK: PSYCHOLOGICAL (NON-FATALIST, NON-DETERMINISTIC)

BASELINE: Hellenistic techniques (sect, dignity, depositors, lots, timing) provide
the rigorous foundation. This framework layers psychological interpretation on top.

The chart describes archetypal fields of POTENTIAL, not fixed outcomes.
Write in SECOND PERSON ("you may find..." not "she is...").
Use INVITATIONAL language: "suggests," "may," "the potential here is," "you might notice."
The math gives moderate certainty about where potential lives.
The narrative offers that potential as an invitation to recognize — not a verdict.

Use psychological frameworks as the language:
- Attachment theory (secure, anxious, avoidant, disorganized patterns)
- Jungian individuation and shadow work
- Internal Family Systems (exiles, managers, firefighters)
- Developmental psychology and formative imprints
- Defense mechanisms and coping strategies

INCLUDE OUTER PLANET ARCHETYPES (Uranus, Neptune, Pluto):
Weave their themes as psychological patterns, not astro terms.
- Pluto: transformation, power dynamics, depth, intensity
- Neptune: idealization, confusion, transcendence, dissolution of boundaries
- Uranus: disruption, innovation, unconventional patterns, sudden insight

KEY INTERPRETATION RULE: Dignity score drives narrative weight more than ASC archetype.
Lead with the STRONGEST planet's lived experience, not ASC cookbook.

NARRATIVE RULES:
- NO astro jargon in the narrative (save for Technical appendix)
- Pure human experience language
- Rigorous technique → illuminated possibility → space for agency""",
    },
    "deterministic": {
        "label": "Deterministic (GTEI)",
        "description": "Necessitated unfolding through Absolute Self-Consistency.",
        "instructions": """FRAMEWORK: DETERMINISTIC (GTEI)

BASELINE: Hellenistic techniques provide the rigorous foundation.

The chart is a necessitated expression of Absolute Self-Consistency (ASC).
Every placement is the only possible configuration — the singular,
self-consistent solution to this person's coherence equation.

Analyze through the 5 Primordial Categories:
- Distinction/Unity: This individual chart within the collective
- Relation/Separation: Aspects and house relationships as necessitated connections
- Potentiality/Actuality: Natal chart as potential, timing as actualization
- Quantity/Quality: Dignities (quantitative) yielding qualitative expression
- Process/State: Timing techniques as process, natal positions as state

"Free will" is reinterpreted as self-generated determinism — the maximally
coherent pathway from this person's internal potentials.

End with a human-readable synthesis and one coherence-aiding question.""",
    },
    "ki": {
        "label": "9 Star Ki",
        "description": "Ki elemental cycles: Essence, Emotion, Life Path.",
        "instructions": """FRAMEWORK: 9 STAR KI

BASELINE: Can integrate with natal chart or stand alone.

The three Ki numbers reveal:

1ST NUMBER (ESSENCE): The iceberg below the water — invisible to self.
Governs the parts of ourselves we can't see. Works in conjunction with
natal chart hidden elements. What operates beneath conscious awareness.

2ND NUMBER (EMOTION): Internal processing, the heart, qualities/abilities,
strengths/weaknesses, potential trauma triggers. Under stress, we resort
to the SHADOW QUALITIES of this number. Connects to Moon themes.

3RD NUMBER (LIFE PATH): How people see you externally + contextualizes
the nodes, career, societal roles, larger lessons. The mirror we must
see through on our journey. Connects to nodal story and career arc.

ELEMENTAL RELATIONSHIPS:
- Productive cycle: Wood → Fire → Earth → Metal → Water → Wood
- Controlling cycle: Wood → Earth → Water → Fire → Metal → Wood

Integrate Ki with natal chart themes where applicable.
Use invitational language for the Psychological aspects.""",
    },
    "zr": {
        "label": "Zodiacal Releasing",
        "description": "Life chapters, peak periods, timing. Vettius Valens lineage.",
        "instructions": """FRAMEWORK: ZODIACAL RELEASING

BASELINE: Hellenistic techniques provide the rigorous foundation.
ZR is a timing technique from Vettius Valens' Anthology.

Interpret through the lens of LIFE CHAPTERS:
- L1 periods: Major life chapters (years to decades)
- L2 periods: Sub-chapters within L1
- Peak periods: Signs angular from Lot of Fortune (1st/10th = Major, 7th = Moderate, 4th = Minor)
  indicate heightened activity and manifestation. Peaks are ALWAYS from Fortune.
- Loosing of the bond: Transition points, pivots, unexpected shifts

NON-DETERMINISTIC REFRAME:
- Peak periods = windows of momentum, not guaranteed success
- Malefic periods = growth edges, not doom
- Loosing of the bond = pivot points, not fate's interruption
- Sect malefic activation = where your work is, not where you lose

ZR as navigation tool, not fortune-telling. Timing precision + agency of response.

Voice: Grounded in tradition but emphasizing choice within timing.""",
    },
    "stoic": {
        "label": "Stoic",
        "description": "Virtue, fate, and the discipline of assent. Marcus Aurelius meets the chart.",
        "instructions": """FRAMEWORK: STOIC

BASELINE: Hellenistic techniques provide the rigorous foundation.

Read the chart through Stoic philosophy. What is "up to us" (prohairesis)
and what is not? The chart shows both the given conditions (fate, heimarmenē)
and the capacity for virtue within those conditions.

For each placement, distinguish:
- What is given (the placement, the condition, the circumstances)
- What is available (the virtue, the response, the discipline)
- Where the person's ruling faculty (hēgemonikon) is strongest/weakest

Use Stoic frameworks: the dichotomy of control, the discipline of assent,
the discipline of desire, the discipline of action. Preferred and
dispreferred indifferents. The view from above.

Quote the Stoics where fitting: Marcus Aurelius, Epictetus, Seneca.
The chart is not a cage — it's the specific arena in which virtue is practiced.

Voice: Measured, clear-eyed, grounding. Like Meditations written for one person.

NOTE: Knowledge base needs more Stoic texts for full support.""",
    },
    "wuxing": {
        "label": "Wu Xing (五行)",
        "description": "Five Elements cosmology. Planets as elemental embodiments. Generating/overcoming cycles.",
        "instructions": """FRAMEWORK: WU XING (五行 — FIVE MOVEMENTS)

BASELINE: Hellenistic techniques (sect, dignity, depositors, lots, timing) provide
the rigorous foundation. Wu Xing layers elemental cosmology on top.

The five visible planets ARE the Five Elements made manifest in the sky:
- Mercury = Water (水 Shuǐ) — Kidneys/Bladder — Fear↔Willpower — Wisdom
- Venus = Metal (金 Jīn) — Lungs/Large Intestine — Grief↔Righteousness — Integrity
- Mars = Fire (火 Huǒ) — Heart/Small Intestine — Agitation↔Joy — Propriety
- Jupiter = Wood (木 Mù) — Liver/Gallbladder — Frustration↔Kindness — Benevolence
- Saturn = Earth (土 Tǔ) — Spleen/Stomach — Worry↔Trust — Faithfulness

TWO CORE CYCLES:
Generating (相生) — Mother feeds Child:
  Wood→Fire→Earth→Metal→Water→Wood
Overcoming (相克) — Controller checks Controlled:
  Wood→Earth→Water→Fire→Metal→Wood

7-STEP METHOD:
1. Map planets to elements (Mercury=Water, Venus=Metal, Mars=Fire, Jupiter=Wood, Saturn=Earth)
2. Assess elemental dominance — which elements are concentrated by dignity/angularity?
   That element's wisdom AND challenge define core themes.
3. Identify MISSING elements — absence reveals growth edges and constitutional vulnerabilities.
4. Read elemental interactions between planets — generating = support,
   overcoming = productive tension, weakening = depletion.
5. Apply directional/seasonal axis — angular planets carry directional meaning.
6. Body-mind-emotion matrix — for each dominant element: organs, challenging emotion,
   wisdom emotion, virtue being cultivated.
7. Transit reading — apply generating/overcoming logic to transiting planets over natal.
   Jupiter (Wood) transit to natal Mars (Fire) generates — expansion fuels drive.
   Saturn (Earth) transit to natal Mercury (Water) overcomes — structure dams flow.

NARRATIVE RULES:
- Use the DUAL EMOTION for each element (challenge + wisdom as two faces of the same energy)
- Organ systems are diagnostic, not decorative — they map to real somatic patterns
- The virtue is the developmental trajectory, not a given
- Missing elements are as important as dominant ones
- Integrate with dignity scores: a planet in domicile embodies its element's WISDOM emotion;
  a planet in detriment tends toward the CHALLENGE emotion
- Voice: embodied, precise, integrative. Clinical clarity with elemental poetry.""",
    },
}

# Legacy compatibility — PERSPECTIVES maps to the new FRAMEWORKS
PERSPECTIVES = {k: v["instructions"] for k, v in FRAMEWORKS.items()}


# ── Add-ons ──
# Supplemental sections that can be appended to any report.
# One round of selection — pick any/all, then generate.
# If a framework was already selected (e.g., ZR framework), don't show it as add-on.

ADD_ONS = {
    "zr": {
        "label": "+ZR",
        "description": "Zodiacal Releasing timing section (L1/L2 chapters, peak periods)",
    },
    "transits": {
        "label": "+Transits",
        "description": "Current transits to natal chart",
    },
    "ki": {
        "label": "+Ki",
        "description": "9 Star Ki cycle section (current personal year/month)",
    },
    "wuxing": {
        "label": "+Wu Xing",
        "description": "Five Elements analysis (elemental dominance, missing elements, generating/overcoming cycles, body-mind-emotion matrix)",
    },
}


# ── Chart Reading Workflow ──
# This is the canonical workflow for generating chart readings.
# Follow these steps IN ORDER. Do not skip or reorder.

WORKFLOW_PROMPT = """
## Chart Reading Workflow

### Baseline (Always Present)
Hellenistic + Whole Sign Houses — the backbone of all readings. Sect, dignity, lots, depositors, timing techniques. This isn't a framework choice — it's how we do astrology. All frameworks layer ON TOP of this.

### Step 1: Chart Selection
Ask: "Which chart? (name one from the list, or say 'new' to create one)"
If new → collect: Name, Date (YYYY-MM-DD), Time (HH:MM), Location

### Step 2: Type (output format)
Ask: "What type of reading?"
- Technical — math first, full astrological architecture, astro jargon fine
- Narrative — portrait first, NO astro jargon in prose, math as appendix
- Poem — pure poetry in body (NO jargon), symbolism only, appendix with technical
- Ki — pure 9 Star Ki + I Ching, trigrams, hexagrams, elemental cycles

### Step 3: Framework (interpretive lens)
**ALWAYS ask this step, regardless of type.** Frameworks apply to ALL types.
Ask: "Which framework(s)? You can pick multiple."
- Psychological — attachment, shadow, IFS, developmental, non-deterministic
- GTEI — Absolute Self-Consistency, 5 Primordial Categories, deterministic
- Ki — blend Ki pattern INTO interpretation (Essence→identity, Emotion→Moon, Life Path→nodes)
- ZR — Zodiacal Releasing as primary timing lens
- Stoic — virtue, fate, dichotomy of control

### Step 4: Size
Ask: "What size?"
- XS — 3-5 sentences
- S — 2-3 paragraphs
- M — 1-2 pages
- L — 3-5 pages
- XL — 5-10+ pages

### Step 5: Add-ons
Ask: "Any add-ons? (ZR section, Transits, Ki cycle) Or ready to generate?"
Don't offer an add-on if it's already selected as framework.

### Step 6: Generate
Confirm the full spec, then generate.

### Rules
1. No astro jargon in Narrative/Poem body — pure psychology, behavior, felt experience
2. Non-deterministic language (unless GTEI) — "may," "likely," "suggests"
3. Second person — "you" not "they"
4. Technical appendix at END (except for Technical type)
5. Each reading must be unique — NO recycling phrases or structures
6. Dignity score drives narrative weight more than ASC archetype
"""


# ── Whole Sign Houses ──
# Stella uses whole sign houses natively. The ASC sign = 1st house,
# each subsequent sign = next house. One sign per house. No interceptions.
# Planet house placement is determined by sign alone.
# Helios provides planetary longitudes and the ASC degree. Stella computes
# the houses. Helios's Placidus house cusps are discarded.

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
SIGN_RULERS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}

# ── Derivative Houses ──
# Counting from one house to another reveals how life areas relate.
# The derivative number = (source_house - target_house) % 12 + 1

DERIVATIVE_HOUSES = {
    1: "identity, self, vitality",
    2: "resources, values, sustenance",
    3: "communication, siblings, local environment",
    4: "foundations, home, roots, endings",
    5: "creativity, pleasure, children, joy",
    6: "service, health, daily work, adversity",
    7: "partnership, the other, open enemies",
    8: "shared resources, transformation, death",
    9: "philosophy, travel, higher learning, faith",
    10: "career, reputation, public role, authority",
    11: "friends, aspirations, community, hopes",
    12: "isolation, hidden matters, self-undoing, transcendence",
}

ASPECT_GEOMETRY = {
    1: {"type": "conjunction", "quality": "fusion, identity"},
    2: {"type": "semisextile", "quality": "adjustment, resource exchange", "pairs": [(2, 12)]},
    3: {"type": "sextile", "quality": "opportunity, communication", "pairs": [(3, 11)]},
    4: {"type": "square", "quality": "tension, action required", "pairs": [(4, 10)]},
    5: {"type": "trine", "quality": "flow, natural harmony", "pairs": [(5, 9)]},
    6: {"type": "quincunx", "quality": "crisis, forced adaptation", "pairs": [(6, 8)]},
    7: {"type": "opposition", "quality": "polarity, awareness through other", "pairs": [(7, 7)]},
}

ANGULAR_HOUSES = {1, 4, 7, 10}


def _sign_index(sign: str) -> int:
    """Return 0-11 index for a zodiac sign."""
    return SIGNS.index(sign)


def _whole_sign_house(planet_sign: str, asc_sign: str) -> int:
    """Which whole sign house (1-12) does a planet occupy?"""
    return ((_sign_index(planet_sign) - _sign_index(asc_sign)) % 12) + 1


def _apply_whole_sign_houses(chart: dict) -> dict:
    """Compute whole sign houses from ASC sign and assign planet houses.

    This is not a conversion — it is the primary house calculation.
    Helios provides longitudes and ASC. Stella computes houses.
    """
    # Determine ASC sign
    asc_sign = None
    angles = chart.get("angles", {})
    if isinstance(angles, dict):
        asc_sign = angles.get("ascendant", {}).get("sign")
    if not asc_sign:
        # Fallback: first house from Helios (always the ASC sign)
        houses = chart.get("houses", [])
        if houses:
            asc_sign = houses[0].get("sign")
    if not asc_sign:
        return chart  # Cannot compute without ASC

    asc_idx = _sign_index(asc_sign)

    # Build the 12 whole sign houses
    chart["houses"] = [
        {
            "house": i + 1,
            "sign": SIGNS[(asc_idx + i) % 12],
            "ruler": SIGN_RULERS[SIGNS[(asc_idx + i) % 12]],
        }
        for i in range(12)
    ]
    chart["house_system"] = "whole_sign"

    # Assign planet houses from sign
    for p in chart.get("planets", []):
        p_sign = p.get("sign")
        if p_sign and p_sign in SIGNS:
            p["house"] = _whole_sign_house(p_sign, asc_sign)

    return chart


def compute_derivative_houses(chart_data: dict) -> dict:
    """Compute derivative house relationships for every planet in the chart.

    For each planet in house H, calculates what every other house "is" from
    that planet's perspective. E.g., if Mars is in house 3, house 7 is the
    5th from Mars (creativity/joy of communication).

    Groups results by aspect geometry (sextile, square, trine, etc.) and
    identifies key connections where dignified planets link to angular houses.

    Args:
        chart_data: Chart dict with whole sign houses and planet placements.

    Returns:
        Dict with planet_relationships, aspect_groups, and key_connections.
    """
    planets = chart_data.get("planets", [])
    houses = chart_data.get("houses", [])
    if not planets or not houses:
        return {"planet_relationships": {}, "aspect_groups": {}, "key_connections": []}

    # Build house lookup: house_number -> house info
    house_lookup = {h["house"]: h for h in houses}

    planet_relationships = {}
    all_connections = []  # flat list for grouping

    for p in planets:
        pname = p.get("name", "")
        p_house = p.get("house")
        if not p_house or not pname:
            continue
        p_house = int(p_house)

        relationships = []
        for x in range(1, 13):
            # Clockwise counting (Pelletier): from planet's house DOWN to target
            # E.g., H=6, X=2: (6-2)%12+1 = 5 → house 2 is the 5th from house 6
            # E.g., H=2, X=6: (2-6)%12+1 = 9 → house 6 is the 9th from house 2
            derivative_num = (p_house - x) % 12 + 1

            # Minimum arc distance for aspect geometry mapping
            forward = (x - p_house) % 12  # 0 = same house
            if forward > 6:
                forward = 12 - forward
            geo_key = forward + 1  # 1=conjunction, 2=semisextile, ..., 7=opposition

            geo = ASPECT_GEOMETRY.get(geo_key, {})
            house_info = house_lookup.get(x, {})

            conn = {
                "house": x,
                "house_sign": house_info.get("sign", ""),
                "house_ruler": house_info.get("ruler", ""),
                "derivative_number": derivative_num,
                "derivative_meaning": DERIVATIVE_HOUSES.get(derivative_num, ""),
                "aspect_type": geo.get("type", ""),
                "aspect_quality": geo.get("quality", ""),
            }
            relationships.append(conn)
            all_connections.append({
                "planet": pname,
                "planet_house": p_house,
                **conn,
            })

        planet_relationships[pname] = {
            "house": p_house,
            "sign": p.get("sign", ""),
            "connections": relationships,
        }

    # Group by aspect geometry
    aspect_groups = {}
    for geo_key, geo_info in ASPECT_GEOMETRY.items():
        asp_type = geo_info["type"]
        matching = [c for c in all_connections if c["aspect_type"] == asp_type]
        if matching:
            aspect_groups[asp_type] = {
                "quality": geo_info["quality"],
                "connections": matching,
            }

    # Identify key connections: dignified planets linking to angular houses
    key_connections = []
    # Check dignity info if available on planet objects
    for c in all_connections:
        target_house = c["house"]
        is_angular = target_house in ANGULAR_HOUSES
        if not is_angular:
            continue

        # Find the planet data
        planet_data = next((p for p in planets if p.get("name") == c["planet"]), None)
        if not planet_data:
            continue

        # Check for dignity markers (set by dignity computation)
        dignity = planet_data.get("dignity", {})
        is_dignified = False
        if isinstance(dignity, dict):
            is_dignified = dignity.get("domicile") or dignity.get("exaltation")
        elif isinstance(dignity, str):
            is_dignified = dignity.lower() in ("domicile", "exaltation")

        # Also flag any traditional planet connecting to an angle via trine/sextile
        is_traditional = c["planet"] in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")
        is_harmonious = c["aspect_type"] in ("trine", "sextile")

        if is_dignified or (is_traditional and is_harmonious):
            key_connections.append({
                **c,
                "significance": "dignified planet to angle" if is_dignified
                    else f"traditional planet {c['aspect_type']} to angular house {target_house}",
            })

    return {
        "planet_relationships": planet_relationships,
        "aspect_groups": aspect_groups,
        "key_connections": key_connections,
    }


def _normalize_legacy_chart(data: dict) -> dict:
    """Convert legacy chart format (dict-keyed planets, string angles) to Helios format.

    Legacy format has planets as {name: {sign, house, position, ...}}.
    Helios format has planets as [{name, sign, house, longitude, ...}].
    """
    normalized = dict(data)

    # ── Normalize planets from dict to list ──
    planets_raw = data.get("planets", {})
    if isinstance(planets_raw, dict):
        PLANET_NAME_MAP = {
            "sun": "Sun", "moon": "Moon", "mercury": "Mercury",
            "venus": "Venus", "mars": "Mars", "jupiter": "Jupiter",
            "saturn": "Saturn", "uranus": "Uranus", "neptune": "Neptune",
            "pluto": "Pluto", "chiron": "Chiron",
            "northNode": "North Node", "north_node": "North Node",
            "southNode": "South Node", "south_node": "South Node",
        }
        planet_list = []
        for key, pdata in planets_raw.items():
            if not isinstance(pdata, dict):
                continue
            name_clean = PLANET_NAME_MAP.get(key, key.capitalize())
            # Parse degree from position string like "27°Sg01'11''"
            pos = pdata.get("position", "")
            degree_str = ""
            try:
                degree_str = pos.split("°")[0]
                deg_num = float(degree_str)
            except (ValueError, IndexError):
                deg_num = 0.0

            planet_list.append({
                "name": name_clean,
                "sign": pdata.get("sign", ""),
                "house": pdata.get("house"),
                "degreeInSign": str(round(deg_num, 2)),
                "isRetrograde": pdata.get("isRetrograde", False),
            })
        normalized["planets"] = planet_list

    # ── Normalize angles from string format ──
    chart_angles = data.get("chartAngles", {})
    if chart_angles and "angles" not in data:
        SIGN_ABBREVS = {
            "Ar": "Aries", "Ta": "Taurus", "Ge": "Gemini", "Cn": "Cancer",
            "Le": "Leo", "Vi": "Virgo", "Li": "Libra", "Sc": "Scorpio",
            "Sg": "Sagittarius", "Cp": "Capricorn", "Aq": "Aquarius", "Pi": "Pisces",
        }

        def _parse_angle(s):
            """Parse '09°Le46'22''' into {sign, degreeInSign}."""
            if not s:
                return {}
            try:
                parts = s.split("°")
                deg = float(parts[0])
                rest = parts[1] if len(parts) > 1 else ""
                abbrev = rest[:2]
                sign = SIGN_ABBREVS.get(abbrev, abbrev)
                return {"sign": sign, "degreeInSign": str(round(deg, 2))}
            except Exception:
                return {}

        normalized["angles"] = {
            "ascendant": _parse_angle(chart_angles.get("ascendant", "")),
            "midheaven": _parse_angle(chart_angles.get("midheaven", "")),
        }

    # ── Normalize sect (infer from Sun position if not present) ──
    if "sect" not in data:
        # Check if Sun is above horizon (houses 7-12 = above in whole sign)
        sun_house = None
        for p in normalized.get("planets", []):
            if p.get("name") == "Sun":
                sun_house = p.get("house")
                break
        if sun_house:
            is_day = int(sun_house) >= 7 or int(sun_house) <= 1
            normalized["sect"] = {
                "isDaySect": is_day,
                "sectLabel": "Day" if is_day else "Night",
                "note": "inferred from Sun house position",
            }

    return normalized


async def full_chart_computation(name: str) -> str:
    """Gather ALL computational data for a natal chart in one call.

    Returns every piece of astrological data Helios can compute:
    planets, dignities, depositors, houses, angles, lots, sect,
    aspects, profections, zodiacal releasing, and current transits.

    All house assignments converted to whole sign houses.

    This is the raw data layer. Always maximal, regardless of report size.

    Args:
        name: Chart name (must exist in Helios or local storage)
    """
    results = {}
    errors = []

    # 1. Full chart data (planets, houses, angles, lots, depositors, sect)
    try:
        results["chart"] = await call_sweph(f"/chart/{name}")
    except Exception as e:
        errors.append(f"chart: {e}")
        # Try local storage as fallback
        local = _load_local_chart(name)
        if local:
            results["chart"] = _normalize_legacy_chart(local)
        else:
            return json.dumps({"error": f"Chart '{name}' not found", "details": errors})

    # 1b. Compute whole sign houses (Stella's native house system)
    results["chart"] = _apply_whole_sign_houses(results["chart"])

    # 1c. Derivative houses (planet-to-house relationships + aspect geometry)
    results["derivative_houses"] = compute_derivative_houses(results["chart"])

    # 2. Essential dignities for every planet in the chart
    chart = results.get("chart", {})
    planets = chart.get("planets", [])
    sect = chart.get("sect", {})
    is_day = sect.get("isDaySect", True)

    dignity_results = []
    for p in planets:
        p_name = p.get("name", "")
        lon = p.get("longitude")
        if lon and p_name not in ("North Node", "South Node", "Chiron"):
            try:
                dignity = await call_sweph(
                    f"/dignity-score?planet={p_name}&longitude={lon}&isDaySect={'true' if is_day else 'false'}"
                )
                dignity_results.append(dignity)
            except Exception as e:
                errors.append(f"dignity {p_name}: {e}")
    results["dignities"] = dignity_results

    # 3. Current aspects between all planets
    try:
        results["current_aspects"] = await call_sweph("/aspects-now")
    except Exception as e:
        errors.append(f"aspects: {e}")

    # 4. Profections
    try:
        results["profections"] = await call_sweph(f"/profections/{name}")
    except Exception as e:
        errors.append(f"profections: {e}")

    # 5. Zodiacal Releasing (both lots)
    for lot in ["spirit", "fortune"]:
        try:
            results[f"zr_{lot}"] = await call_sweph(f"/zr/{name}?lot={lot}")
        except Exception as e:
            errors.append(f"zr_{lot}: {e}")

    # 6. Current transits to natal
    try:
        results["transits"] = await call_sweph(f"/transits/{name}/now?major=true")
    except Exception as e:
        errors.append(f"transits: {e}")

    # 7. Transit summary (compact view with timing context)
    try:
        results["transit_summary"] = await call_sweph(f"/transits/{name}/summary")
    except Exception as e:
        errors.append(f"transit_summary: {e}")

    # 8. Current planetary positions (for context)
    try:
        results["current_positions"] = await call_sweph("/planets-now")
    except Exception as e:
        errors.append(f"current_positions: {e}")

    # 9. Current moon
    try:
        results["current_moon"] = await call_sweph("/moon-now")
    except Exception as e:
        errors.append(f"current_moon: {e}")

    if errors:
        results["_warnings"] = errors

    return json.dumps(results, indent=2)


def _gather_knowledge_for_chart(chart_data: dict, results_per_query: int = 3) -> list[dict]:
    """Query the Neo4j knowledge graph for every significant placement in the chart.

    Uses graph traversals — NO embedding API calls. Instant.

    Pulls interpretive material across all layers for every planet,
    plus timing techniques (profections, ZR).

    Returns a list of {query, layer, results} dicts.
    """
    knowledge_hits = []
    chart = chart_data.get("chart", {})
    planets = chart.get("planets", [])

    # Map planet names to graph IDs
    name_to_id = {
        "Sun": "sun", "Moon": "moon", "Mercury": "mercury", "Venus": "venus",
        "Mars": "mars", "Jupiter": "jupiter", "Saturn": "saturn",
        "Uranus": "uranus", "Neptune": "neptune", "Pluto": "pluto",
        "North Node": "north_node", "South Node": "south_node", "Chiron": None,
    }

    for p in planets:
        pname = p.get("name", "")
        sign = p.get("sign", "")
        house = p.get("house", "")
        planet_id = name_to_id.get(pname)
        if not planet_id:
            continue
        sign_id = sign.lower() if sign else None
        house_num = int(house) if house and str(house).isdigit() else None

        # ── Planet + Sign: technical layer (dignity, rulership) ──
        if sign_id:
            results = neo4j_query("""
                MATCH (i:Interpretation)-[:DESCRIBES]->(p:Planet {id: $planet}),
                      (i)-[:DESCRIBES]->(s:Sign {id: $sign}),
                      (i)-[:IN_LAYER]->(l:Layer {id: 'technical'}),
                      (i)-[:AUTHORED_BY]->(a:Author)
                RETURN i.text AS text, a.name AS author, i.source_title AS title,
                       i.trust_tier AS tier
                ORDER BY i.trust_tier ASC
                LIMIT $limit
            """, planet=planet_id, sign=sign_id, limit=results_per_query)

            if results:
                knowledge_hits.append({
                    "query": f"{pname} in {sign} (technical)",
                    "results": [{"text": r["text"][:500], "author": r["author"],
                                 "title": r["title"], "tier": r["tier"]} for r in results],
                })

        # ── Planet + House: psychological layer ──
        if house_num:
            results = neo4j_query("""
                MATCH (i:Interpretation)-[:DESCRIBES]->(p:Planet {id: $planet}),
                      (i)-[:DESCRIBES]->(h:House {number: $house}),
                      (i)-[:IN_LAYER]->(l:Layer {id: 'psychological'}),
                      (i)-[:AUTHORED_BY]->(a:Author)
                RETURN i.text AS text, a.name AS author, i.source_title AS title,
                       i.trust_tier AS tier
                ORDER BY i.trust_tier ASC
                LIMIT $limit
            """, planet=planet_id, house=house_num, limit=results_per_query)

            if results:
                knowledge_hits.append({
                    "query": f"{pname} in house {house} (psychological)",
                    "results": [{"text": r["text"][:500], "author": r["author"],
                                 "title": r["title"], "tier": r["tier"]} for r in results],
                })

        # ── Planet + Sign: reference layer (delineations) ──
        if sign_id:
            results = neo4j_query("""
                MATCH (i:Interpretation)-[:DESCRIBES]->(p:Planet {id: $planet}),
                      (i)-[:DESCRIBES]->(s:Sign {id: $sign}),
                      (i)-[:IN_LAYER]->(l:Layer {id: 'reference'}),
                      (i)-[:AUTHORED_BY]->(a:Author)
                RETURN i.text AS text, a.name AS author, i.source_title AS title,
                       i.trust_tier AS tier
                ORDER BY i.trust_tier ASC
                LIMIT $limit
            """, planet=planet_id, sign=sign_id, limit=results_per_query)

            if results:
                knowledge_hits.append({
                    "query": f"{pname} in {sign} (reference)",
                    "results": [{"text": r["text"][:500], "author": r["author"],
                                 "title": r["title"], "tier": r["tier"]} for r in results],
                })

    # ── Derivative houses: Pelletier planet-in-house interpretations ──
    derivative_data = chart_data.get("derivative_houses", {})
    key_connections = derivative_data.get("key_connections", [])
    for conn in key_connections[:6]:  # Limit to top 6 key connections
        conn_planet = conn.get("planet", "")
        conn_house = conn.get("house")
        conn_planet_id = name_to_id.get(conn_planet)
        if not conn_planet_id or not conn_house:
            continue

        # Try Neo4j first (Pelletier authored interpretations)
        results = neo4j_query("""
            MATCH (i:Interpretation)-[:DESCRIBES]->(p:Planet {id: $planet}),
                  (i)-[:DESCRIBES]->(h:House {number: $house}),
                  (i)-[:AUTHORED_BY]->(a:Author {name: 'Robert Pelletier'}),
                  (i)-[:IN_LAYER]->(l:Layer)
            RETURN i.text AS text, a.name AS author, i.source_title AS title,
                   i.trust_tier AS tier, l.id AS layer
            ORDER BY i.trust_tier ASC
            LIMIT $limit
        """, planet=conn_planet_id, house=int(conn_house), limit=results_per_query)

        if results:
            deriv_num = conn.get("derivative_number", "?")
            deriv_meaning = conn.get("derivative_meaning", "")
            knowledge_hits.append({
                "query": f"{conn_planet} derivative to house {conn_house} "
                         f"({deriv_num}th = {deriv_meaning}, Pelletier)",
                "results": [{"text": r["text"][:500], "author": r["author"],
                             "title": r["title"], "tier": r["tier"],
                             "layer": r.get("layer", "")} for r in results],
            })
        else:
            # Fall back to Neo4j text search
            try:
                fallback_results = _knowledge_query_neo4j(
                    query=f"{conn_planet} {conn_house}th house",
                    author="Robert Pelletier",
                    top=results_per_query,
                )
                if fallback_results:
                    deriv_num = conn.get("derivative_number", "?")
                    deriv_meaning = conn.get("derivative_meaning", "")
                    knowledge_hits.append({
                        "query": f"{conn_planet} derivative to house {conn_house} "
                                 f"({deriv_num}th = {deriv_meaning}, graph search)",
                        "results": [
                            {
                                "text": (r.get("text") or "")[:500],
                                "author": r.get("author", "?"),
                                "title": r.get("title", "?"),
                                "tier": r.get("tier", 4),
                            }
                            for r in fallback_results
                        ],
                    })
            except Exception:
                pass  # Graph fallback is best-effort

    # ── Archetypal layer: notable dignities/debilities ──
    dignities = chart_data.get("dignities", [])
    for d in dignities:
        if d.get("detriment") or d.get("fall") or d.get("domicile") or d.get("exaltation"):
            planet_name = d.get("planet", "")
            sign_name = d.get("sign", "")
            condition = d.get("condition", "")
            planet_id = planet_name.lower()
            sign_id = sign_name.lower()

            results = neo4j_query("""
                MATCH (i:Interpretation)-[:DESCRIBES]->(p:Planet {id: $planet}),
                      (i)-[:DESCRIBES]->(s:Sign {id: $sign}),
                      (i)-[:IN_LAYER]->(l:Layer {id: 'archetypal'}),
                      (i)-[:AUTHORED_BY]->(a:Author)
                RETURN i.text AS text, a.name AS author, i.source_title AS title,
                       i.trust_tier AS tier
                ORDER BY i.trust_tier ASC
                LIMIT $limit
            """, planet=planet_id, sign=sign_id, limit=results_per_query)

            if results:
                knowledge_hits.append({
                    "query": f"{planet_name} in {sign_name} ({condition}, archetypal)",
                    "results": [{"text": r["text"][:500], "author": r["author"],
                                 "title": r["title"], "tier": r["tier"]} for r in results],
                })

    # ── Timing: profections ──
    profections = chart_data.get("profections", {})
    lord_of_year = profections.get("profection", {}).get("lordOfYear", "")
    if lord_of_year:
        lord_id = lord_of_year.lower()
        results = neo4j_query("""
            MATCH (i:Interpretation)-[:DESCRIBES]->(t:Technique {id: 'profections'}),
                  (i)-[:DESCRIBES]->(p:Planet {id: $planet}),
                  (i)-[:AUTHORED_BY]->(a:Author)
            RETURN i.text AS text, a.name AS author, i.source_title AS title,
                   i.trust_tier AS tier
            ORDER BY i.trust_tier ASC
            LIMIT $limit
        """, planet=lord_id, limit=results_per_query)

        if results:
            knowledge_hits.append({
                "query": f"Lord of year: {lord_of_year} (profections)",
                "results": [{"text": r["text"][:500], "author": r["author"],
                             "title": r["title"], "tier": r["tier"]} for r in results],
            })

    # ── Timing: ZR ──
    zr_spirit = chart_data.get("zr_spirit", {})
    zr_sign = zr_spirit.get("activePeriod", {}).get("sign", "")
    zr_ruler = zr_spirit.get("activePeriod", {}).get("ruler", "")
    if zr_sign:
        results = neo4j_query("""
            MATCH (i:Interpretation)-[:DESCRIBES]->(t:Technique {id: 'zodiacal_releasing'}),
                  (i)-[:IN_LAYER]->(l:Layer {id: 'technical'}),
                  (i)-[:AUTHORED_BY]->(a:Author)
            RETURN i.text AS text, a.name AS author, i.source_title AS title,
                   i.trust_tier AS tier
            ORDER BY i.trust_tier ASC
            LIMIT $limit
        """, limit=results_per_query)

        if results:
            knowledge_hits.append({
                "query": f"ZR Spirit L1: {zr_sign} ruled by {zr_ruler}",
                "results": [{"text": r["text"][:500], "author": r["author"],
                             "title": r["title"], "tier": r["tier"]} for r in results],
            })

    # ── Structural context: rulership web for key planets ──
    # Get the dignity relationships for the chart from the graph itself
    for p in planets[:7]:  # Traditional planets only
        planet_id = name_to_id.get(p.get("name", ""))
        if not planet_id:
            continue
        sign_id = p.get("sign", "").lower()
        if not sign_id:
            continue

        # What dignity does this planet have in this sign?
        dignity_info = neo4j_query("""
            MATCH (p:Planet {id: $planet})
            OPTIONAL MATCH (p)-[:RULES]->(s:Sign {id: $sign})
            OPTIONAL MATCH (p)-[:EXALTED_IN]->(s2:Sign {id: $sign})
            OPTIONAL MATCH (p)-[:DETRIMENT_IN]->(s3:Sign {id: $sign})
            OPTIONAL MATCH (p)-[:FALL_IN]->(s4:Sign {id: $sign})
            OPTIONAL MATCH (p)-[:TRIPLICITY_RULER]->(s5:Sign {id: $sign})
            RETURN s IS NOT NULL AS domicile,
                   s2 IS NOT NULL AS exalted,
                   s3 IS NOT NULL AS detriment,
                   s4 IS NOT NULL AS fall,
                   s5 IS NOT NULL AS triplicity
        """, planet=planet_id, sign=sign_id)

        if dignity_info:
            d = dignity_info[0]
            conditions = []
            if d["domicile"]: conditions.append("domicile")
            if d["exalted"]: conditions.append("exaltation")
            if d["detriment"]: conditions.append("detriment")
            if d["fall"]: conditions.append("fall")
            if d["triplicity"]: conditions.append("triplicity ruler")
            if conditions:
                knowledge_hits.append({
                    "query": f"{p['name']} in {p['sign']} (graph dignity)",
                    "results": [{"text": f"{p['name']} is in {', '.join(conditions)} in {p['sign']}. "
                                         f"This is a structural relationship from the astrological ontology.",
                                 "author": "graph", "title": "Structural Ontology", "tier": 0}],
                })

    return knowledge_hits


@mcp.tool()
async def chart_reading(
    name: str,
    size: str = "m",
    report_type: str = "narrative",
    framework: str = "psychological",
) -> str:
    """Generate a complete chart reading: full computation + knowledge graph + narrative prompt.

    This is the main chart interpretation tool. Three axes control the output:
    1. SIZE — how deep (xs/s/m/l/xl)
    2. TYPE — how it's delivered (technical/narrative/poem)
    3. FRAMEWORK — what interpretive lens (psychological/deterministic/hellenistic/stoic/mythological)

    The LLM receives: raw data + source material + interpretation instructions.
    The LLM synthesizes the reading.

    Args:
        name: Chart name (e.g. 'chris', 'robin')
        size: xs | s | m | l | xl (default: m)
        report_type: technical | narrative | poem (default: narrative)
        framework: psychological | deterministic | hellenistic | stoic | mythological (default: psychological)
    """
    size = size.lower()
    if size not in CHART_SIZES:
        return f"Invalid size '{size}'. Choose from: {', '.join(CHART_SIZES.keys())}"

    report_type = report_type.lower()
    if report_type not in REPORT_TYPES:
        return f"Invalid report_type '{report_type}'. Choose from: {', '.join(REPORT_TYPES.keys())}"

    framework = framework.lower()
    if framework not in FRAMEWORKS:
        return f"Invalid framework '{framework}'. Choose from: {', '.join(FRAMEWORKS.keys())}"

    size_config = CHART_SIZES[size]
    type_config = REPORT_TYPES[report_type]
    framework_config = FRAMEWORKS[framework]

    # ── Step 1: Full computation (always maximal) ──
    computation_json = await full_chart_computation(name)
    computation = json.loads(computation_json)

    if "error" in computation:
        return json.dumps(computation)

    # ── Step 2: Knowledge graph queries (grounded in corpus) ──
    knowledge = _gather_knowledge_for_chart(
        computation,
        results_per_query=size_config["knowledge_results"],
    )

    # ── Step 2b: Dignity-weighted narrative priority analysis ──
    # The strongest planets by dignity score drive the lived experience.
    # A debilitated chart ruler delivers its archetype CONDITIONALLY,
    # gated by the strongest planet's state.
    chart = computation.get("chart", {})
    planets = chart.get("planets", [])
    sect = chart.get("sect", {})
    asc_sign = None
    angles = chart.get("angles", {})
    if isinstance(angles, dict):
        asc_sign = angles.get("ascendant", {}).get("sign")

    planet_weights = []
    for p in planets:
        pname = p.get("name", "")
        if pname in ("Chiron", "North Node", "South Node", "Uranus", "Neptune", "Pluto"):
            continue
        d = p.get("dignities", {})
        score = d.get("score", 0) if isinstance(d, dict) else 0
        house = p.get("house", "")
        sign = p.get("sign", "")
        condition = d.get("condition", "neutral") if isinstance(d, dict) else "neutral"
        is_asc_ruler = (sign == asc_sign) if asc_sign else False
        planet_weights.append({
            "name": pname, "sign": sign, "house": house,
            "score": score, "condition": condition,
        })

    # Sort by score descending
    planet_weights.sort(key=lambda x: x["score"], reverse=True)

    # Find chart ruler (ASC ruler)
    chart_ruler = None
    asc_ruler_name = SIGN_RULERS.get(asc_sign, "") if asc_sign else ""
    for pw in planet_weights:
        if pw["name"] == asc_ruler_name:
            chart_ruler = pw
            break

    # Build the priority analysis
    strongest = planet_weights[:3] if planet_weights else []
    weakest = [p for p in planet_weights if p["score"] < 0]

    priority_lines = []
    priority_lines.append("=== DIGNITY-WEIGHTED NARRATIVE PRIORITY ===")
    priority_lines.append("CRITICAL: Dignity score determines which planets dominate LIVED EXPERIENCE.")
    priority_lines.append("The strongest planet by score shapes who this person IS day-to-day.")
    priority_lines.append("The ASC archetype is the MASK — it only expresses freely when the")
    priority_lines.append("strongest planet's needs are met. If the chart ruler is weak/peregrine,")
    priority_lines.append("the ASC qualities are CONDITIONAL, not constant.")
    priority_lines.append("")

    if asc_sign and chart_ruler:
        priority_lines.append(f"Chart ruler: {chart_ruler['name']} ({asc_sign} ASC) — score {chart_ruler['score']} ({chart_ruler['condition']})")
        if chart_ruler["score"] <= 0:
            priority_lines.append(f"  ⚠ WEAK CHART RULER: {asc_sign} ASC qualities are NOT the default presentation.")
            priority_lines.append(f"  They emerge conditionally — when externally validated or when the dominant")
            priority_lines.append(f"  planet below is settled. Lead the narrative with the dominant planet, not the ASC.")
        elif chart_ruler["score"] >= 5:
            priority_lines.append(f"  ✓ STRONG CHART RULER: {asc_sign} ASC qualities ARE the default presentation.")
            priority_lines.append(f"  Lead the narrative with the ASC archetype — it's reliably expressed.")
        priority_lines.append("")

    priority_lines.append("Dominant planets (highest dignity — drive the lived experience):")
    for pw in strongest:
        priority_lines.append(f"  {pw['name']:10s} {pw['sign']:14s} {pw['house']}H  score={pw['score']:+d} ({pw['condition']})")
    priority_lines.append("")

    if weakest:
        priority_lines.append("Debilitated planets (these functions are DIFFICULT, not absent):")
        for pw in weakest:
            priority_lines.append(f"  {pw['name']:10s} {pw['sign']:14s} {pw['house']}H  score={pw['score']:+d} ({pw['condition']})")
        priority_lines.append("  Name their shadows DIRECTLY. Debilitated Mercury = jumps to conclusions,")
        priority_lines.append("  not 'broad thinking.' Debilitated Venus = loves intensely but not legibly,")
        priority_lines.append("  not 'deep love style.' The reader should recognize themselves in the friction.")
        priority_lines.append("")

    priority_lines.append("NARRATIVE WEIGHT RULE: The planet with the highest dignity score gets the")
    priority_lines.append("most narrative real estate. If a 12H planet scores highest, the person's")
    priority_lines.append("HIDDEN life dominates their experience even if the ASC looks different.")
    priority_lines.append("The gap between the ASC mask and the dominant planet's reality IS the story.")

    narrative_priority = "\n".join(priority_lines)

    # ── Step 3: Build narrative structure based on type ──
    if report_type == "technical":
        narrative_structure = """
=== STRUCTURE (TECHNICAL) ===
Lead with data, follow with interpretation. For each section:
1. State the astrological facts (positions, dignities, aspects)
2. Note derivative house relationships where significant
3. Interpret through the chosen framework
4. Cite knowledge graph sources by author/tradition

Sections:
## Chart Overview — Sect, ASC, key dignities, final dispositor
## The Planets — Each planet: position → dignity → house → aspects → interpretation
## House Relationships — Derivative house connections, structural geometry
## Timing — Profections, ZR, current transits, upcoming activations
## Synthesis — The whole picture, key tensions, growth edges
## Appendix — Raw computation tables (auto-included)
"""
    elif report_type == "poem":
        narrative_structure = """
=== STRUCTURE (POEM) ===
The chart becomes art. Choose the form that best fits this person's chart:
- Free verse with stanzas for each life domain
- Mythological narrative (the hero's journey of this chart)
- A letter from the chart to its person
- Lyric fragments, each capturing a placement

No astrological jargon in the verse. Images carry the meaning.
The technical appendix follows separately.

End with a single distilled image or line that captures the whole chart.
"""
    else:  # narrative (default)
        narrative_structure = """
=== NARRATIVE STRUCTURE ===
Use these as section headers (## headers in markdown). They are the framework.
Each section is a clear container. The narrative weaves within each section.
Adapt header names to feel natural for this specific person, but follow the order.

## First Impression
Who this person appears to be. The face they show. How the world reads them.

## The Interior
How they actually feel inside. Emotional processing style. What soothes them,
what overwhelms them. The gap (or alignment) between the face and the interior.

## The Roots
How early life and family shaped their patterns. Attachment style. What the
home environment taught them about safety, stability, love, and self-worth.

## The Mind
How they think, communicate, process information. The quality and orientation
of their intellectual life. What their mind is drawn to.

## The Drive
What powers them. Creative and professional output. Natural strengths.
Where the drive overheats — compulsion, overwork, self-exploitation.

## The Mirror
What they attract in others. Relationship patterns. What gets projected.
The feedback loop between self-image and how others reflect them back.

## The Blind Spots
What operates below awareness. Shadow material. Unconscious patterns.
The things they can't see about themselves that others can.

## The Current Chapter
Where they are right now in life's larger arc. What season this is.
What's ending, beginning, or being demanded. The biographical moment.

## The Invitation
What this moment is asking of them. The growth edge. Actionable insight.
What a wise friend who could see everything would say.
"""

    # ── Step 4: Package everything ──
    output = {
        "report_config": {
            "chart_name": name,
            "size": size_config["label"],
            "target_length": size_config["target_length"],
            "report_type": type_config["label"],
            "framework": framework_config["label"],
        },
        "narrative_instructions": f"""
=== CHART READING: {name.upper()} ===
Size: {size_config['label']}
Target length: {size_config['target_length']}
Type: {type_config['label']}
Framework: {framework_config['label']}

{narrative_priority}

=== DEPTH GUIDELINES ===
{size_config['depth']}

{narrative_structure}

=== REPORT TYPE ===
{type_config['instructions']}

=== INTERPRETIVE FRAMEWORK ===
{framework_config['instructions']}

=== OUTPUT RULES ===
- Every size gets full computation. Sizing controls elaboration depth only.
- The reader should feel deeply understood, not lectured about their chart.
- The computation data and knowledge graph are your RAW MATERIALS.
- For 'narrative' and 'poem' types: include a TECHNICAL APPENDIX at the end
  with the raw astrological data (planets, dignities, houses, aspects, timing).
  This lets the reader verify and go deeper.
- For 'technical' type: data IS the body. No appendix needed.
- DIGNITY DRIVES NARRATIVE WEIGHT. The highest-scoring planet gets the most
  space. If the ASC ruler is weak, the ASC archetype is CONDITIONAL — describe
  WHEN and WHY it activates, not as a constant. The gap between mask and
  dominant planet IS the central tension of the reading.
""",
        "computation": computation,
        "knowledge_graph": knowledge,
    }

    return json.dumps(output, indent=2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 7: DISCOVER — Emergent Pattern Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Throws ALL techniques at a chart and surfaces what's interesting.
# The data self-organizes into the reading. Variation → Selection → Memory.

_SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
          'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
_ASPECT_TYPES = {0: 'conjunction', 60: 'sextile', 90: 'square', 120: 'trine', 180: 'opposition'}


def _d_lon_to_sign(lon: float) -> str:
    return _SIGNS[int(lon / 30)]


def _d_lon_to_display(lon: float) -> str:
    sign = _SIGNS[int(lon / 30)]
    deg = lon % 30
    return f"{int(deg)}°{int((deg % 1) * 60):02d}' {sign}"


def _d_aspect_between(lon1: float, lon2: float, orb_limit: float = 2.0):
    diff = abs(lon1 - lon2) % 360
    if diff > 180:
        diff = 360 - diff
    for asp_deg, asp_name in _ASPECT_TYPES.items():
        orb = abs(diff - asp_deg)
        if orb <= orb_limit:
            return (asp_name, orb)
    return None


def _d_midpoint_90(lon1: float, lon2: float):
    l1, l2 = lon1 % 90, lon2 % 90
    near = (l1 + l2) / 2
    far = (near + 45) % 90
    return near, far


def _d_midpoint_orb_90(test_lon: float, mp: float) -> float:
    t = test_lon % 90
    diff = abs(t - mp)
    if diff > 45:
        diff = 90 - diff
    return diff


def _d_solar_arc(birth_date: str) -> float:
    parts = birth_date.split('-')
    birth = datetime(int(parts[0]), int(parts[1]), int(parts[2]), tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - birth).days / 365.25 * 0.9856


def _discover_patterns(chart_data: dict, transit_data: dict) -> dict:
    """Run all techniques and rank convergences."""
    natal_planets = {}
    birth_date = chart_data.get("birthDate", chart_data.get("date", "1986-05-01"))

    for p in chart_data.get("planets", []):
        name = p.get("name", "")
        lon = p.get("longitude")
        if lon is not None:
            natal_planets[name] = {
                "longitude": float(lon),
                "sign": p.get("sign", _d_lon_to_sign(float(lon))),
                "house": p.get("house"),
                "dignity_score": p.get("dignityScore", p.get("dignity_score")),
            }

    for key in ["ascendant", "midheaven"]:
        angle = chart_data.get(key, chart_data.get("angles", {}).get(key))
        if angle:
            lon = float(angle.get("longitude", angle) if isinstance(angle, dict) else angle)
            label = "ASC" if "asc" in key.lower() else "MC"
            natal_planets[label] = {"longitude": lon, "sign": _d_lon_to_sign(lon),
                                     "house": 1 if label == "ASC" else 10}

    transit_positions = {}
    transits_list = transit_data if isinstance(transit_data, list) else transit_data.get("transits", [])
    seen = set()
    for t in transits_list:
        tp = t.get("transit", {})
        name = tp.get("planet", "")
        if name and name not in seen:
            seen.add(name)
            sign = tp.get("sign", "Aries")
            deg = float(tp.get("degree", 0))
            sign_idx = _SIGNS.index(sign) if sign in _SIGNS else 0
            transit_positions[name] = {
                "longitude": sign_idx * 30 + deg, "sign": sign, "degree": deg,
                "isRetrograde": tp.get("isRetrograde", False),
            }

    solar_arc = _d_solar_arc(birth_date)
    sa_positions = {}
    for name, info in natal_planets.items():
        sa_lon = (info["longitude"] + solar_arc) % 360
        sa_positions[name] = {"longitude": sa_lon, "sign": _d_lon_to_sign(sa_lon),
                               "display": _d_lon_to_display(sa_lon)}

    natal_names = list(natal_planets.keys())
    midpoints = []
    for i in range(len(natal_names)):
        for j in range(i + 1, len(natal_names)):
            n1, n2 = natal_names[i], natal_names[j]
            near, far = _d_midpoint_90(natal_planets[n1]["longitude"], natal_planets[n2]["longitude"])
            midpoints.append({"pair": f"{n1}/{n2}", "mp": near})
            midpoints.append({"pair": f"{n1}/{n2}", "mp": far})

    findings = {
        "solar_arc_degrees": round(solar_arc, 2),
        "transit_to_midpoint": [], "solar_arc_aspects": [],
        "solar_arc_to_midpoint": [], "transit_aspects_tight": [],
        "convergence_zones": [],
    }

    # Transit planets → natal midpoints (orb < 1.5°)
    for t_name, t_info in transit_positions.items():
        for mp in midpoints:
            orb = _d_midpoint_orb_90(t_info["longitude"], mp["mp"])
            if orb < 1.5:
                findings["transit_to_midpoint"].append({
                    "transit": t_name, "transit_pos": _d_lon_to_display(t_info["longitude"]),
                    "retrograde": t_info.get("isRetrograde", False),
                    "midpoint": mp["pair"], "orb": round(orb, 2),
                })

    # SA aspects → natal (orb < 2°)
    for sa_name, sa_info in sa_positions.items():
        for n_name, n_info in natal_planets.items():
            if sa_name == n_name:
                continue
            result = _d_aspect_between(sa_info["longitude"], n_info["longitude"], 2.0)
            if result:
                findings["solar_arc_aspects"].append({
                    "sa_planet": sa_name, "sa_pos": sa_info["display"],
                    "aspect": result[0], "natal_planet": n_name,
                    "natal_pos": _d_lon_to_display(n_info["longitude"]),
                    "natal_house": n_info.get("house"), "orb": round(result[1], 2),
                })

    # SA → natal midpoints (orb < 1.5°)
    for sa_name, sa_info in sa_positions.items():
        for mp in midpoints:
            orb = _d_midpoint_orb_90(sa_info["longitude"], mp["mp"])
            if orb < 1.5:
                pair_parts = mp["pair"].split("/")
                if sa_name in pair_parts:
                    continue
                findings["solar_arc_to_midpoint"].append({
                    "sa_planet": sa_name, "sa_pos": sa_info["display"],
                    "midpoint": mp["pair"], "orb": round(orb, 2),
                })

    # Tight transit aspects (orb < 1°)
    for t in transits_list:
        orb = float(t.get("orb", 99))
        if orb > 1.0:
            continue
        tp = t.get("transit", {})
        np = t.get("natal", t.get("natalPoint", {}))
        findings["transit_aspects_tight"].append({
            "transit": tp.get("planet", "?"),
            "transit_pos": f"{tp.get('degree', '?')}° {tp.get('sign', '?')}",
            "retrograde": tp.get("isRetrograde", False),
            "aspect": t.get("aspect", "?"), "natal": np.get("planet", np.get("name", "?")),
            "natal_house": np.get("house"), "orb": round(orb, 2),
            "is_lord_of_year": t.get("isToLordOfYear", False),
        })

    # Convergence zones — cluster all active points into 5° bins
    all_pts = []
    for item in findings["transit_aspects_tight"]:
        for t_name, t_info in transit_positions.items():
            if t_name == item["transit"]:
                all_pts.append({"lon": t_info["longitude"],
                                "desc": f"TR {item['transit']} {item['aspect']} natal {item['natal']}"})
    for item in findings["solar_arc_aspects"]:
        all_pts.append({"lon": sa_positions[item["sa_planet"]]["longitude"],
                        "desc": f"SA {item['sa_planet']} {item['aspect']} natal {item['natal_planet']}"})
    for item in findings["transit_to_midpoint"]:
        if item["orb"] < 0.5:
            for t_name, t_info in transit_positions.items():
                if t_name == item["transit"]:
                    all_pts.append({"lon": t_info["longitude"],
                                    "desc": f"TR {item['transit']} = {item['midpoint']} mp"})
    for item in findings["solar_arc_to_midpoint"]:
        if item["orb"] < 0.5:
            all_pts.append({"lon": sa_positions[item["sa_planet"]]["longitude"],
                            "desc": f"SA {item['sa_planet']} = {item['midpoint']} mp"})

    zone_hits = {}
    for pt in all_pts:
        zk = round(pt["lon"] / 5) * 5 % 360
        if zk not in zone_hits:
            zone_hits[zk] = {"zone": _d_lon_to_display(zk), "hits": []}
        zone_hits[zk]["hits"].append(pt["desc"])

    for zk, zd in sorted(zone_hits.items()):
        if len(zd["hits"]) >= 2:
            findings["convergence_zones"].append({
                "zone": zd["zone"], "hit_count": len(zd["hits"]), "patterns": zd["hits"],
            })

    # Sort by orb
    for key in ["transit_to_midpoint", "solar_arc_aspects", "solar_arc_to_midpoint", "transit_aspects_tight"]:
        findings[key].sort(key=lambda x: x["orb"])
    findings["convergence_zones"].sort(key=lambda x: x["hit_count"], reverse=True)

    # Summary
    findings["summary"] = {
        "total_transit_midpoint_hits": len(findings["transit_to_midpoint"]),
        "total_sa_aspects": len(findings["solar_arc_aspects"]),
        "total_sa_midpoint_hits": len(findings["solar_arc_to_midpoint"]),
        "total_tight_transits": len(findings["transit_aspects_tight"]),
        "convergence_zones_found": len(findings["convergence_zones"]),
        "top_convergence": findings["convergence_zones"][0] if findings["convergence_zones"] else None,
        "tightest_transit_midpoint": findings["transit_to_midpoint"][0] if findings["transit_to_midpoint"] else None,
        "tightest_sa_aspect": findings["solar_arc_aspects"][0] if findings["solar_arc_aspects"] else None,
        "tightest_sa_midpoint": findings["solar_arc_to_midpoint"][0] if findings["solar_arc_to_midpoint"] else None,
    }

    return findings


# ── Cosmobiology / Midpoint Tools ──

from midpoints import (
    lookup_ebertin_pair, find_midpoint_activations,
    find_transit_midpoint_activations, format_midpoint_sort,
    normalize_body, BODY_DISPLAY, to_90,
)


def _extract_positions_from_chart(chart_data: dict) -> dict[str, float]:
    """Extract {body_name: zodiac_longitude} from a chart data dict."""
    positions = {}
    for p in chart_data.get("planets", []):
        name = p.get("name", "")
        lon = p.get("longitude")
        if lon is not None and name:
            positions[name.lower()] = float(lon)

    # Angles
    for key, label in [("ascendant", "asc"), ("midheaven", "mc")]:
        angle = chart_data.get(key, chart_data.get("angles", {}).get(key))
        if angle:
            lon = float(angle.get("longitude", angle) if isinstance(angle, dict) else angle)
            positions[label] = lon

    # Node
    for p in chart_data.get("planets", []):
        name = p.get("name", "").lower()
        if "node" in name or "rahu" in name:
            positions["north_node"] = float(p["longitude"])

    return positions


@mcp.tool()
def get_midpoint_interpretation(
    body_1: str,
    body_2: str,
) -> str:
    """Look up Ebertin's COSI interpretation for a midpoint pair.

    Returns the full entry: principle, psychological/biological/sociological
    correspondence, probable manifestations, and all third-body activations.

    Args:
        body_1: First body (sun, moon, mercury, venus, mars, jupiter, saturn,
                uranus, neptune, pluto, node, asc, mc)
        body_2: Second body (same options)
    """
    text = lookup_ebertin_pair(body_1, body_2)
    if text:
        return text

    # Fallback to knowledge graph search
    b1 = normalize_body(body_1)
    b2 = normalize_body(body_2)
    display_1 = BODY_DISPLAY.get(b1, b1)
    display_2 = BODY_DISPLAY.get(b2, b2)
    results = _knowledge_query_neo4j(
        query=f"{display_1} {display_2} midpoint cosmobiology",
        tradition="cosmobiology",
        top=3,
    )
    if results:
        texts = [(r.get("text") or "") for r in results]
        return f"# {display_1}/{display_2} (graph search fallback)\n\n" + "\n\n---\n\n".join(texts)
    return f"No Ebertin data found for {display_1}/{display_2}"


@mcp.tool()
async def get_midpoint_pictures(
    name: str,
    orb: float = 1.5,
    top: int = 20,
) -> str:
    """Calculate natal midpoint pictures for a stored chart (90° dial).

    Finds all planets activating midpoints within orb. Returns midpoint sort,
    activated pictures with Ebertin delineations, and dignity context.

    Args:
        name: Stored chart name (e.g. 'chris', 'lisa')
        orb: Maximum orb on 90° dial in degrees (default 1.5)
        top: Maximum number of pictures to return (default 20)
    """
    # Load chart
    chart_path = STELLA_DIR / "charts" / f"{name.lower()}.json"
    if not chart_path.exists():
        return f"Chart '{name}' not found. Use list_charts to see available charts."
    with open(chart_path) as f:
        chart_data = json.load(f)

    positions = _extract_positions_from_chart(chart_data)
    if len(positions) < 4:
        return f"Insufficient positions in chart ({len(positions)} found). Need at least 4 bodies."

    # Midpoint sort
    output = [f"# Cosmobiogram — {name.title()}\n"]
    output.append("## Midpoint Sort (90° Dial)\n")
    output.append("```")
    output.append(format_midpoint_sort(positions))
    output.append("```\n")

    # Find activations
    activations = find_midpoint_activations(positions, orb=orb)

    output.append(f"## Midpoint Pictures (orb ≤ {orb}°)\n")
    output.append(f"Found **{len(activations)}** activations.\n")

    # Get dignity data for context
    dignities = {}
    for p in chart_data.get("planets", []):
        n = p.get("name", "").lower()
        ds = p.get("dignityScore", p.get("dignity_score"))
        if ds is not None:
            dignities[n] = int(ds)

    shown = 0
    for act in activations:
        if shown >= top:
            output.append(f"\n*...{len(activations) - top} more activations not shown (increase top parameter)*")
            break

        notation = act["notation"]
        orb_val = act["orb"]
        pair = act["pair"]

        output.append(f"### {notation}  (orb {orb_val:.2f}°)")

        # Ebertin lookup
        ebertin = lookup_ebertin_pair(act["body_1"], act["body_2"])
        if ebertin:
            # Extract first ~300 chars of the pair meaning (before sub-entries)
            preview = ebertin[:400].strip()
            # Cut at last complete sentence
            last_period = preview.rfind('.')
            if last_period > 100:
                preview = preview[:last_period + 1]
            output.append(f"> {preview}\n")

        # Dignity context
        act_body_lower = act["activating_body"].lower()
        if act_body_lower in dignities:
            ds = dignities[act_body_lower]
            quality = "strong" if ds >= 5 else "moderate" if ds >= 0 else "challenged"
            output.append(f"*{BODY_DISPLAY.get(act['activating_body'], act['activating_body'])} dignity: {ds:+d} ({quality})*\n")

        shown += 1

    return "\n".join(output)


@mcp.tool()
async def get_midpoint_transits(
    name: str,
    orb: float = 1.0,
    top: int = 15,
) -> str:
    """Find current transiting planets activating natal midpoints.

    Uses the 90° dial to find transits hitting natal midpoint structures.
    Includes Ebertin delineations for each activation.

    Args:
        name: Stored chart name
        orb: Maximum orb on 90° dial (default 1.0° — tighter for transits)
        top: Maximum activations to return (default 15)
    """
    # Load natal chart
    chart_path = STELLA_DIR / "charts" / f"{name.lower()}.json"
    if not chart_path.exists():
        return f"Chart '{name}' not found."
    with open(chart_path) as f:
        chart_data = json.load(f)

    natal_positions = _extract_positions_from_chart(chart_data)

    # Get current positions from Helios
    planet_data = await call_sweph("/planets-now")
    if not planet_data:
        return "Could not fetch current planet positions from Helios."

    sign_offsets = {
        "Aries": 0, "Taurus": 30, "Gemini": 60, "Cancer": 90, "Leo": 120,
        "Virgo": 150, "Libra": 180, "Scorpio": 210, "Sagittarius": 240,
        "Capricorn": 270, "Aquarius": 300, "Pisces": 330,
    }

    transit_positions = {}
    planets_list = planet_data if isinstance(planet_data, list) else planet_data.get("planets", [])
    for p in planets_list:
        pname = p.get("name", p.get("planet", "")).lower()
        # Handle absolute longitude OR sign+degree format
        lon = p.get("longitude", p.get("lon"))
        if lon is not None:
            transit_positions[pname] = float(lon)
        else:
            sign = p.get("sign", "")
            deg = p.get("degreeInSign", p.get("degree"))
            if sign in sign_offsets and deg is not None:
                transit_positions[pname] = sign_offsets[sign] + float(deg)

    if not transit_positions:
        return "Could not fetch current planet positions from Helios."

    # Find activations
    activations = find_transit_midpoint_activations(natal_positions, transit_positions, orb=orb)

    output = [f"# Midpoint Transits — {name.title()}\n"]
    output.append(f"*Current transits activating natal midpoints (orb ≤ {orb}°)*\n")
    output.append(f"Found **{len(activations)}** activations.\n")

    shown = 0
    for act in activations:
        if shown >= top:
            output.append(f"\n*...{len(activations) - top} more not shown*")
            break

        notation = act["notation"]
        orb_val = act["orb"]

        output.append(f"### {notation}  (orb {orb_val:.2f}°)")

        # Ebertin lookup — use transit body as activator of natal pair
        ebertin = lookup_ebertin_pair(act["natal_body_1"], act["natal_body_2"])
        if ebertin:
            preview = ebertin[:400].strip()
            last_period = preview.rfind('.')
            if last_period > 100:
                preview = preview[:last_period + 1]
            output.append(f"> {preview}\n")

        shown += 1

    return "\n".join(output)


@mcp.tool()
async def get_solar_arcs(
    name: str,
    orb: float = 1.0,
    top: int = 10,
) -> str:
    """Calculate solar arc directions hitting natal midpoints.

    Solar arcs move ~0.9856°/year. Each natal planet is advanced by
    the solar arc to find activations against natal midpoints.
    Primary cosmobiological timing method.

    Args:
        name: Stored chart name
        orb: Maximum orb on 90° dial (default 1.0°)
        top: Maximum results (default 10)
    """
    chart_path = STELLA_DIR / "charts" / f"{name.lower()}.json"
    if not chart_path.exists():
        return f"Chart '{name}' not found."
    with open(chart_path) as f:
        chart_data = json.load(f)

    natal_positions = _extract_positions_from_chart(chart_data)

    # Get birth date for solar arc calculation
    birth_date = (
        chart_data.get("birthDate")
        or chart_data.get("date")
        or chart_data.get("birthData", {}).get("date", "")
    )
    if not birth_date:
        return "Chart has no birth date — cannot calculate solar arcs."

    # Calculate solar arc
    parts = birth_date.split("-")
    birth_dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]), tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    age_years = (now - birth_dt).days / 365.25
    solar_arc = age_years * 0.9856  # ~1° per year

    # Create solar arc directed positions
    sa_positions = {}
    for body, lon in natal_positions.items():
        sa_positions[body] = (lon + solar_arc) % 360

    # Find SA planets hitting natal midpoints
    activations = find_transit_midpoint_activations(natal_positions, sa_positions, orb=orb)

    output = [f"# Solar Arc Directions — {name.title()}\n"]
    output.append(f"*Age: {age_years:.1f} years | Solar arc: {solar_arc:.2f}°*\n")
    output.append(f"Found **{len(activations)}** activations (orb ≤ {orb}°).\n")

    shown = 0
    for act in activations:
        if shown >= top:
            output.append(f"\n*...{len(activations) - top} more not shown*")
            break

        # Relabel from "transit" to "SA"
        sa_body = act["transit_body"]
        display_body = BODY_DISPLAY.get(sa_body, sa_body)
        pair = act["pair"]
        pair_display = f"{BODY_DISPLAY.get(act['natal_body_1'], act['natal_body_1'])}/{BODY_DISPLAY.get(act['natal_body_2'], act['natal_body_2'])}"
        orb_val = act["orb"]

        output.append(f"### SA {display_body} = {pair_display}  (orb {orb_val:.2f}°)")

        ebertin = lookup_ebertin_pair(act["natal_body_1"], act["natal_body_2"])
        if ebertin:
            preview = ebertin[:400].strip()
            last_period = preview.rfind('.')
            if last_period > 100:
                preview = preview[:last_period + 1]
            output.append(f"> {preview}\n")

        # Timing: when was/is exact?
        # orb / rate = years offset. Positive orb = not yet exact if SA approaching.
        output.append(f"*Solar arc rate: ~0.99°/year*\n")

        shown += 1

    return "\n".join(output)


@mcp.tool()
async def discover(name: str, top: int = 10) -> str:
    """Discover what's most active in a chart RIGHT NOW.

    Throws all techniques at a stored chart — transits, solar arcs, midpoints,
    convergence zones — and surfaces the tightest, most significant patterns.
    The data self-organizes into ranked findings.

    This is the seed of emergent pattern detection: instead of asking
    specific questions, let the chart tell you what's happening.

    Args:
        name: Name of the stored chart
        top: Number of results per category (default 10)
    """
    # Load chart data
    chart_data = _load_local_chart(name)
    if not chart_data:
        try:
            chart_data = await call_sweph(f"/chart/{name}")
        except Exception:
            return json.dumps({"error": f"Chart '{name}' not found"})

    chart_data = _normalize_legacy_chart(chart_data)
    chart_data = _apply_whole_sign_houses(chart_data)

    # Get current transits
    try:
        transit_data = await call_sweph(f"/transits/{name}/now")
    except Exception as e:
        return json.dumps({"error": f"Failed to get transits: {e}"})

    # Run discovery
    findings = _discover_patterns(chart_data, transit_data)

    # Trim to top N per category
    for key in ["transit_to_midpoint", "solar_arc_aspects", "solar_arc_to_midpoint", "transit_aspects_tight"]:
        findings[key] = findings[key][:top]

    # Add profection context
    try:
        findings["profections"] = await call_sweph(f"/profections/{name}")
    except Exception:
        pass

    return json.dumps(findings, indent=2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 8: REFLECT & RECALL — Learning Memory System
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Selection + Memory for the emergent system.
# reflect() stores validated insights. recall() retrieves them.
# Each chart accumulates a living interpretive layer over time.
#
# Memory structure (charts/memory/{name}.json):
# {
#   "insights": [
#     {
#       "id": "uuid",
#       "timestamp": "ISO-8601",
#       "type": "insight|prediction|technique|life_event|feedback",
#       "content": "The actual insight text",
#       "techniques": ["midpoints", "solar_arc", "sabian"],
#       "placements": ["SA Venus opp natal Mars", "Saturn=Sun/Moon"],
#       "rating": 1-5 (how much it resonated),
#       "source": "reading|discover|manual|transit",
#       "reading_ref": "optional filename of source reading",
#       "validated": true/false (confirmed by lived experience),
#       "tags": ["love", "career", "identity"]
#     }
#   ],
#   "technique_scores": {
#     "midpoints": {"hits": 12, "resonance_sum": 45},
#     "solar_arc": {"hits": 8, "resonance_sum": 35},
#     ...
#   },
#   "placement_memory": {
#     "SA Venus opp natal Mars": {
#       "first_noted": "2026-02-14",
#       "times_referenced": 3,
#       "best_insight": "love meeting power — the engine confronted by softness"
#     }
#   }
# }


def _load_chart_memory(name: str) -> dict:
    """Load or initialize a chart's memory file."""
    path = MEMORY_DIR / f"{name.lower()}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"insights": [], "technique_scores": {}, "placement_memory": {}}


def _save_chart_memory(name: str, memory: dict):
    """Save a chart's memory file."""
    path = MEMORY_DIR / f"{name.lower()}.json"
    path.write_text(json.dumps(memory, indent=2))


def _generate_id() -> str:
    """Generate a short unique ID."""
    import hashlib
    return hashlib.md5(
        f"{datetime.now(timezone.utc).isoformat()}{random.random()}".encode()
    ).hexdigest()[:8]


@mcp.tool()
def reflect(
    name: str,
    content: str,
    insight_type: str = "insight",
    techniques: Optional[str] = None,
    placements: Optional[str] = None,
    rating: Optional[int] = None,
    source: str = "manual",
    reading_ref: Optional[str] = None,
    validated: bool = False,
    tags: Optional[str] = None,
) -> str:
    """Store a validated insight, prediction, or life event for a chart.

    This is how the system learns. Every time a reading resonates, a prediction
    lands, or a life event confirms a pattern — reflect it. Over time, the
    chart's memory builds a living interpretive layer.

    Args:
        name: Chart name (e.g. 'chris', 'lisa')
        content: The insight, prediction, or event description
        insight_type: One of: insight, prediction, technique, life_event, feedback
        techniques: Comma-separated techniques used (e.g. 'midpoints,solar_arc,sabian')
        placements: Comma-separated placements involved (e.g. 'SA Venus opp Mars,Saturn=Sun/Moon')
        rating: 1-5 how strongly it resonated (5 = profound)
        source: Where this came from: reading, discover, manual, transit
        reading_ref: Optional filename of the source reading
        validated: Whether this has been confirmed by lived experience
        tags: Comma-separated topic tags (e.g. 'love,career,identity')
    """
    memory = _load_chart_memory(name)

    tech_list = [t.strip() for t in techniques.split(",")] if techniques else []
    place_list = [p.strip() for p in placements.split(",")] if placements else []
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    entry = {
        "id": _generate_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": insight_type,
        "content": content,
        "techniques": tech_list,
        "placements": place_list,
        "rating": rating,
        "source": source,
        "reading_ref": reading_ref,
        "validated": validated,
        "tags": tag_list,
    }

    memory["insights"].append(entry)

    # Update technique scores
    if rating and tech_list:
        for tech in tech_list:
            if tech not in memory["technique_scores"]:
                memory["technique_scores"][tech] = {"hits": 0, "resonance_sum": 0}
            memory["technique_scores"][tech]["hits"] += 1
            memory["technique_scores"][tech]["resonance_sum"] += rating

    # Update placement memory
    for placement in place_list:
        if placement not in memory["placement_memory"]:
            memory["placement_memory"][placement] = {
                "first_noted": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "times_referenced": 0,
                "insights": [],
            }
        pm = memory["placement_memory"][placement]
        pm["times_referenced"] += 1
        if rating and rating >= 4:
            pm["insights"].append(content[:200])  # Store abbreviated high-resonance insights

    _save_chart_memory(name, memory)

    # Summary
    total = len(memory["insights"])
    top_tech = None
    if memory["technique_scores"]:
        top_tech = max(memory["technique_scores"].items(),
                       key=lambda x: x[1]["resonance_sum"] / max(x[1]["hits"], 1))

    return json.dumps({
        "status": "stored",
        "id": entry["id"],
        "total_insights": total,
        "top_technique": {
            "name": top_tech[0],
            "avg_resonance": round(top_tech[1]["resonance_sum"] / top_tech[1]["hits"], 1),
            "total_hits": top_tech[1]["hits"],
        } if top_tech else None,
    }, indent=2)


@mcp.tool()
def recall(
    name: str,
    query: Optional[str] = None,
    insight_type: Optional[str] = None,
    technique: Optional[str] = None,
    tag: Optional[str] = None,
    min_rating: Optional[int] = None,
    validated_only: bool = False,
    limit: int = 20,
) -> str:
    """Recall stored insights for a chart. The system's memory.

    Search and filter the chart's accumulated insights, validated patterns,
    and technique effectiveness scores. Use before generating readings to
    build on what's already been learned.

    Args:
        name: Chart name
        query: Text search across insight content
        insight_type: Filter by type (insight/prediction/technique/life_event/feedback)
        technique: Filter by technique used
        tag: Filter by tag
        min_rating: Minimum resonance rating (1-5)
        validated_only: Only show confirmed insights
        limit: Max results to return
    """
    memory = _load_chart_memory(name)

    results = memory["insights"]

    # Apply filters
    if insight_type:
        results = [r for r in results if r.get("type") == insight_type]
    if technique:
        results = [r for r in results if technique in r.get("techniques", [])]
    if tag:
        results = [r for r in results if tag in r.get("tags", [])]
    if min_rating:
        results = [r for r in results if (r.get("rating") or 0) >= min_rating]
    if validated_only:
        results = [r for r in results if r.get("validated")]
    if query:
        q = query.lower()
        results = [r for r in results if q in r.get("content", "").lower()]

    # Most recent first
    results = sorted(results, key=lambda x: x.get("timestamp", ""), reverse=True)
    results = results[:limit]

    return json.dumps({
        "name": name,
        "total_stored": len(memory["insights"]),
        "filtered_count": len(results),
        "technique_scores": memory.get("technique_scores", {}),
        "placement_memory": memory.get("placement_memory", {}),
        "insights": results,
    }, indent=2)


@mcp.tool()
def validate(name: str, insight_id: str, confirmed: bool = True, note: Optional[str] = None) -> str:
    """Mark an insight as validated (or invalidated) by lived experience.

    The feedback loop: predictions and insights get confirmed or denied
    by what actually happens. This is how the system learns what works.

    Args:
        name: Chart name
        insight_id: The ID of the insight to validate
        confirmed: True if confirmed, False if invalidated
        note: Optional note about what happened
    """
    memory = _load_chart_memory(name)

    for insight in memory["insights"]:
        if insight.get("id") == insight_id:
            insight["validated"] = confirmed
            insight["validation_date"] = datetime.now(timezone.utc).isoformat()
            if note:
                insight["validation_note"] = note

            # Boost or penalize technique scores based on validation
            multiplier = 1.5 if confirmed else 0.5
            for tech in insight.get("techniques", []):
                if tech in memory["technique_scores"]:
                    current = memory["technique_scores"][tech]
                    # Adjust resonance based on real-world confirmation
                    rating = insight.get("rating", 3)
                    adjusted = rating * multiplier
                    current["resonance_sum"] += (adjusted - rating)

            _save_chart_memory(name, memory)

            return json.dumps({
                "status": "validated" if confirmed else "invalidated",
                "insight_id": insight_id,
                "content": insight["content"][:100],
                "techniques_affected": insight.get("techniques", []),
            }, indent=2)

    return json.dumps({"error": f"Insight '{insight_id}' not found for chart '{name}'"})


@mcp.tool()
def chart_memory_stats(name: str) -> str:
    """Get memory statistics for a chart — what's been learned, what techniques work best.

    Shows technique effectiveness rankings, total insights, validation rates,
    and the most-referenced placements. Use this to understand what the system
    has learned about a particular chart over time.

    Args:
        name: Chart name
    """
    memory = _load_chart_memory(name)

    insights = memory["insights"]
    total = len(insights)
    validated = sum(1 for i in insights if i.get("validated"))
    avg_rating = (sum(i.get("rating", 0) for i in insights if i.get("rating")) /
                  max(sum(1 for i in insights if i.get("rating")), 1))

    # Technique rankings by average resonance
    tech_rankings = []
    for tech, scores in memory.get("technique_scores", {}).items():
        avg = scores["resonance_sum"] / max(scores["hits"], 1)
        tech_rankings.append({
            "technique": tech,
            "avg_resonance": round(avg, 2),
            "total_hits": scores["hits"],
        })
    tech_rankings.sort(key=lambda x: x["avg_resonance"], reverse=True)

    # Most referenced placements
    top_placements = sorted(
        memory.get("placement_memory", {}).items(),
        key=lambda x: x[1]["times_referenced"],
        reverse=True
    )[:10]

    # Type distribution
    type_counts = {}
    for i in insights:
        t = i.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Tag cloud
    tag_counts = {}
    for i in insights:
        for tag in i.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    return json.dumps({
        "name": name,
        "total_insights": total,
        "validated_count": validated,
        "validation_rate": f"{validated/max(total,1)*100:.0f}%",
        "avg_resonance": round(avg_rating, 1),
        "technique_rankings": tech_rankings,
        "top_placements": [
            {"placement": k, "times_referenced": v["times_referenced"],
             "top_insight": v.get("insights", [""])[0] if v.get("insights") else ""}
            for k, v in top_placements
        ],
        "type_distribution": type_counts,
        "tag_cloud": dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)),
    }, indent=2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION: NEO4J KNOWLEDGE GRAPH TOOLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

try:
    from graph.neo4j_tools import (
        traverse_chain, find_receptions, get_aspect_network,
        get_midpoint_pictures, chart_as_graph, walk_interpretation,
        query_graph, compare_charts, graph_stats
    )
    NEO4J_AVAILABLE = True
    print("[stella] Neo4j graph tools loaded", file=sys.stderr)
except Exception as e:
    NEO4J_AVAILABLE = False
    print(f"[stella] Neo4j tools unavailable: {e}", file=sys.stderr)

if NEO4J_AVAILABLE:
    @mcp.tool()
    async def graph_traverse_chain(name: str, planet: str) -> str:
        """Walk the depositor chain from a planet to its final dispositor.
        Shows every step: planet → sign ruler → sign ruler → ... → terminus.
        Use to understand how planetary energy flows through the chart."""
        result = traverse_chain(name, planet)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def graph_find_receptions(name: str) -> str:
        """Find all mutual receptions in a chart (by domicile, exaltation, or mixed).
        Mutual receptions create hidden bridges between planets that bypass normal depositor flow."""
        result = find_receptions(name)
        if not result:
            return json.dumps({"message": f"No mutual receptions found in {name}'s chart"})
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def graph_aspect_network(name: str, planet: str = "") -> str:
        """Get the natal aspect network for a chart. Pass planet name to filter to one planet's aspects.
        Returns all aspects sorted by orb (tightest first)."""
        result = get_aspect_network(name, planet if planet else None)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def graph_midpoint_pictures(name: str, planet: str = "", max_orb: float = 1.0) -> str:
        """Get midpoint pictures (90° dial) for a chart. The cosmobiogram wiring.
        Pass planet to filter. max_orb defaults to 1.0°."""
        result = get_midpoint_pictures(name, planet if planet else None, max_orb)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def graph_chart(name: str) -> str:
        """Return complete chart as a graph structure: placements, depositor chains,
        aspects, mutual receptions, and connected insights. The full picture."""
        result = chart_as_graph(name)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def graph_walk(name: str, planet: str) -> str:
        """Walk the graph from a natal placement, collecting EVERYTHING connected:
        the placement, its depositor chain, who deposits to it, all aspects,
        midpoint pictures, sign ontology, relevant text interpretations, and
        emergent triad insights. This is the tool for novel interpretation —
        the reading emerges from the walk, not from pre-written text."""
        result = walk_interpretation(name, planet)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def graph_compare(chart1: str, chart2: str) -> str:
        """Compare two charts — shared sign placements, cross-chart aspects (synastry),
        and structural similarities (final dispositors, depositor chain overlap)."""
        result = compare_charts(chart1, chart2)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def graph_cypher(cypher: str) -> str:
        """Execute a raw Cypher query against the Neo4j knowledge graph.
        Use for custom traversals and analysis not covered by other tools.
        Node labels: Interpretation, Planet, Sign, House, Author, Layer, Technique, NatalPlacement, Aspect, Decan, Term, Insight, Chart, Element
        Interpretation properties: text, source_title, trust_tier, layer, chunk_id, tradition, tags (source_title NOT source)
        Examples:
        - MATCH (p:NatalPlacement {chart:'chris'})-[:DEPOSITS_TO*]->(t) RETURN p.planet, t.planet
        - MATCH (i:Interpretation) WHERE i.source_title CONTAINS 'Anthology' RETURN i.text LIMIT 3
        - MATCH (i:Interpretation)-[:DESCRIBES]->(p:Planet {name:'Mars'})-[:EXALTED_IN]->(s:Sign) RETURN i.text LIMIT 3"""
        result = query_graph(cypher)
        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    async def graph_synthesize(name: str, planet: str) -> str:
        """Generate a narrative scaffold for a single placement by walking the graph.
        Collects everything connected — dignity, decan, term, depositor chain,
        aspects, midpoints, interpretations, insights — and organizes it for synthesis.
        The reading emerges from the walk. Includes auto-generated synthesis questions."""
        from graph.synthesize import synthesize_placement
        return synthesize_placement(name, planet)

    @mcp.tool()
    async def graph_synthesize_chart(name: str) -> str:
        """Generate a full chart synthesis scaffold by walking every traditional planet.
        Returns the complete narrative scaffold for all 7 traditional planets."""
        from graph.synthesize import synthesize_chart
        return synthesize_chart(name)

    @mcp.tool()
    async def graph_stats() -> str:
        """Return current knowledge graph statistics — node counts, relationship counts,
        chart names, and overall graph size."""
        from graph.neo4j_tools import graph_stats as _stats
        result = _stats()
        return json.dumps(result, indent=2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION: AUTOPOIETIC CHART TOOLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AUTOPOIETIC_DIR = STELLA_DIR / "autopoietic"
AUTOPOIETIC_SESSIONS = AUTOPOIETIC_DIR / "sessions"
AUTOPOIETIC_CONFIG = AUTOPOIETIC_DIR / "config.json"


def _load_auto_config() -> dict:
    """Load the autopoietic framework config."""
    if AUTOPOIETIC_CONFIG.exists():
        return json.loads(AUTOPOIETIC_CONFIG.read_text())
    return {"frameworks": {}, "types": [], "temperature_curve": [], "max_rounds": 5}


def _load_auto_session(session_id: str) -> dict | None:
    """Load an autopoietic session by ID."""
    path = AUTOPOIETIC_SESSIONS / f"{session_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def _save_auto_session(session: dict):
    """Save an autopoietic session."""
    AUTOPOIETIC_SESSIONS.mkdir(parents=True, exist_ok=True)
    path = AUTOPOIETIC_SESSIONS / f"{session['session_id']}.json"
    path.write_text(json.dumps(session, indent=2))


def _pick_divergent_pair(config: dict, used: list[str]) -> tuple[str, str]:
    """Pick two frameworks from different distance groups, preferring unused ones."""
    frameworks = config["frameworks"]
    remaining = {k: v for k, v in frameworks.items() if k not in used}
    # Fall back to all frameworks if fewer than 2 remain
    pool = remaining if len(remaining) >= 2 else frameworks

    # Group by distance_group
    groups: dict[str, list[str]] = {}
    for name, meta in pool.items():
        g = meta["distance_group"]
        groups.setdefault(g, []).append(name)

    # Pick from two different groups
    group_keys = list(groups.keys())
    random.shuffle(group_keys)
    if len(group_keys) >= 2:
        a = random.choice(groups[group_keys[0]])
        b = random.choice(groups[group_keys[1]])
    else:
        # Only one group available — pick two from it
        members = groups[group_keys[0]]
        random.shuffle(members)
        a, b = members[0], members[1] if len(members) > 1 else members[0]
    return a, b


def _get_temperature(config: dict, pass_index: int) -> int:
    """Get temperature for a given pass index (0-based) from the curve."""
    curve = config.get("temperature_curve", [9, 9, 5, 7, 7, 3, 5, 5, 1])
    if pass_index < len(curve):
        return curve[pass_index]
    return curve[-1] if curve else 5


@mcp.tool()
async def autopoietic_init(name: str, frameworks: list[str] | None = None) -> dict:
    """Initialize an autopoietic chart session.
    Picks two maximally divergent frameworks from the pool.
    Returns session_id, assigned frameworks, temperatures, and generation prompts.

    Args:
        name: Chart name (must exist in charts/)
        frameworks: Optional list to restrict framework pool. If None, uses all.
    """
    config = _load_auto_config()
    now = datetime.now()
    session_id = f"auto_{name}_{now.strftime('%Y%m%d_%H%M%S')}"

    # Pick first divergent pair
    if frameworks and len(frameworks) >= 2:
        fw_a, fw_b = frameworks[0], frameworks[1]
    else:
        fw_a, fw_b = _pick_divergent_pair(config, [])

    type_a = random.choice(config.get("types", ["narrative"]))
    type_b = random.choice([t for t in config.get("types", ["narrative"]) if t != type_a] or config.get("types", ["narrative"]))
    temp_d1 = _get_temperature(config, 0)
    temp_d2 = _get_temperature(config, 1)

    all_fw = list(config["frameworks"].keys())
    remaining = [f for f in all_fw if f not in [fw_a, fw_b]]

    session = {
        "session_id": session_id,
        "chart_name": name,
        "created": now.isoformat(),
        "status": "active",
        "rounds": [],
        "current_round": {
            "round": 1,
            "diverge": [],
            "converge": None,
        },
        "frameworks_used": [fw_a, fw_b],
        "frameworks_remaining": remaining,
        "final_statement": None,
        "terminated": False,
    }
    _save_auto_session(session)

    fw_meta = config["frameworks"]
    return {
        "session_id": session_id,
        "chart_name": name,
        "round": 1,
        "assignments": [
            {
                "framework": fw_a,
                "lens": fw_meta.get(fw_a, {}).get("lens", ""),
                "vocabulary": fw_meta.get(fw_a, {}).get("vocabulary", ""),
                "type": type_a,
                "temperature": temp_d1,
            },
            {
                "framework": fw_b,
                "lens": fw_meta.get(fw_b, {}).get("lens", ""),
                "vocabulary": fw_meta.get(fw_b, {}).get("vocabulary", ""),
                "type": type_b,
                "temperature": temp_d2,
            },
        ],
        "instructions": (
            f"Generate TWO independent readings of {name}'s chart.\n"
            f"Reading 1: {fw_a} framework ({fw_meta.get(fw_a, {}).get('lens', '')} lens), "
            f"{type_a} format, temperature {temp_d1}.\n"
            f"Reading 2: {fw_b} framework ({fw_meta.get(fw_b, {}).get('lens', '')} lens), "
            f"{type_b} format, temperature {temp_d2}.\n"
            f"Each reading is INDEPENDENT — do not reference the other.\n"
            f"Submit each with autopoietic_submit(pass_type='diverge')."
        ),
    }


@mcp.tool()
async def autopoietic_submit(session_id: str, pass_type: str, content: str, framework: str = "", temperature: int = 0) -> dict:
    """Submit a diverge or converge pass to an autopoietic session.

    Args:
        session_id: The session ID from autopoietic_init
        pass_type: 'diverge' or 'converge'
        content: The reading text or convergence statement
        framework: Framework name (required for diverge passes)
        temperature: Temperature used for this pass
    """
    session = _load_auto_session(session_id)
    if not session:
        return {"error": f"Session {session_id} not found"}
    if session.get("terminated"):
        return {"error": "Session is terminated", "final_statement": session.get("final_statement")}

    current = session.get("current_round", {})

    if pass_type == "diverge":
        config = _load_auto_config()
        entry = {
            "framework": framework,
            "type": "",
            "temperature": temperature,
            "content": content,
        }
        current.setdefault("diverge", []).append(entry)
        session["current_round"] = current

        diverge_count = len(current["diverge"])
        _save_auto_session(session)
        return {
            "status": "diverge_submitted",
            "round": current.get("round", 1),
            "diverge_count": diverge_count,
            "next": "Submit another diverge pass" if diverge_count < 2 else "Call autopoietic_converge to get convergence prompt",
        }

    elif pass_type == "converge":
        current["converge"] = {
            "temperature": temperature,
            "content": content,
        }
        # Complete the round
        completed_round = {
            "round": current.get("round", 1),
            "diverge": current.get("diverge", []),
            "converge": current["converge"],
        }
        session["rounds"].append(completed_round)
        session.pop("current_round", None)
        _save_auto_session(session)

        return {
            "status": "round_complete",
            "round": completed_round["round"],
            "rounds_completed": len(session["rounds"]),
            "next": "Call autopoietic_status to check if process should continue or terminate",
        }

    return {"error": f"Unknown pass_type: {pass_type}. Use 'diverge' or 'converge'."}


@mcp.tool()
async def autopoietic_converge(session_id: str) -> dict:
    """Get the convergence prompt for the current round.
    Returns a prompt that instructs the agent to find overlap between
    the current round's diverge passes. Includes the actual reading texts.
    """
    session = _load_auto_session(session_id)
    if not session:
        return {"error": f"Session {session_id} not found"}

    current = session.get("current_round", {})
    diverge_passes = current.get("diverge", [])

    if len(diverge_passes) < 2:
        return {"error": f"Need at least 2 diverge passes before converging. Have {len(diverge_passes)}."}

    # Calculate convergence temperature
    config = _load_auto_config()
    round_num = current.get("round", 1)
    # Convergence is pass index: (round-1)*3 + 2 (0-indexed: D1, D2, C1, D3, D4, C2, ...)
    pass_index = (round_num - 1) * 3 + 2
    conv_temp = _get_temperature(config, pass_index)

    # Build the passages text
    passages = []
    for i, d in enumerate(diverge_passes, 1):
        passages.append(f"--- PASSAGE {i} ({d.get('framework', 'unknown')}) ---\n{d['content']}")
    passages_text = "\n\n".join(passages)

    # Include previous convergence as context if exists
    prev_convergence = ""
    if session["rounds"]:
        last_conv = session["rounds"][-1].get("converge", {}).get("content", "")
        if last_conv:
            prev_convergence = f"\n\nPrevious convergence statement:\n{last_conv}"

    prompt = (
        f"CONVERGENCE PASS — Round {round_num}, Temperature {conv_temp}\n\n"
        f"Read these {len(diverge_passes)} passages carefully.\n\n"
        f"{passages_text}\n"
        f"{prev_convergence}\n\n"
        f"INSTRUCTIONS:\n"
        f"State ONLY what ALL passages arrived at independently.\n"
        f"No framework vocabulary. No astrology jargon.\n"
        f"Plain language. Be as brief or as long as the truth requires.\n"
        f"If they don't overlap, say so — that's data.\n"
        f"Temperature {conv_temp}: {'Be precise and conservative.' if conv_temp <= 3 else 'Allow some interpretive latitude.' if conv_temp <= 6 else 'Cast a wide net for shared signal.'}\n\n"
        f"Submit your convergence with: autopoietic_submit(session_id='{session_id}', pass_type='converge', content='...', temperature={conv_temp})"
    )

    return {
        "round": round_num,
        "temperature": conv_temp,
        "num_passages": len(diverge_passes),
        "prompt": prompt,
    }


@mcp.tool()
async def autopoietic_status(session_id: str) -> dict:
    """Check the status of an autopoietic session.
    Returns: rounds completed, frameworks used/remaining, convergence statements,
    whether to continue or terminate, next assignment if continuing.
    """
    session = _load_auto_session(session_id)
    if not session:
        return {"error": f"Session {session_id} not found"}

    config = _load_auto_config()
    rounds_completed = len(session.get("rounds", []))
    convergences = [r["converge"]["content"] for r in session.get("rounds", []) if r.get("converge")]

    # Check termination conditions
    should_terminate = False
    termination_reason = None

    if rounds_completed >= config.get("max_rounds", 5):
        should_terminate = True
        termination_reason = "Maximum rounds reached"
    elif len(convergences) >= 2:
        # Compare last two convergences — if substantially similar, terminate
        last = convergences[-1]
        prev = convergences[-2]
        # Simple heuristic: if they share >70% of words, likely converged
        last_words = set(last.lower().split())
        prev_words = set(prev.lower().split())
        if last_words and prev_words:
            overlap = len(last_words & prev_words) / max(len(last_words | prev_words), 1)
            if overlap > 0.7:
                should_terminate = True
                termination_reason = f"Convergence stabilized (word overlap: {overlap:.0%})"

    if should_terminate:
        session["terminated"] = True
        session["status"] = "terminated"
        session["final_statement"] = convergences[-1] if convergences else None
        _save_auto_session(session)
        return {
            "status": "terminated",
            "reason": termination_reason,
            "rounds_completed": rounds_completed,
            "final_statement": session["final_statement"],
            "convergence_history": convergences,
            "frameworks_used": session.get("frameworks_used", []),
        }

    # Continue — pick next pair
    fw_a, fw_b = _pick_divergent_pair(config, session.get("frameworks_used", []))
    next_round = rounds_completed + 1

    # Update session
    session["frameworks_used"] = list(set(session.get("frameworks_used", []) + [fw_a, fw_b]))
    session["frameworks_remaining"] = [
        f for f in config["frameworks"] if f not in session["frameworks_used"]
    ]
    session["current_round"] = {
        "round": next_round,
        "diverge": [],
        "converge": None,
    }
    _save_auto_session(session)

    type_a = random.choice(config.get("types", ["narrative"]))
    type_b = random.choice([t for t in config.get("types", ["narrative"]) if t != type_a] or config.get("types", ["narrative"]))
    pass_idx_d1 = (next_round - 1) * 3
    pass_idx_d2 = (next_round - 1) * 3 + 1
    temp_d1 = _get_temperature(config, pass_idx_d1)
    temp_d2 = _get_temperature(config, pass_idx_d2)

    fw_meta = config["frameworks"]
    seed = convergences[-1] if convergences else ""

    return {
        "status": "continue",
        "rounds_completed": rounds_completed,
        "convergence_history": convergences,
        "next_round": next_round,
        "seed": seed,
        "assignments": [
            {
                "framework": fw_a,
                "lens": fw_meta.get(fw_a, {}).get("lens", ""),
                "type": type_a,
                "temperature": temp_d1,
            },
            {
                "framework": fw_b,
                "lens": fw_meta.get(fw_b, {}).get("lens", ""),
                "type": type_b,
                "temperature": temp_d2,
            },
        ],
        "instructions": (
            f"Round {next_round}: Generate TWO independent readings of {session['chart_name']}'s chart.\n"
            f"SEED from previous convergence: \"{seed}\"\n"
            f"Each reading should explore this seed through its own lens — do NOT just restate it.\n"
            f"Reading 1: {fw_a} ({fw_meta.get(fw_a, {}).get('lens', '')}), {type_a}, temp {temp_d1}\n"
            f"Reading 2: {fw_b} ({fw_meta.get(fw_b, {}).get('lens', '')}), {type_b}, temp {temp_d2}\n"
            f"Submit each with autopoietic_submit(pass_type='diverge')."
        ),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DASHA & TIMING STACK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
async def get_timing_stack(
    name: str,
    target_date: Optional[str] = None,
    target_time: Optional[str] = None,
) -> str:
    """Get the full timing stack for a stored chart.

    Combines four timing systems:

    DASHA (Vimshottari, mathematical, birth-seeded):
      1. Maha — lord of the era (years-decades)
      2. Bhukti — lord of the season (months-years)
      3. Pratyantara — lord of the push (weeks-months)
      4. Sookshma — lord of the day (days-weeks)
      5. Prana — lord of the hour (hours)

    ZODIACAL RELEASING (Hellenistic, lot-based):
      Spirit (career/action) and Fortune (body/circumstances)
      L1-L5 periods with peak detection and loosing of the bond

    NAKSHATRA TRANSIT (astronomical, live Moon position):
      6. Nakshatra lord — the day quality (~24 hours)
      7. Pada — the sub-quality (~6 hours): Dharma/Artha/Kama/Moksha

    KI (solar-terrestrial cascade):
      Year / Month / Day / Hour

    Also detects resonances (e.g., transit Moon in same lord's nakshatra
    as a dasha level).

    Vimshottari lord sequence: Ketu(7), Venus(20), Sun(6), Moon(10),
    Mars(7), Rahu(18), Jupiter(16), Saturn(19), Mercury(17) = 120 years.

    Args:
        name: Chart name (e.g., 'chris', 'lisa', 'betsy')
        target_date: YYYY-MM-DD (default: today)
        target_time: HH:MM:SS (default: now)
    """
    from dasha import get_full_timing_stack
    result = get_full_timing_stack(name, target_date, target_time)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def get_dasha_periods(
    name: str,
    target_date: Optional[str] = None,
    target_time: Optional[str] = None,
) -> str:
    """Get the 5-level Vimshottari dasha stack for a stored chart.

    Returns maha through prana dashas with lord, position (1-9),
    start/end dates, and duration. Uses natal Moon nakshatra to
    seed the sequence.

    Vimshottari lord sequence (nakshatra order):
      1=Ketu(7yr), 2=Venus(20yr), 3=Sun(6yr), 4=Moon(10yr),
      5=Mars(7yr), 6=Rahu(18yr), 7=Jupiter(16yr), 8=Saturn(19yr),
      9=Mercury(17yr). Total = 120 years.

    Each sub-level divides the parent period proportionally by the
    same 9 lords starting from the parent's lord.

    Args:
        name: Chart name (e.g., 'chris', 'lisa')
        target_date: YYYY-MM-DD (default: today)
        target_time: HH:MM:SS (default: now)
    """
    from dasha import get_full_timing_stack
    import os as _os

    chart_path = _os.path.join(_os.path.dirname(__file__) or '.', 'charts', f'{name}.json')
    if not _os.path.exists(chart_path):
        return json.dumps({'error': f'Chart not found: {name}'})

    with open(chart_path) as f:
        chart = json.load(f)

    birth_data = chart.get('birthData', {})
    birth_date = birth_data.get('date')
    moon_planet = next((p for p in chart.get('planets', []) if p['name'] == 'Moon'), None)
    if not birth_date or not moon_planet:
        return json.dumps({'error': 'Chart missing birth date or Moon data'})

    from dasha import compute_dasha_stack
    result = compute_dasha_stack(birth_date, float(moon_planet['longitude']),
                                 target_date, target_time)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def get_nakshatra_transit(
    target_date: Optional[str] = None,
    target_time: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> str:
    """Get the Moon's current nakshatra position as a live transit layer.

    Returns the nakshatra name, number (1-27), dasha lord, pada (1-4),
    pada aim (Dharma/Artha/Kama/Moksha), entry/exit times, and duration.

    This is levels 6-7 of the timing stack — the astronomical layer
    determined by where the Moon actually is right now.

    Each nakshatra = 13°20' of ecliptic. Each pada = 3°20'.
    Moon transits one nakshatra in roughly 24 hours, one pada in ~6 hours.

    Args:
        target_date: YYYY-MM-DD (default: today)
        target_time: HH:MM (default: now)
        lat: Latitude (default: 28.5383 / Orlando)
        lon: Longitude (default: -81.3792 / Orlando)
    """
    from dasha import get_current_nakshatra_transit
    kwargs = {}
    if target_date:
        kwargs['target_date'] = target_date
    if target_time:
        kwargs['target_time'] = target_time
    if lat is not None:
        kwargs['lat'] = lat
    if lon is not None:
        kwargs['lon'] = lon
    result = get_current_nakshatra_transit(**kwargs)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def get_ki_changes(
    target_date: str = None,
    birth_date: str = None,
    include_gnostic: bool = False,
) -> str:
    """Compute Ki changes at all levels — Mercury's reading of the Ki field.

    Shows what's transitioning, not just what IS. For each Ki level
    (synodic, year, month, day, hour):
    - Current and next Ki number with trigram
    - When it changes next
    - Changing lines (trigram transitions, yin→yang / yang→yin)
    - Wu Xing phase relationship of the transition

    For each adjacent pair of levels, forms the I Ching hexagram
    (lower trigram = slower/stable level, upper = faster/changing level)
    with King Wen sequence number.

    Optionally looks up Gnostic Book of Changes interpretations for
    each hexagram formed.

    Args:
        target_date: ISO date YYYY-MM-DD (default: now)
        birth_date: Birth date YYYY-MM-DD for personal Ki overlay
        include_gnostic: If True, look up Gnostic I Ching text for each hexagram
    """
    from ki_changes import (
        get_ki_changes as _get_ki_changes,
        format_ki_changes as _format,
        format_ki_changes_full as _format_full,
    )
    data = _get_ki_changes(target_date=target_date, birth_date=birth_date)

    if include_gnostic:
        return _format_full(data, personal=bool(birth_date))
    else:
        return _format(data)


@mcp.tool()
async def get_ki_change_schedule(
    birth_date: str = None,
    level: str = "day",
    count: int = 9,
) -> str:
    """Show the next N Ki changes at a specific level with hexagram transitions.

    Useful for seeing the rhythm of changes — when does Ki cycle through
    all 9 numbers? What hexagrams form along the way?

    Args:
        birth_date: Birth date YYYY-MM-DD for personal Ki
        level: Which level to track: 'hour', 'day', 'month', 'year'
        count: Number of upcoming changes to show (default 9 = one full cycle)
    """
    from ki_changes import get_ki_changes as _get_ki_changes, _changing_lines, _hexagram_from_ki, KI_TO_TRIGRAM
    from convergence_ki import _flying_star, _year_ki
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/New_York")
    now = datetime.now(tz)

    if level not in ("hour", "day", "month", "year"):
        return f"Invalid level '{level}'. Use: hour, day, month, year"

    # Get current state
    data = _get_ki_changes(birth_date=birth_date)
    current_ki = data["global"]["current"][level]

    lines = []
    lines.append(f"═══ KI CHANGE SCHEDULE — {level.upper()} ═══")
    lines.append(f"Starting: Ki {current_ki} {KI_TO_TRIGRAM[current_ki]['symbol']} {KI_TO_TRIGRAM[current_ki]['name']}")
    lines.append(f"Next {count} changes:\n")

    ki = current_ki
    # Determine step interval
    if level == "hour":
        step = timedelta(hours=2)
    elif level == "day":
        step = timedelta(days=1)
    elif level == "month":
        step = timedelta(days=30)  # approximate
    elif level == "year":
        step = timedelta(days=365)

    cursor = now
    natal_yki = None
    if birth_date:
        from datetime import date
        bd = date.fromisoformat(birth_date)
        natal_yki = _year_ki(bd.year, bd.month, bd.day)

    for i in range(count):
        next_ki = (ki - 1) % 9
        if next_ki <= 0:
            next_ki += 9

        change = _changing_lines(ki, next_ki)
        changes_str = ", ".join(
            f"L{c['line']} {c['direction']}" for c in change["changing_lines"]
        ) if change["num_changes"] > 0 else "same trigram"

        cursor += step
        line = (f"  {i+1}. Ki {ki} {KI_TO_TRIGRAM[ki]['symbol']}"
                f" → {next_ki} {KI_TO_TRIGRAM[next_ki]['symbol']}"
                f"  [{changes_str}]")

        if natal_yki:
            p_curr = _flying_star(natal_yki, ki)
            p_next = _flying_star(natal_yki, next_ki)
            line += f"  (personal: {p_curr}→{p_next})"

        lines.append(line)
        ki = next_ki

    lines.append(f"\n9 changes = one full cycle. Ki descends by 1 each {level}.")
    return "\n".join(lines)


# ── Individual Ki change tools (one per level) ──

def _ki_change_single_level(level: str, birth_date: str = None,
                             include_gnostic: bool = False) -> str:
    """Shared implementation for individual Ki change level tools.

    When include_gnostic=True, uses the full format with line diagrams,
    changing lines, transformed hexagram, and Gnostic I Ching text including
    all translator versions, Editor commentary, and lettered statements.
    """
    from ki_changes import (
        get_ki_changes as _get_ki_changes,
        format_ki_changes_full as _format_full,
        _changing_lines, _hexagram_from_ki, _wu_xing_relationship,
        KI_TO_TRIGRAM, lookup_hexagram_gnostic, LEVEL_NAMES,
        _get_transformed_hex,
    )
    from convergence_ki import TRIAD_OF

    data = _get_ki_changes(birth_date=birth_date)

    # If gnostic requested, use the full format filtered to this level's pairs
    if include_gnostic:
        # Use full format but we'll build it for just this level
        use_personal = bool(birth_date) and data.get("personal")

        if use_personal:
            p = data["personal"]
            ki_current = p["current"]
            ki_next = p["next"]
            hex_source = p.get("hexagrams", {})
        else:
            ki_current = data["global"]["current"]
            ki_next = data["global"]["next"]
            hex_source = data.get("hexagrams", {})

        pair_map = {
            "synodic": [("synodic", "year", "synodic_year")],
            "year": [("synodic", "year", "synodic_year"), ("year", "month", "year_month")],
            "month": [("year", "month", "year_month"), ("month", "day", "month_day")],
            "day": [("month", "day", "month_day"), ("day", "hour", "day_hour")],
            "hour": [("day", "hour", "day_hour")],
        }

        lines = []
        lines.append(f"═══ KI CHANGE — {level.upper()} ═══")

        # Show current level info
        lc = data["level_changes"][level] if not use_personal else p["level_changes"].get(level, data["level_changes"][level])
        curr = lc["current"]
        nxt = lc["next"]
        lines.append(f"  Current: {curr['ki']} {curr['symbol']} {curr['trigram']} ({TRIAD_OF[curr['ki']]})")
        lines.append(f"  Next:    {nxt['ki']} {nxt['symbol']} {nxt['trigram']} ({TRIAD_OF[nxt['ki']]})")
        lines.append(f"  Changes: {lc['changes_at']}")
        lines.append("")

        for lower_name, upper_name, pair_key in pair_map.get(level, []):
            if pair_key not in hex_source:
                continue

            hx = hex_source[pair_key]
            lower_ki = hx["lower"]["ki"]
            upper_ki = hx["upper"]["ki"]
            next_upper_ki = ki_next.get(upper_name)
            if next_upper_ki is None:
                continue

            lower_tri = KI_TO_TRIGRAM[lower_ki]
            upper_tri = KI_TO_TRIGRAM[upper_ki]
            next_upper_tri = KI_TO_TRIGRAM[next_upper_ki]

            hex_lines_val = lower_tri["lines"] + upper_tri["lines"]
            next_hex_lines = lower_tri["lines"] + next_upper_tri["lines"]

            changing = []
            for i in range(6):
                if hex_lines_val[i] != next_hex_lines[i]:
                    direction = "yin→yang" if next_hex_lines[i] == 1 else "yang→yin"
                    changing.append({"line": i + 1, "direction": direction})

            transformed_num = _get_transformed_hex(lower_ki, next_upper_ki)

            lines.append(f"{'═' * 60}")
            lines.append(f"HEXAGRAM {hx['hexagram']} — {lower_name.upper()}/{upper_name.upper()}")
            lines.append(f"  {upper_tri['symbol']} {upper_tri['name']} above  (Ki {upper_ki})")
            lines.append(f"  {lower_tri['symbol']} {lower_tri['name']} below  (Ki {lower_ki})")
            lines.append(f"  Wu Xing: {hx.get('wu_xing', '')}")
            lines.append("")

            for i in range(5, -1, -1):
                val = hex_lines_val[i]
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

            # Gnostic lookup
            cl = [c["line"] for c in changing] if changing else None
            gnostic = lookup_hexagram_gnostic(hx["hexagram"], changing_lines=cl)

            if gnostic.get("judgment"):
                lines.append(f"  JUDGMENT:")
                for jl in gnostic["judgment"][:800].split("\n"):
                    lines.append(f"  {jl}")
                lines.append("")

            if gnostic.get("line_readings"):
                for line_num, reading in sorted(gnostic["line_readings"].items()):
                    lines.append(f"  ── LINE {line_num} ──")
                    for rl in reading.split("\n"):
                        lines.append(f"  {rl}")
                    lines.append("")

            lines.append("")

        return "\n".join(lines)

    # Non-gnostic compact format (original)
    g = data["global"]
    lc = data["level_changes"][level]

    lines = []
    curr = lc["current"]
    nxt = lc["next"]
    lines.append(f"═══ KI CHANGE — {level.upper()} ═══")
    lines.append(f"  Current: {curr['ki']} {curr['symbol']} {curr['trigram']} ({TRIAD_OF[curr['ki']]})")
    lines.append(f"  Next:    {nxt['ki']} {nxt['symbol']} {nxt['trigram']} ({TRIAD_OF[nxt['ki']]})")
    lines.append(f"  Changes: {lc['changes_at']}")
    lines.append(f"  Wu Xing: {lc['wu_xing']}")

    if lc["num_changes"] > 0:
        ch_str = ", ".join(f"L{c['line']} {c['direction']}" for c in lc["changing_lines"])
        lines.append(f"  Lines:   {ch_str}")
    else:
        lines.append(f"  Lines:   no change (same trigram)")

    lines.append("")
    lines.append("── HEXAGRAMS ──")

    pair_map = {
        "synodic": [("synodic", "year", "synodic_year")],
        "year": [("synodic", "year", "synodic_year"), ("year", "month", "year_month")],
        "month": [("year", "month", "year_month"), ("month", "day", "month_day")],
        "day": [("month", "day", "month_day"), ("day", "hour", "day_hour")],
        "hour": [("day", "hour", "day_hour")],
    }

    for lower_name, upper_name, pair_key in pair_map.get(level, []):
        if pair_key in data["hexagrams"]:
            hx = data["hexagrams"][pair_key]
            lines.append(f"  {hx['pair']}:")
            lines.append(f"    {hx['upper']['symbol']} {hx['upper']['trigram']} above  (Ki {hx['upper']['ki']})")
            lines.append(f"    {hx['lower']['symbol']} {hx['lower']['trigram']} below  (Ki {hx['lower']['ki']})")
            lines.append(f"    = Hexagram {hx['hexagram']}  |  {hx['wu_xing']}")
            lines.append("")

    if data.get("personal"):
        p = data["personal"]
        lines.append("── PERSONAL ──")
        if level in p.get("level_changes", {}):
            plc = p["level_changes"][level]
            pc = plc["current"]
            pn = plc["next"]
            lines.append(f"  Current: {pc['ki']} {pc['symbol']} {pc['trigram']}")
            lines.append(f"  Next:    {pn['ki']} {pn['symbol']} {pn['trigram']}")
            lines.append(f"  Wu Xing: {plc['wu_xing']}")
            if plc["num_changes"] > 0:
                ch_str = ", ".join(f"L{c['line']} {c['direction']}" for c in plc["changing_lines"])
                lines.append(f"  Lines:   {ch_str}")

        if p.get("hexagrams"):
            for lower_name, upper_name, pair_key in pair_map.get(level, []):
                if pair_key in p["hexagrams"]:
                    hx = p["hexagrams"][pair_key]
                    lines.append(f"  Personal {hx['pair']}: Hex {hx['hexagram']}"
                                  f" ({hx['lower']['symbol']}/{hx['upper']['symbol']})")

    return "\n".join(lines)


@mcp.tool()
async def ki_change_hour(
    birth_date: str = None,
    include_gnostic: bool = False,
) -> str:
    """Ki change at the HOUR level — fastest cycle (~2 hours per shift).

    Shows current hour Ki, what it's becoming, when it changes,
    the changing lines, and hexagrams formed with the day level.
    Hour = the ascendant's rhythm, Mercury's most rapid pulse.

    Args:
        birth_date: Birth date YYYY-MM-DD for personal Ki
        include_gnostic: Pull Gnostic I Ching text for hexagrams
    """
    return _ki_change_single_level("hour", birth_date, include_gnostic)


@mcp.tool()
async def ki_change_day(
    birth_date: str = None,
    include_gnostic: bool = False,
) -> str:
    """Ki change at the DAY level — daily solar rhythm.

    Shows current day Ki, what it's becoming at midnight,
    the changing lines, and hexagrams formed with month and hour levels.
    Day = the Sun's daily pulse through the -3 cascade from Lichun.

    Args:
        birth_date: Birth date YYYY-MM-DD for personal Ki
        include_gnostic: Pull Gnostic I Ching text for hexagrams
    """
    return _ki_change_single_level("day", birth_date, include_gnostic)


@mcp.tool()
async def ki_change_month(
    birth_date: str = None,
    include_gnostic: bool = False,
) -> str:
    """Ki change at the MONTH level — solar month (~30 days per shift).

    Shows current month Ki, what it's becoming when Sun crosses
    the next 30° boundary, changing lines, and hexagrams formed
    with year and day levels.

    Args:
        birth_date: Birth date YYYY-MM-DD for personal Ki
        include_gnostic: Pull Gnostic I Ching text for hexagrams
    """
    return _ki_change_single_level("month", birth_date, include_gnostic)


@mcp.tool()
async def ki_change_year(
    birth_date: str = None,
    include_gnostic: bool = False,
) -> str:
    """Ki change at the YEAR level — annual cycle (changes at Lichun ~Feb 4).

    Shows current year Ki, what it's becoming next Lichun,
    the changing lines, and hexagrams formed with synodic and month levels.
    Year = the Sun's annual pulse, the foundational Ki number.

    Args:
        birth_date: Birth date YYYY-MM-DD for personal Ki
        include_gnostic: Pull Gnostic I Ching text for hexagrams
    """
    return _ki_change_single_level("year", birth_date, include_gnostic)


@mcp.tool()
async def ki_change_global(
    birth_date: str = None,
    include_gnostic: bool = False,
) -> str:
    """Ki change at the SYNODIC (global) level — Jupiter's ~12-year cycle.

    Shows current synodic Ki, what it's becoming at the next
    Jupiter perihelion gate, and the hexagram formed with the year level.
    Synodic = the slowest Ki pulse, the Great Year (~108 years for full cycle).

    Args:
        birth_date: Birth date YYYY-MM-DD for personal Ki
        include_gnostic: Pull Gnostic I Ching text for hexagrams
    """
    return _ki_change_single_level("synodic", birth_date, include_gnostic)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MOON SQUARE DAILY NAKSHATRA TRACKER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_MOON_SQUARE = [
    [37,78,29,70,21,62,13,54,5],
    [6,38,79,30,71,22,63,14,46],
    [47,7,39,80,31,72,23,55,15],
    [16,48,8,40,81,32,64,24,56],
    [57,17,49,9,41,73,33,65,25],
    [26,58,18,50,1,42,74,34,66],
    [67,27,59,10,51,2,43,75,35],
    [36,68,19,60,11,52,3,44,76],
    [77,28,69,20,61,12,53,4,45],
]

_MOON_NAKSHATRAS = [
    ("Ashwini", "☋Ketu"),      ("Bharani", "♀Venus"),
    ("Krittika", "☉Sun"),      ("Rohini", "☽Moon"),
    ("Mrigashira", "♂Mars"),   ("Ardra", "☊Rahu"),
    ("Punarvasu", "♃Jupiter"), ("Pushya", "♄Saturn"),
    ("Ashlesha", "☿Mercury"),  ("Magha", "☋Ketu"),
    ("Purva Phalguni", "♀Venus"), ("Uttara Phalguni", "☉Sun"),
    ("Hasta", "☽Moon"),        ("Chitra", "♂Mars"),
    ("Swati", "☊Rahu"),        ("Vishakha", "♃Jupiter"),
    ("Anuradha", "♄Saturn"),   ("Jyeshtha", "☿Mercury"),
    ("Mula", "☋Ketu"),         ("Purva Ashadha", "♀Venus"),
    ("Uttara Ashadha", "☉Sun"), ("Shravana", "☽Moon"),
    ("Dhanishta", "♂Mars"),    ("Shatabhisha", "☊Rahu"),
    ("Purva Bhadrapada", "♃Jupiter"), ("Uttara Bhadrapada", "♄Saturn"),
    ("Revati", "☿Mercury"),
]

_MOON_PADAS = ["Dharma", "Artha", "Kama"]  # 3 material padas

# Epoch: Lichun 2022 (start of current Great Year / synodic gate 8)
_MOON_SQUARE_EPOCH = datetime(2022, 2, 3).date()

# Build value → grid position map
_MOON_VAL_POS = {}
for _r in range(9):
    for _c in range(9):
        _MOON_VAL_POS[_MOON_SQUARE[_r][_c]] = (_r, _c)


def _moon_square_day(target_date=None):
    """Compute Moon square daily nakshatra position.

    The Moon's 9×9 magic square (81 cells) maps to 27 nakshatras × 3 material padas.
    Starting from Chitra (nakshatra 14, the center) at the Great Year epoch (Lichun 2022),
    the pointer advances by 3 cells per day through the walk order.
    Full cycle = 27 days. The walk starts at value 40 (first pada of Chitra).

    Returns dict with current position, nakshatra, grid coordinates, and cycle info.
    """
    if target_date is None:
        target_date = datetime.now().date()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()

    days_since = (target_date - _MOON_SQUARE_EPOCH).days
    cycle_day = days_since % 27  # 0-26
    full_cycles = days_since // 27

    # Walk values: starting from 40, advance by 3 per day
    start_val = ((39 + days_since * 3) % 81) + 1
    vals = [((39 + days_since * 3 + i) % 81) + 1 for i in range(3)]

    # Nakshatra
    nak_idx = (13 + cycle_day) % 27  # 0-based, starts at Chitra (13)
    nak_name, nak_lord = _MOON_NAKSHATRAS[nak_idx]

    # Grid positions for the 3 values
    positions = []
    for v in vals:
        r, c = _MOON_VAL_POS[v]
        positions.append({"value": v, "row": r, "col": c,
                          "pada": _MOON_PADAS[(v - 1) % 3]})

    # Digital root of center value
    center_val = vals[1]  # middle of the 3
    dr = (center_val - 1) % 9 + 1

    return {
        "date": target_date.isoformat(),
        "days_since_epoch": days_since,
        "cycle": {
            "day_in_cycle": cycle_day,
            "full_cycles_completed": full_cycles,
            "cycle_length_days": 27,
            "epoch": _MOON_SQUARE_EPOCH.isoformat(),
            "epoch_event": "Lichun 2022 (Great Year gate 8, Gen ☶ Mountain)",
        },
        "nakshatra": {
            "number": nak_idx + 1,
            "name": nak_name,
            "lord": nak_lord,
        },
        "walk_values": vals,
        "padas": [
            {"value": p["value"], "pada": p["pada"],
             "grid": f"[{p['row']},{p['col']}]"}
            for p in positions
        ],
        "digital_root": dr,
        "grid_positions": positions,
    }


@mcp.tool()
async def get_moon_square_transit(
    name: str = None,
    target_date: str = None,
    target_time: str = None,
) -> str:
    """Moon Square daily dasha transit — where is the Moon in the grid right now?

    Uses the ACTUAL Moon's nakshatra position (no epoch, no drift) to determine
    which cells and dasha lord territory the Moon is activating in the 9×9 grid.
    If a name is given (stored chart), shows how the transit relates to the
    person's active maha dasha and bhukti.

    Each nakshatra = 3 cells in the Moon square. Each dasha lord owns 9 cells
    (3 nakshatras). The Moon transits one nakshatra per ~day, activating a
    different lord's territory daily.

    Args:
        name: Person's chart name (for dasha context). Optional.
        target_date: YYYY-MM-DD (default today)
        target_time: HH:MM (default now)
    """
    from dasha import get_current_nakshatra_transit, compute_dasha_stack

    # Get actual Moon position
    kwargs = {}
    if target_date:
        kwargs['target_date'] = target_date
    if target_time:
        kwargs['target_time'] = target_time
    transit = get_current_nakshatra_transit(**kwargs)

    nak_num = transit['nakshatra']['number']
    nak_name = transit['nakshatra']['name']
    nak_lord = transit['nakshatra']['lord']
    pada_num = transit['pada']['number']
    pada_aim = transit['pada']['aim']

    # Map to Moon square
    lord_idx = (nak_num - 1) % 9
    transit_lord = _MOON_NAKSHATRAS[(nak_num - 1)][1]  # lord with glyph
    base_cell = (nak_num - 1) * 3 + 1
    cells = [base_cell, base_cell + 1, base_cell + 2]

    # Current pada → active cell (pada 4 = moksha, off-grid)
    if pada_num <= 3:
        active_cell = base_cell + (pada_num - 1)
        active_pada = _MOON_PADAS[pada_num - 1]
    else:
        active_cell = None
        active_pada = "Moksha (off-grid)"

    # Grid positions
    cell_positions = []
    for c in cells:
        r, col = _MOON_VAL_POS[c]
        cell_positions.append({"value": c, "row": r, "col": col})

    # Digital root of active cell
    dr = ((active_cell - 1) % 9 + 1) if active_cell else None

    lines = []
    lines.append(f"☽ Moon Square Transit — {transit['moon']['degree']}")
    lines.append(f"")
    lines.append(f"  Nakshatra: {nak_name} (#{nak_num}) — {transit_lord}")
    lines.append(f"  Pada: {pada_num} ({pada_aim})")
    lines.append(f"  Grid cells: {cells}")
    if active_cell:
        r, col = _MOON_VAL_POS[active_cell]
        lines.append(f"  Active cell: {active_cell} at [{r},{col}] ({active_pada}) DR={dr}")
    else:
        lines.append(f"  Pada 4 (Moksha) — unbuffered, off the grid")
    lines.append(f"  Entered: {transit['nakshatra']['entered']}")
    lines.append(f"  Exits:   {transit['nakshatra']['exits']}")

    # Personal dasha context
    if name:
        try:
            chart = _load_local_chart(name)
            if chart:
                bd = chart.get('birthData', {})
                birth_date = bd.get('date', chart.get('date', ''))
                moon_lon = chart.get('moon_lon')

                # If no moon_lon stored, try to compute from natal chart
                if moon_lon is None:
                    # Try planets list
                    planets = chart.get('planets', [])
                    for p in planets:
                        if p.get('name', '').lower() == 'moon':
                            moon_lon = p.get('longitude', p.get('lon'))
                            break

                if moon_lon is not None:
                    dasha_result = compute_dasha_stack(birth_date, float(moon_lon))
                    if dasha_result and 'stack' in dasha_result:
                        levels = dasha_result['stack']
                        maha = levels[0]
                        bhukti = levels[1] if len(levels) > 1 else None

                        lines.append(f"")
                        lines.append(f"  ── {name}'s Dasha Context ──")
                        lines.append(f"  Maha: {maha['glyph']}{maha['lord']} ({maha['start'][:10]}→{maha['end'][:10]})")
                        if bhukti:
                            lines.append(f"  Bhukti: {bhukti['glyph']}{bhukti['lord']} ({bhukti['start'][:10]}→{bhukti['end'][:10]})")

                        # Check transit-dasha relationship
                        transit_lord_name = nak_lord
                        if transit_lord_name == maha['lord']:
                            lines.append(f"  ★ Moon transiting YOUR maha dasha lord's territory")
                        elif bhukti and transit_lord_name == bhukti['lord']:
                            lines.append(f"  ★ Moon transiting YOUR bhukti lord's territory")
                        else:
                            lines.append(f"  Moon transiting {nak_lord}'s territory")
                else:
                    lines.append(f"  (No natal Moon longitude found for {name})")
        except Exception as e:
            lines.append(f"  (Could not load dasha for {name}: {e})")

    return "\n".join(lines)


@mcp.tool()
async def get_moon_square_day(
    target_date: str = None,
    range_days: int = 0,
) -> str:
    """Moon Square daily nakshatra tracker.

    The Moon's 9×9 magic square cycles through 27 nakshatras, advancing 3 cells
    per day from the Chitra center. Epoch: Lichun 2022 (Great Year gate boundary).
    Full cycle = 27 days.

    Args:
        target_date: Date to compute for (YYYY-MM-DD, default today)
        range_days: Show surrounding days (-N to +N). 0 = just target date.
                    Max 27 (full cycle).

    Returns:
        Current Moon square position with nakshatra, walk values, grid coordinates.
    """
    from datetime import timedelta

    if target_date:
        base = datetime.strptime(target_date, "%Y-%m-%d").date()
    else:
        base = datetime.now().date()

    range_days = min(abs(range_days), 27)

    if range_days == 0:
        result = _moon_square_day(base)
        lines = []
        lines.append(f"☽ Moon Square — {result['date']}")
        lines.append(f"Cycle day {result['cycle']['day_in_cycle']}/27 "
                      f"(cycle #{result['cycle']['full_cycles_completed'] + 1})")
        lines.append("")
        nak = result['nakshatra']
        lines.append(f"  Nakshatra {nak['number']}: {nak['name']} ({nak['lord']})")
        lines.append(f"  Walk values: {result['walk_values']}")
        for p in result['padas']:
            lines.append(f"    {p['value']:2d} → {p['grid']} ({p['pada']})")
        lines.append(f"  Digital root: {result['digital_root']}")
        return "\n".join(lines)
    else:
        lines = [f"☽ Moon Square — {range_days*2+1} days around {base.isoformat()}", ""]
        for d in range(-range_days, range_days + 1):
            dt = base + timedelta(days=d)
            r = _moon_square_day(dt)
            nak = r['nakshatra']
            marker = " ◄" if d == 0 else ""
            lines.append(
                f"  {r['date']}  cycle {r['cycle']['day_in_cycle']:2d}  "
                f"{nak['name']:22s} ({nak['lord']:10s})  "
                f"vals {r['walk_values']}{marker}"
            )
        return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MOON SQUARE — TAO TE CHING READING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_TTC_CHAPTERS = None


def _load_ttc():
    """Load Tao Te Ching chapters (Hinton translation) from JSON."""
    global _TTC_CHAPTERS
    if _TTC_CHAPTERS is None:
        ttc_path = STELLA_DIR / "tao_te_ching.json"
        if ttc_path.exists():
            with open(ttc_path) as f:
                _TTC_CHAPTERS = json.load(f)
        else:
            _TTC_CHAPTERS = {}
    return _TTC_CHAPTERS


def _ttc_chapter_for_nakshatra(nak_num: int) -> int:
    """Given a nakshatra number (1-27), return the TTC chapter.

    The Moon's walk starts at Chitra (nakshatra 14) = walk steps 40, 41, 42.
    Each nakshatra offset = +3 walk steps. The center step (middle pada)
    maps directly to a Tao Te Ching chapter (1-81).
    """
    offset = (nak_num - 14) % 27
    center_step = ((41 - 1 + offset * 3) % 81) + 1
    return center_step


@mcp.tool()
async def get_moon_tao(
    target_date: str = None,
    range_days: int = 0,
    name: str = None,
) -> str:
    """Moon Square × Tao Te Ching daily reading.

    The Moon transits one nakshatra per day (~13°/day through 13°20' divisions).
    Each nakshatra maps to 3 walk steps in the 9×9 Moon square, starting from
    Chitra (center). The center step = a Tao Te Ching chapter (Hinton translation).

    Shows today's chapter with flanking chapters (previous and next padas)
    as context. Uses the Moon's ACTUAL sidereal position, not the epoch cycle.

    Args:
        target_date: Date for reading (YYYY-MM-DD, default today)
        range_days: Show surrounding days (0-13). 0 = just target.
        name: Chart name for natal Moon nakshatra context (optional)

    Returns:
        Daily TTC reading based on Moon's nakshatra position.
    """
    import swisseph as swe
    swe.set_ephe_path("/mnt/baratie/baratie/sweph-service/ephemeris")

    ttc = _load_ttc()
    if not ttc:
        return "Error: tao_te_ching.json not found in stella directory."

    if target_date:
        base = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base = datetime.now()

    range_days = min(abs(range_days), 13)

    # Lahiri ayanamsa for sidereal
    jd_base = _datetime_to_jd(base)

    def _reading_for_jd(jd):
        moon_lon = swe.calc_ut(jd, swe.MOON)[0][0]
        ayan = swe.get_ayanamsa_ut(jd)
        sid = (moon_lon - ayan) % 360
        nak_num = int(sid / (360 / 27)) + 1  # 1-27
        pada = int((sid % (360 / 27)) / (360 / 108)) + 1  # 1-4
        nak_name = _MOON_NAKSHATRAS[nak_num - 1][0]
        nak_lord = _MOON_NAKSHATRAS[nak_num - 1][1]

        chapter = _ttc_chapter_for_nakshatra(nak_num)
        # Flanking chapters (previous and next walk steps)
        left_ch = ((chapter - 2) % 81) + 1
        right_ch = (chapter % 81) + 1

        return {
            "nak_num": nak_num,
            "nak_name": nak_name,
            "nak_lord": nak_lord,
            "pada": pada,
            "sid_deg": sid,
            "chapter": chapter,
            "left_chapter": left_ch,
            "right_chapter": right_ch,
        }

    def _format_chapter(ch_num, full=False):
        text = ttc.get(str(ch_num), f"(Chapter {ch_num} not available)")
        if full:
            return text
        # First 4 meaningful lines for flanks
        lines = [l for l in text.split("\n") if l.strip()]
        return "\n".join(lines[:4])

    if range_days == 0:
        # Single day — full reading with flanks
        r = _reading_for_jd(jd_base)
        lines = []
        lines.append("☽ Moon Square × Tao Te Ching")
        lines.append(f"  {base.strftime('%Y-%m-%d')}")
        lines.append(f"  Moon: {r['sid_deg']:.1f}° sidereal")
        lines.append(f"  Nakshatra {r['nak_num']}: {r['nak_name']} "
                      f"({r['nak_lord']}), Pada {r['pada']}")
        lines.append("")

        # Left flank
        lines.append(f"── Ch. {r['left_chapter']} (leaving) ──")
        lines.append(_format_chapter(r["left_chapter"]))
        lines.append("")

        # Center
        lines.append(f"══ Ch. {r['chapter']} (present) ══")
        lines.append(_format_chapter(r["chapter"], full=True))
        lines.append("")

        # Right flank
        lines.append(f"── Ch. {r['right_chapter']} (entering) ──")
        lines.append(_format_chapter(r["right_chapter"]))

        # Natal context if chart name given
        if name:
            try:
                chart = _load_local_chart(name)
                if chart:
                    natal_moon = None
                    for body in chart.get("planets", []):
                        if body.get("name") == "Moon":
                            natal_moon = body.get("longitude")
                            break
                    if natal_moon is not None:
                        ayan = swe.get_ayanamsa_ut(jd_base)
                        natal_sid = (natal_moon - ayan) % 360
                        natal_nak = int(natal_sid / (360 / 27)) + 1
                        natal_ch = _ttc_chapter_for_nakshatra(natal_nak)
                        natal_name = _MOON_NAKSHATRAS[natal_nak - 1][0]
                        lines.append("")
                        lines.append(f"── Natal Moon: {natal_name} "
                                      f"(#{natal_nak}) → Ch. {natal_ch} ──")
                        lines.append(_format_chapter(natal_ch))
            except Exception:
                pass

        return "\n".join(lines)
    else:
        # Range view
        lines = ["☽ Moon × Tao Te Ching — Daily Chapters", ""]
        from datetime import timedelta
        for d in range(-range_days, range_days + 1):
            dt = base + timedelta(days=d)
            jd = _datetime_to_jd(dt)
            r = _reading_for_jd(jd)
            first_line = ttc.get(str(r["chapter"]), "?").split("\n")[0]
            first_line = first_line.strip()
            if len(first_line) > 50:
                first_line = first_line[:47] + "..."
            marker = " ◄" if d == 0 else ""
            lines.append(
                f"  {dt.strftime('%b %d')}  "
                f"{r['nak_name']:22s}  "
                f"Ch.{r['chapter']:2d}  "
                f"\"{first_line}\"{marker}"
            )
        return "\n".join(lines)


def _datetime_to_jd(dt):
    """Convert datetime to Julian Day (noon-based, UT)."""
    import swisseph as swe
    if isinstance(dt, datetime):
        hour = dt.hour + dt.minute / 60 + dt.second / 3600
        return swe.julday(dt.year, dt.month, dt.day, hour)
    else:
        # date object, use noon
        return swe.julday(dt.year, dt.month, dt.day, 12.0)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SABIAN SYMBOLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SIGN_ORDER = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
              'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']


@mcp.tool()
async def get_sabian_symbol(
    sign: str,
    degree: int,
) -> str:
    """Get the Sabian Symbol for a specific zodiac degree.

    Args:
        sign: Zodiac sign (e.g. 'Taurus', 'Scorpio')
        degree: Degree within the sign (1-30)

    Returns:
        The Sabian Symbol image, interpretation, decan ruler, and pip card.
    """
    sign_cap = sign.strip().title()
    if sign_cap not in SIGN_ORDER:
        return f"Unknown sign: {sign}. Use full sign name (e.g. 'Aries', 'Pisces')."
    if not (1 <= degree <= 30):
        return f"Degree must be 1-30, got {degree}."

    rows = neo4j_query(
        "MATCH (s:SabianSymbol {sign: $sign, degree: $degree}) "
        "RETURN s.image as image, s.interpretation as interp, "
        "s.decan_ruler as decan_ruler, s.pip_card as pip_card, "
        "s.modality as modality, s.element as element, s.decan as decan",
        sign=sign_cap, degree=degree
    )
    if not rows:
        return f"No Sabian Symbol found for {sign_cap} {degree}°."

    r = rows[0]
    lines = [
        f"**{sign_cap} {degree}°**",
        f"*\"{r['image']}\"*",
        "",
        f"**Decan:** {r['decan']} ({r['decan_ruler']}) | **Pip:** {r['pip_card']} | **Modality:** {r['modality']} | **Element:** {r['element']}",
        "",
        r['interp'] or ""
    ]
    return "\n".join(lines)


@mcp.tool()
async def get_sabian_symbols_for_chart(
    name: str,
) -> str:
    """Get Sabian Symbols for all natal placements in a stored chart.

    Args:
        name: Chart name (e.g. 'chris', 'lisa', 'betsy')

    Returns:
        Sabian Symbol for each planet, ASC, and MC with image, decan ruler, and pip card.
    """
    # Load chart from Neo4j
    placements = neo4j_query(
        "MATCH (c:Chart {name: $name})-[:HAS_PLACEMENT]->(p:NatalPlacement) "
        "RETURN p.body as body, p.sign as sign, p.degree as degree, p.minutes as minutes "
        "ORDER BY CASE p.body "
        "  WHEN 'Sun' THEN 0 WHEN 'Moon' THEN 1 WHEN 'Mercury' THEN 2 "
        "  WHEN 'Venus' THEN 3 WHEN 'Mars' THEN 4 WHEN 'Jupiter' THEN 5 "
        "  WHEN 'Saturn' THEN 6 WHEN 'Uranus' THEN 7 WHEN 'Neptune' THEN 8 "
        "  WHEN 'Pluto' THEN 9 WHEN 'ASC' THEN 10 WHEN 'MC' THEN 11 "
        "  WHEN 'North Node' THEN 12 WHEN 'South Node' THEN 13 "
        "  ELSE 20 END",
        name=name.strip().lower()
    )
    if not placements:
        return f"No chart found for '{name}'. Use list_stored_charts to see available charts."

    lines = [f"# Sabian Symbols — {name.title()}'s Chart\n"]

    for p in placements:
        body = p['body']
        sign = p['sign']
        deg_raw = p.get('degree', 0)
        minutes = p.get('minutes', 0)

        # Sabian tradition: round up (any minutes = next degree)
        # Sabian degree 1 = 0°00'-0°59', degree 30 = 29°00'-29°59'
        sabian_deg = int(deg_raw) + 1 if int(deg_raw) < 30 else 30
        # If degree is already integer and minutes > 0, we're in the next Sabian degree
        # If degree is 0 with 0 minutes, Sabian degree = 1

        rows = neo4j_query(
            "MATCH (s:SabianSymbol {sign: $sign, degree: $degree}) "
            "RETURN s.image as image, s.decan_ruler as decan_ruler, s.pip_card as pip_card",
            sign=sign, degree=sabian_deg
        )

        if rows:
            r = rows[0]
            lines.append(
                f"**{body}** {sign} {deg_raw}°{minutes:02d}' → "
                f"*{r['image'][:80]}{'…' if len(r['image']) > 80 else ''}* "
                f"({r['decan_ruler']}, {r['pip_card']})"
            )
        else:
            lines.append(f"**{body}** {sign} {deg_raw}°{minutes:02d}' → (no symbol found)")

    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    import asyncio

    # Try to discover additional sweph endpoints before starting
    try:
        asyncio.get_event_loop().run_until_complete(discover_and_register())
    except Exception as e:
        print(f"[stella] Startup discovery skipped: {e}", file=sys.stderr)

    mcp.run(transport="stdio")
