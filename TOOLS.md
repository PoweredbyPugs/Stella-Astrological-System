# Stella MCP Server — 89 Tools

*Last updated: Mar 27, 2026*

## Helios Bridge (current sky data)

| # | Tool | Description |
|---|------|-------------|
| 1 | `get_current_moon` | Current moon phase and sign |
| 2 | `get_planet_positions` | Current positions of all planets |
| 3 | `get_planet_aspects` | Current aspects between planets |
| 4 | `get_weekly_moon_phase` | This week's major moon phase |
| 5 | `get_natal_chart` | Calculate natal chart from birth data |
| 6 | `generate_chart` | Generate and optionally save a natal chart |
| 7 | `get_chart` | Retrieve a stored natal chart by name |
| 8 | `list_charts` | List all stored natal charts |

## pyswisseph Native (no Helios dependency)

| # | Tool | Description |
|---|------|-------------|
| 9 | `get_void_of_course_moons` | VOC periods (modern planet set, validated vs MoonTracks) |
| 10 | `transit_timing` | When a transit enters orb, perfects, and leaves orb |
| 11 | `search_next_transit` | Scan for upcoming transits to a natal chart |
| 12 | `lunar_return` | Chart for Moon's return to natal position |
| 13 | `solar_return` | Chart for Sun's return to natal position |
| 14 | `secondary_progressions` | Progressed chart (1 day = 1 year) with solar arc ASC/MC |
| 15 | `find_elections` | Electional windows scored by Moon condition + aspects |
| 16 | `find_eclipses` | Solar/lunar eclipses with natal contact detection |
| 17 | `get_exact_ingresses` | Precise sign ingress times via binary search |
| 18 | `get_planetary_hours` | 24 planetary hours, Chaldean order, sunrise/sunset |

## Timing Techniques

| # | Tool | Description |
|---|------|-------------|
| 19 | `get_profections` | Annual profections with lord of year |
| 20 | `get_zodiacal_releasing` | ZR L1–L5 periods for a chart |
| 21 | `get_zr_report` | Comprehensive ZR report (Brennan worksheet framework) |
| 22 | `get_transits_now` | All current transits to a natal chart |
| 23 | `get_transit_summary` | High-level outer planet transit summary |
| 24 | `get_dignity_score` | Essential dignity score for any planet/position |
| 25 | `get_current_dignities` | Dignity scores for all planets right now |

## Vimshottari Dasha & Timing Stack *(NEW 2026-03-26)*

| # | Tool | Description |
|---|------|-------------|
| 26 | `get_timing_stack` | **Full timing stack** — 4 systems in one call: Dasha (5 levels), ZR (Spirit + Fortune, L1-L5), Nakshatra transit (lord + pada), Ki (5 levels). Includes glyphs, resonance detection. |
| 27 | `get_dasha_periods` | 5-level Vimshottari dasha only (maha→prana) with dates and durations |
| 28 | `get_nakshatra_transit` | Live Moon nakshatra position with lord, pada, entry/exit times |

### Vimshottari Dasha — Key Facts

- **Lord sequence (nakshatra order):** ☋Ketu(7yr), ♀Venus(20yr), ☉Sun(6yr), ☽Moon(10yr), ♂Mars(7yr), ☊Rahu(18yr), ♃Jupiter(16yr), ♄Saturn(19yr), ☿Mercury(17yr) = 120 years
- **NOT the sequence:** Ke,Su,Mo,Ma,Ra,Ju,Sa,Me,Ve — that's a common misquote
- **Each lord owns 3 nakshatras:** position i → nakshatras i, i+9, i+18
- **5 levels:** Maha (decades) → Bhukti (months-years) → Pratyantara (weeks-months) → Sookshma (days-weeks) → Prana (hours)
- **Sub-division:** Each level divides parent period proportionally by the same 9 lords, starting from parent's lord
- **Birth seeding:** Natal Moon nakshatra determines first lord; fraction of nakshatra traversed = fraction of first period elapsed
- **Nakshatra transit (levels 6-7):** Live Moon position gives daily lord (~24h per nakshatra) and pada quality (~6h per pada: Dharma/Artha/Kama/Moksha)
- **Module:** `dasha.py`

## 9 Star Ki & I Ching

| # | Tool | Description |
|---|------|-------------|
| 29 | `get_ki` | 9 Star Ki numbers for a date |
| 30 | `get_ki_cycle` | Full Ki profile with personal year/month cycle |
| 31 | `get_ki_reading` | Combined Ki + I Ching reading (hexagram from Ki) |
| 32 | `get_ki_transition` | Ki month transition report with hexagram derivation |
| 33 | `cast_hexagram` | Cast I Ching hexagram (coins or yarrow) |
| 34 | `retrieve_wisdom` | Search Gnostic Book of Changes + I Ching texts |

## Convergence Ki (5-level solar-terrestrial cascade)

Based on the -3 cascade and 365-day continuity breakthrough (March 6, 2026). Research: `stella/research/convergence-sockets.md`

| # | Tool | Description |
|---|------|-------------|
| 35 | `get_convergence_ki_now` | Full 5-level Ki state with personal transformation. Synodic (Jupiter gate), Year, Month, Day, Hour. Location-aware. |
| 36 | `get_synodic_gate_now` | Jupiter's ~12-year orbital gate Ki with perihelion chain |
| 37 | `get_natal_gates` | Map a chart's planets to their permanent 15° gates and San Cai triads |

## Ki Changes — Mercury's Reading *(NEW 2026-03-27)*

Mercury reads the delta, not the state. These tools show what's transitioning at each level: changing lines (trigram yin↔yang), Wu Xing phase relationships, I Ching hexagrams formed by adjacent level pairs, and Gnostic Book of Changes interpretations.

| # | Tool | Description |
|---|------|-------------|
| 38 | `get_ki_changes` | **Full Ki changes** — all 5 levels at once. Current→next Ki, changing lines, hexagrams from level pairs, Wu Xing transitions. `include_gnostic=true` for I Ching text. |
| 39 | `get_ki_change_schedule` | Next N changes at a specific level (default 9 = full cycle). Shows rhythm of transitions. |
| 40 | `ki_change_hour` | Hour-level Ki change (~2h cycle). Hexagram with day level. Fastest pulse. |
| 41 | `ki_change_day` | Day-level Ki change (midnight). Hexagrams with month and hour levels. |
| 42 | `ki_change_month` | Month-level Ki change (Sun crosses 30° boundary). Hexagrams with year and day levels. |
| 43 | `ki_change_year` | Year-level Ki change (Lichun ~Feb 4). Hexagrams with synodic and month levels. |
| 44 | `ki_change_global` | Synodic (global) Ki change (~12yr Jupiter cycle). Hexagram with year level. Slowest pulse. |

### Ki Changes — Architecture

**Core insight:** Ki numbers map to I Ching trigrams (1=Kan☵, 2=Kun☷, 3=Zhen☳, 4=Xun☴, 5=Kun☷, 6=Qian☰, 7=Dui☱, 8=Gen☶, 9=Li☲). Two adjacent Ki levels form a hexagram: slower level = lower trigram (stable ground), faster level = upper trigram (what's cycling).

**Changing lines:** When a Ki level transitions (e.g. day Ki 9☲→8☶), the trigram lines that differ are "changing lines" in I Ching terms. This gives direction of change (yin→yang or yang→yin).

**64 = Mercury's grid:** Mercury's magic square is 8×8 = 64 cells = 64 hexagrams. The I Ching IS Mercury's square. Every Ki transition is a hexagram reading.

**Module:** `ki_changes.py`

### Ki — Key Architecture (Definitive, March 6 2026)

**5 levels, -3 cascade:**
```
Synodic Ki  — Jupiter perihelion cycle (~11.86 yr), 9 gates = ~108 years
Year Ki     — Sun completes orbit, ticks at Lichun (15° Aquarius), ~365 days
Month Ki    — Sun crosses 15° of each sign, ~30 days
Day Ki      — Solar day, descends 1/day from Lichun, 365 mod 9 = 5 → full continuity
Hour Ki     — Chinese double-hour (shíchén), 12/day, descends 1 each, shifts 3/day
```

**-3 cascade rule:** Each level starts at parent minus 3:
- Year 1 → Month 8 → Day 5 → Hour 2
- Month always starts Earth (8, 5, 2) at Lichun
- Hour always starts Earth (2, 5, 8) at Lichun
- 365 mod 9 = 5 ensures all 9 starting values over 9 years

**Moon is NOT structural for Ki.** Moon's 12-gate/convergence socket rhythm is real but kept as a parallel observation layer. Ki is purely solar + terrestrial.

**Personal Ki:** Flying Star transformation — `_flying_star(natal_year_ki, global_ki)` applied independently to each level.

**Month gate crossings:** Sun at 15° of each sign (Chinese solar terms / 节气). NOT Gregorian months.

- **Module:** `convergence_ki.py`
- **Synodic module:** `convergence_ki.py` → `get_synodic_gate()`

## Midpoints & Cosmobiology

| # | Tool | Description |
|---|------|-------------|
| 45 | `get_midpoint_interpretation` | Ebertin COSI lookup for a midpoint pair |
| 46 | `get_midpoint_pictures` | Natal midpoint pictures (90° dial) |
| 47 | `get_midpoint_transits` | Transiting planets activating natal midpoints |
| 48 | `get_solar_arcs` | Solar arc directions hitting natal midpoints |

## Chart Reading & Synthesis

| # | Tool | Description |
|---|------|-------------|
| 49 | `chart_reading` | Full chart reading (size × type × framework) |

## Knowledge Graph (10,548 chunks, 41 texts)

| # | Tool | Description |
|---|------|-------------|
| 50 | `knowledge_search` | Semantic search across interpretation nodes |
| 51 | `knowledge_search_json` | Structured JSON search results |
| 52 | `knowledge_stats` | Graph statistics |
| 53 | `interpret_placement` | Multi-layered interpretation for a placement |

## Neo4j Graph Traversal

| # | Tool | Description |
|---|------|-------------|
| 54 | `graph_traverse_chain` | Depositor chain from planet to final dispositor |
| 55 | `graph_find_receptions` | All mutual receptions in a chart |
| 56 | `graph_aspect_network` | Natal aspect network (tightest first) |
| 57 | `graph_midpoint_pictures` | Midpoint pictures from graph |
| 58 | `graph_chart` | Complete chart as graph structure |
| 59 | `graph_walk` | Deep walk from a placement (all connections) |
| 60 | `graph_compare` | Compare two charts (synastry + structural) |
| 61 | `graph_query` | Structured graph query with filters |
| 62 | `graph_cypher` | Raw Cypher query against Neo4j |
| 63 | `graph_stats` | Neo4j graph statistics |
| 64 | `graph_synthesize` | Narrative scaffold for one planet |
| 65 | `graph_synthesize_chart` | Full chart synthesis scaffold (all 7 traditional planets) |
| 66 | `graph_rulership_web` | Complete rulership web for a sign |
| 67 | `graph_planet_condition` | Planet's full condition in a sign |

## Chart Storage

| # | Tool | Description |
|---|------|-------------|
| 68 | `store_chart` | Save a natal chart |
| 69 | `load_chart` | Load a chart (local storage → Helios fallback) |
| 70 | `list_stored_charts` | List locally stored charts |
| 71 | `delete_chart` | Delete a stored chart |

## Emergent Triad (chart memory)

| # | Tool | Description |
|---|------|-------------|
| 72 | `discover` | What's most active in a chart right now |
| 73 | `reflect` | Store a validated insight/prediction/event |
| 74 | `recall` | Search chart's accumulated insights |
| 75 | `validate` | Confirm or invalidate a stored insight |
| 76 | `chart_memory_stats` | What the system has learned about a chart |

## Autopoietic

| # | Tool | Description |
|---|------|-------------|
| 77 | `autopoietic_init` | Initialize autopoietic chart session |
| 78 | `autopoietic_submit` | Submit a diverge/converge pass |
| 79 | `autopoietic_converge` | Get convergence prompt for current round |
| 80 | `autopoietic_status` | Check session status |

## Sweph Passthroughs (Helios REST)

| # | Tool | Description |
|---|------|-------------|
| 81 | `sweph_test` | Test server connectivity |
| 82 | `sweph_profections_calc` | Profections without stored chart |
| 83 | `sweph_zr_calc` | ZR without stored chart |
| 84 | `sweph_planetary_retrogrades` | Current retrograde status |
| 85 | `sweph_daily_transits` | Transits to a natal chart |
| 86 | `sweph_moon_for_date` | Moon phase/sign for a date |
| 87 | `sweph_planetary_ingresses` | Planetary sign changes |
| 88 | `sweph_planetary_stations` | Retrograde/direct stations |
| 89 | `sweph_important_transits` | Significant outer planet aspects |
