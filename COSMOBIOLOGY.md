# Cosmobiology in Stella — Design Outline

## Overview

Cosmobiology (Reinhold Ebertin's system) uses the **90° dial** and **midpoint structures** as its primary interpretive framework. Unlike house-based astrology, it focuses purely on geometric relationships between planetary positions.

**Knowledge source**: Ebertin's *The Combination of Stellar Influences* (COSI), now ingested — 78 midpoint pairs in ChromaDB + structured JSON lookup.

---

## 1. Cosmobiogram (Chart Type)

A **Cosmobiogram** is a natal chart rendered on the 90° dial. It's a standalone chart type in the workflow (Step 2).

### What it produces:

**A. Midpoint Sort (the foundation)**
For each planet/point in the chart, list its midpoint position on the 90° dial, sorted. This is the raw data.

```
Planet    Zodiac Position    90° Position
Sun       Taurus 11°04'      11°04'
Moon      Aquarius 19°01'    19°01'
Mercury   Aries 20°04'       20°04'
Mars      Capricorn 27°00'   27°00'
...
```

**B. Midpoint Trees**
For each planet, which midpoints does it activate? (within orb — typically 1.5° on the 90° dial)

```
Jupiter 5°09' (90°) activates:
  = Sun/Venus (midpoint at 8°33' — orb 3°24' ❌ too wide)
  = Venus/MC  (midpoint at 2°31' — orb 2°38' ❌)
  ...
```

Only direct hits (conjunction on the 90° dial = conjunction, square, or opposition in the zodiac).

**C. Midpoint Pictures**
The interpretive output. For each activated midpoint, pull Ebertin's delineation + synthesize with dignity/depositor context.

```
Mars = Sun/Saturn
  Ebertin: "The living being is strongly influenced by inhibition and
  separation. Hard work, the tendency to be austere."
  
  Dignity context: Mars exalted (+8) in Capricorn 5H — this inhibition
  is channeled into disciplined creative mastery. Not weakness, but 
  controlled force.
```

### Calculation (new Stella tool: `get_midpoint_pictures`)

**Input**: chart name (or raw positions)
**Process**:
1. Get all planet positions from stored chart / Helios
2. Convert each to 90° dial position: `pos_90 = zodiac_position % 90`
3. Calculate all pair midpoints: `mid = ((pos_a + pos_b) / 2) % 90` (handle wrap)
4. For each planet, check which midpoints it conjuncts on the 90° dial (orb ≤ 1.5°)
5. For each hit: pull Ebertin delineation from JSON lookup, pull dignity context from chart data
6. Return structured output

**Where the math lives**: **Stella** (Python). Helios stays stateless — it gives positions, Stella does the midpoint math. This is consistent with the existing architecture (Helios = ephemeris, Stella = interpretation).

---

## 2. Cosmobiological Framework (Step 3)

When selected as a **framework** (not type), midpoint pictures become the structural skeleton of the reading, with dignities/depositors/houses layered in.

### How it differs from using it as a Type:
- **Type = Cosmobiogram**: Output IS the midpoint analysis. 90° dial format, midpoint trees, Ebertin delineations. Technical.
- **Framework = Cosmobiological**: Midpoints organize the narrative, but the prose is full-spectrum interpretation. Ebertin's meanings get synthesized with house topics, dignity states, sect, depositors.

### Narrative structure when Cosmobiological framework:
1. **Dominant midpoint pictures** — the 2-3 tightest activations define the core personality
2. **Each section organized by activated planet**, not by planet-in-sign
3. **Dignity state modifies Ebertin's keywords** — exalted Mars = controlled; debilitated Mars = frustrated
4. **Depositor chains show HOW midpoints express** — where does the energy flow?

---

## 3. +Midpoints Add-on (Step 5)

Appends natal midpoint analysis to any reading type. Lighter than full Cosmobiogram — just the most significant pictures (tightest orbs, personal planet activations).

### Output:
- Top 5-10 midpoint pictures by tightness
- Brief Ebertin delineation for each
- One-line dignity synthesis

---

## 4. Midpoint Transits Add-on (NEW)

**+Midpoint Transits** — current transiting planets activating natal midpoints.

### What it calculates:
1. Get current planet positions (Helios `get-planet-positions`)
2. Get natal midpoints (from stored chart)
3. Check which current transits hit natal midpoints (orb ≤ 1°, tighter for transits)
4. Pull Ebertin delineation for: `transit_planet = natal_body1/natal_body2`

### Types of midpoint transits:

**A. Transit to Natal Midpoint** (primary)
```
Transit Saturn (27°15' Aries on 90° dial) = natal Sun/Moon (26°02')
  Orb: 1°13'
  Ebertin (Saturn = Sun/Moon): "Inner inhibitions, depression, separation..."
  Context: Transit Saturn in 8H approaching natal Mercury — theme of
  mental heaviness entering the marriage/partnership axis.
```

**B. Transit Midpoint on Natal Planet** (secondary)
```
Transit Jupiter/Saturn midpoint (14°30') = natal Venus (6°03')
  — Two transiting planets forming a midpoint that lands on a natal planet
  — Less commonly used, but powerful for outer planet pairs
```

**C. Solar Arc Directions** (timing)
```
Solar Arc Mars (age 39 × 0.9856° = 38°26' + natal 27°00' = 65°26' on 90°)
  SA Mars = natal Sun/Neptune midpoint (64°12')
  Orb: 1°14'
  Ebertin: "Weak vitality, infection, the necessity to take care of health..."
```

Solar arcs move ~1° per year — they're the primary cosmobiological timing method (more important than transits in Ebertin's system).

---

## 5. New Stella Tools

| Tool | Description |
|------|-------------|
| `get_midpoint_pictures` | All natal midpoint activations for a chart (90° dial) |
| `get_midpoint_interpretation` | Ebertin delineation for a specific pair + activating body |
| `get_midpoint_transits` | Current transits hitting natal midpoints |
| `get_solar_arcs` | Solar arc directions to natal midpoints |

### `get_midpoint_pictures(chart_name, orb=1.5)`
Returns: List of activated midpoints with Ebertin text + dignity context

### `get_midpoint_interpretation(pair, activating_body=None)`
Direct lookup: "What does Ebertin say about Sun/Moon?" or "What does Jupiter = Sun/Moon mean?"
Sources: JSON structured lookup → ChromaDB semantic search fallback

### `get_midpoint_transits(chart_name, orb=1.0)`
Returns: Current transit planets activating natal midpoints, sorted by orb

### `get_solar_arcs(chart_name, orb=1.0)`
Returns: Solar arc directed positions hitting natal midpoints, with timing (exact date of 0° orb)

---

## 6. 90° Dial Math

```python
def to_90(zodiac_degrees: float) -> float:
    """Convert zodiac position to 90° dial position."""
    return zodiac_degrees % 90

def midpoint_90(pos_a: float, pos_b: float) -> float:
    """Calculate midpoint on 90° dial."""
    a = to_90(pos_a)
    b = to_90(pos_b)
    
    # Direct midpoint
    mid = (a + b) / 2
    
    # Check if the far midpoint is closer to any target
    far_mid = (mid + 45) % 90
    
    return mid % 90

def is_activated(planet_90: float, midpoint_90: float, orb: float = 1.5) -> bool:
    """Check if a planet activates a midpoint on the 90° dial."""
    diff = abs(planet_90 - midpoint_90)
    if diff > 45:
        diff = 90 - diff
    return diff <= orb
```

---

## 7. Integration with Existing Workflow

The CHART_WORKFLOW.md already has:
- ✅ Cosmobiogram as Type (Step 2)
- ✅ Cosmobiological as Framework (Step 3)
- ✅ +Midpoints as Add-on (Step 5)

**New additions to workflow:**
- ✅ +Midpoint Transits (Step 5 add-on)
- ✅ +Solar Arcs (Step 5 add-on)

**Already in CHART_WORKFLOW.md TODO section** — this design replaces that TODO.

---

## 8. Archetypal Integration (Moore/Gillette KWML)

The four archetypes from *King, Warrior, Magician, Lover* map to planetary dignities through Aristotle's golden mean:

- **Fullness** (domicile/exalted) = integrated archetype = the golden mean
- **Active shadow** (inflation) = too much energy, wrong expression
- **Passive shadow** (deflation) = collapsed function, avoidance

| Archetype | Planets | Fullness | Active Shadow | Passive Shadow |
|-----------|---------|----------|---------------|----------------|
| King | Sun, Jupiter, Saturn | Order, blessing | Tyrant | Weakling |
| Warrior | Mars, Saturn, Pluto | Discipline, courage | Sadist | Masochist |
| Magician | Mercury, Uranus, Pluto | Awareness, insight | Detached Manipulator | Denying Innocent |
| Lover | Venus, Moon, Neptune | Empathy, aliveness | Addicted Lover | Impotent Lover |

**In cosmobiological context:** Midpoint pictures involving these planets carry archetypal weight. Mars = Sun/Saturn with Mars exalted → the Warrior integrating King structure. Mars = Sun/Saturn with Mars debilitated → Sadist/Masochist shadow around authority and discipline.

**Gender-neutral:** These are human energies. A woman's exalted Mars is Warrior fullness. A man's Venus in domicile is Lover fullness. The shadow poles apply equally.

**Knowledge graph:** 160 KWML chunks tagged with `tradition: jungian`, `layer: archetypal`, `archetype: king/warrior/magician/lover`. Use `knowledge_search(query="...", tradition="jungian")` to pull material.

---

## 9. Build Order

1. ~~Parse COSI into structured JSON~~ ✅ Done (78 pairs)
2. ~~Ingest into ChromaDB~~ ✅ Done (8,892 total chunks incl. KWML)
3. ~~`get_midpoint_interpretation`~~ ✅ Live — JSON lookup + ChromaDB fallback
4. ~~90° dial math module~~ ✅ Live — `midpoints.py` in Stella
5. ~~`get_midpoint_pictures`~~ ✅ Live — natal midpoint analysis
6. ~~`get_midpoint_transits`~~ ✅ Live — transit layer
7. ~~`get_solar_arcs`~~ ✅ Live — timing layer
8. ~~Update CHART_WORKFLOW.md~~ ✅ Done — Archetypal framework + cosmobio tools documented
9. ~~Ingest KWML into ChromaDB~~ ✅ Done — 160 chunks, archetype-tagged
10. **TODO:** Sabian symbols (pending book scan)
11. **TODO:** Constellation Agent — spin up second agent for Buckley's sister (see `CONSTELLATION-AGENT.md` for full blueprint). Needs: identity design session, chart data, channel setup.
