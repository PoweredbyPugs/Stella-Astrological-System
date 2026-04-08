# Stella Changelog

## 2026-03-27 — Ki Changes (Mercury's Reading)

### New Module: `ki_changes.py`
- **Ki transitions as I Ching hexagrams** — every Ki level change produces changing lines (trigram transitions), and every pair of adjacent levels forms a hexagram (lower=stable, upper=changing)
- Ki numbers mapped to Later Heaven trigrams: 1=Kan☵, 2=Kun☷, 3=Zhen☳, 4=Xun☴, 5=Kun☷, 6=Qian☰, 7=Dui☱, 8=Gen☶, 9=Li☲
- Wu Xing phase relationships computed for each transition
- Gnostic Book of Changes lookup from Neo4j for hexagram interpretations
- Core insight: 64 hexagrams = Mercury's 8×8 magic square. Mercury reads the delta.

### New Tools (7)
- `get_ki_changes(target_date?, birth_date?, include_gnostic?)` — Full Ki changes at all 5 levels with hexagrams
- `get_ki_change_schedule(birth_date?, level?, count?)` — Next N changes at a specific level
- `ki_change_hour(birth_date?, include_gnostic?)` — Hour-level changes (~2h cycle)
- `ki_change_day(birth_date?, include_gnostic?)` — Day-level changes (midnight)
- `ki_change_month(birth_date?, include_gnostic?)` — Month-level changes (Sun crosses 30° boundary)
- `ki_change_year(birth_date?, include_gnostic?)` — Year-level changes (Lichun ~Feb 4)
- `ki_change_global(birth_date?, include_gnostic?)` — Synodic-level changes (~12yr Jupiter cycle)

### Research Context
- Mercury's magic square: 8×8, 64 cells, constant 260 (Tiriel), total 2080 (Taphthartharath)
- 81 - 64 = 17 = Mercury's Vimshottari dasha period
- Agrippa: Mercury's square "conduceth to memory, understanding, and divination, and to the understanding of occult things by dreams"
- Book of Thoth: The Magus (Atu I), Intelligence of Transparency, the ape that distorts the Word
- Total tool count: 89

---

## 2026-03-26 — Dasha & Timing Stack + Ki Fixes

### New Module: `dasha.py`
- **Vimshottari Dasha** — 5-level computation (maha→prana) from natal Moon nakshatra
- **Correct lord sequence:** Ke, Ve, Su, Mo, Ma, Ra, Ju, Sa, Me (NOT Ke, Su, Mo, Ma, Ra, Ju, Sa, Me, Ve)
- **Nakshatra transit** — live Moon position with lord, pada (Dharma/Artha/Kama/Moksha), entry/exit times
- **Planetary glyphs:** ☋♀☉☽♂☊♃♄☿ on all dasha output

### New Tools (3)
- `get_timing_stack(name)` — Full stack: Dasha (5) + ZR Spirit/Fortune (L1-L5) + Nakshatra transit + Ki (5) + resonance detection
- `get_dasha_periods(name)` — Dasha only (5 levels with dates)
- `get_nakshatra_transit()` — Live Moon nakshatra/pada

### Bug Fixes in `convergence_ki.py`
- **FIXED: Month start groups were rotated.** Was `{1:5, 2:8, 3:2}`, should be `{1:8, 2:5, 3:2}`. Caused personal month to compute wrong (e.g., 6 instead of 3).
- **FIXED: Day Ki used Moon socket crossings.** Replaced with solar day cascade (-3 from month, descends 1/day from Lichun). Moon dropped as structural per March 6 definitive architecture.
- **FIXED: Hour Ki used ascendant gates.** Replaced with -3 cascade from day Ki, 12 double-hours/day.
- **ADDED: Synodic Ki (Great Year)** as 5th level above Year. Jupiter perihelion cycle (~11.86yr), pulled from `get_synodic_gate()`.
- **FIXED: Variable name collision** — `mki` was used for both month Ki and minute Ki, causing month to be overwritten.
- **Removed:** Moon socket crossing code for day Ki, ascendant gate scanning for hour Ki, minute Ki subdivision (not a primary level).

### Ki Architecture (5 levels, definitive)
```
Synodic  — Jupiter perihelion gate (~11.86yr), 9 gates = ~108 years
Year     — Sun orbit, Lichun to Lichun (~365 days)
Month    — Sun crosses 15° of each sign (~30 days)
Day      — Solar day, descends 1/day, 365 mod 9 = 5
Hour     — Double-hour (shíchén), 12/day, shifts 3/day
```

---

## 2026-02-02 — The Three-Axis Report System

### Major Features

**3-Axis Chart Reading System**
The `chart_reading` tool now operates on three independent axes:
- **Type** (the medium): `technical` | `narrative` | `poem`
- **Framework** (the lens): `psychological` | `deterministic` | `hellenistic` | `stoic` | `mythological`
- **Size** (the depth): `xs` | `s` | `m` | `l` | `xl`

75 possible combinations from a single chart. Each axis is independently configurable.

**Derivative Houses (Pelletier System)**
- `compute_derivative_houses(chart_data)` computes house-to-house relationships for every planet
- Formula: `(origin - target) % 12 + 1` (clockwise/Pelletier method)
- Asymmetric pairs always sum to 14
- Grouped by aspect geometry (conjunction, semisextile, sextile, square, trine, quincunx, opposition)
- Key connections identified: dignified planets to angular houses
- Pelletier's interpretations queried from ChromaDB for each key connection
- Integrated into `full_chart_computation()` and `_gather_knowledge_for_chart()`

**Dignity-Weighted Narrative Priority**
- Automatically analyzes chart ruler condition vs. strongest planets by dignity score
- Generates priority instructions injected into every reading
- Weak/peregrine chart ruler → ASC archetype treated as CONDITIONAL
- Strongest planet by dignity score gets most narrative weight
- Debilitated planets' shadows named directly (not softened)
- Central narrative tension = gap between ASC mask and dominant planet's reality

**Legacy Chart Format Normalization**
- `_normalize_legacy_chart()` converts old format (dict-keyed planets, string angles) to Helios format
- Handles charts imported before Helios integration
- Infers sect from Sun house position when not present

### New Constants
- `REPORT_TYPES` — 3 report types with full LLM instructions
- `FRAMEWORKS` — 5 interpretive frameworks (expanded from 2 `PERSPECTIVES`)
- `DERIVATIVE_HOUSES` — meanings for all 12 derivative positions
- `ASPECT_GEOMETRY` — 7 geometric relationship types
- `ANGULAR_HOUSES` — {1, 4, 7, 10}
- `PERSPECTIVES` maintained as legacy alias → `FRAMEWORKS`

### New Files
- `elections/2026-elections-brennan-schaim.pdf` — Brennan & Schaim electional report
- `elections/2026-elections-chart-data.pdf` — Chart data for elections
- `elections/2026-elections-summary.md` — Quick reference: all 24 elections + planetary events
- `reports/robin-natal-reading.md` — Robin's natal chart (first reading from new system)
- `reports/lisa-natal-reading.md` — Lisa's natal (narrative, psychological, M)
- `reports/lisa-natal-reading-v2.md` — Lisa's natal (calibrated dignity weighting)
- `reports/lisa-xl-technical.md` — Lisa's natal (technical, psychological, XL)

### Calibration Lessons
- Dignity score should drive narrative weight more than ASC archetype
- A peregrine/debilitated chart ruler delivers its sign's qualities CONDITIONALLY
- Leo ASC + peregrine Sun + Moon domicile 12H = warmth only when emotionally settled or externally recognized
- Mercury detriment = "jumps to conclusions," not "broad thinking" — name shadows directly
- Feedback from real people who know the chart subject is the ultimate calibration tool

### Future Roadmap (parked)
- **Evolutionary Astrology framework** — Pluto polarity point, nodal story, skipped steps
- **Archetypal Astrology framework** — Tarnas, outer planet cycle tracking
- **Framework-specific computation adjuncts** — extra data computed per framework
- **"What the chart wants" auto-detection** — scoring function recommends framework from chart signatures
- **Interactive Telegram flow** — inline buttons for chart selection → type → framework → size
- **Transit query language** — deeper drilling into specific transit periods
- **Full transit cycle tracking** — complete planetary return cycles
