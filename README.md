# Stella — Unified Astrology & Divination MCP Server 🌙

**Repo:** [PoweredbyPugs/Stella-Astrological-System](https://github.com/PoweredbyPugs/Stella-Astrological-System) (private)

The Moon of Gnosis. A single Python MCP server that unifies ephemeris computation,
a 6,500+ chunk knowledge graph, chart reading generation, emergent pattern detection,
and a learning memory system.

## Quick Start

```bash
git clone https://github.com/PoweredbyPugs/Stella-Astrological-System.git stella
cd stella
bash setup.sh
```

See [SETUP.md](SETUP.md) for detailed instructions.

---

## Architecture

Stella has 8 core sections, each building on the last:

```
┌─────────────────────────────────────────────────────┐
│                    STELLA MCP                        │
├──────────┬──────────┬──────────┬────────────────────┤
│ Helios   │Knowledge │ Chart    │ Emergent System    │
│ Bridge   │ Graph    │ Reading  │                    │
│          │          │          │ discover()         │
│ 14+ ephe-│ 6,500+   │ 3-axis   │ reflect()          │
│ meris    │ chunks   │ Type ×   │ recall()           │
│ tools    │ from 26  │ Framework│ validate()         │
│          │ texts    │ × Size   │ chart_memory_stats()│
├──────────┼──────────┼──────────┼────────────────────┤
│ Ki (9    │ I Ching  │ ZR       │ Graph Queries      │
│ Star Ki) │ casting  │ Reports  │ (Neo4j)            │
└──────────┴──────────┴──────────┴────────────────────┘
         ▼                ▼               ▼
    Helios API      ChromaDB         charts/memory/
   (baratie:3000)   (local)          (per-chart learning)
```

### Components

1. **Helios Bridge** (Section 1) — 14+ ephemeris tools wrapping the Swiss Ephemeris REST API
2. **Chart Storage** (Section 1b) — Local chart persistence in `charts/`
3. **Knowledge Graph** (Section 2) — ChromaDB semantic search across 26 astrological texts
4. **I Ching** (Section 3) — Hexagram casting (King Wen sequence) and wisdom retrieval
5. **Resources** (Section 4) — 13 static resources (zodiac, planets, houses, aspects, charts)
6. **Prompts** (Section 5) — 11 interpretation templates
7. **Graph Queries** (Section 5b) — Direct Neo4j knowledge traversals (optional)
8. **Chart Reading** (Section 6) — Full computation + knowledge-grounded narrative generation
9. **Discover** (Section 7) — Emergent pattern detection: throws ALL techniques at a chart
10. **Reflect & Recall** (Section 8) — Learning memory system with validation feedback

---

## The Emergent System ⚡

The heart of Stella. Three tools that form a self-organizing learning cycle:

### `discover(name)` — Variation

Throws **all techniques simultaneously** at a chart and surfaces what's most active RIGHT NOW:

- Transit planets hitting natal midpoints (90° dial)
- Solar arc directions aspecting natal positions
- Solar arc directions hitting natal midpoints
- Tight transit aspects to natal (sub-1° orb)
- **Convergence zones** — 5° degree bins where multiple techniques pile up

Returns ranked findings sorted by orb tightness and zone density. Instead of asking
"what are the midpoints?" — let the chart tell you what's happening.

```bash
npx mcporter call stella.discover name=chris
```

### `reflect(name, content, ...)` — Selection

Stores a validated insight, prediction, or life event for a chart:

```bash
npx mcporter call stella.reflect \
  name=chris \
  content="SA Venus opposing natal Mars — love confronting the creative engine" \
  techniques="solar_arc,dignities" \
  placements="SA Venus opp natal Mars" \
  rating=5 \
  source=reading \
  tags="love,power,creative"
```

Each insight carries:
- **Technique tags** — which methods produced it
- **Placement references** — which astrological configurations
- **Resonance rating** (1-5) — how strongly it landed
- **Validation status** — confirmed by lived experience or not
- **Topic tags** — thematic classification

### `recall(name, ...)` — Memory

Searches the chart's accumulated insights before generating new readings:

```bash
npx mcporter call stella.recall name=chris technique=midpoints min_rating=4
```

Filter by type, technique, tag, rating, or text search. Most recent first.

### `validate(name, insight_id, confirmed)` — Feedback Loop

Marks predictions as confirmed or invalidated. This adjusts technique scores —
confirmed predictions boost the techniques that produced them, misses penalize.
Reinforcement learning for astrology.

### `chart_memory_stats(name)` — Dashboard

Shows what the system has learned about a chart: technique rankings by average
resonance, most-referenced placements, validation rates, tag cloud.

### The Cycle

```
discover() → surfaces signal → reading generated
     ↓                              ↓
  reflect() ← stores what worked ← feedback
     ↓
  recall() → informs next reading → discover()
     ↓
  validate() → adjusts technique weights
```

Each reading starts smarter than the last. Chart memory files live in
`charts/memory/{name}.json` (gitignored — local to each instance).

---

## Chart Reading System

The 3-axis reading generator. Every combination runs the full computation pipeline.

### Type × Framework × Size

**Type** (the medium):
| Type | Description |
|------|-------------|
| `technical` | Data-forward. Astro language preserved. For practitioners. |
| `narrative` | Human-first portrait. No jargon. Tech appendix at end. |
| `poem` | Artistic distillation. Verse or lyric prose. Tech appendix. |
| `cosmobiogram` | Ebertin-style midpoint-centered analysis. |

**Framework** (the lens):
| Framework | Description |
|-----------|-------------|
| `psychological` | Attachment, shadow, individuation. Non-fatalist. |
| `deterministic` | GTEI. Necessitated unfolding via Absolute Self-Consistency. |
| `hellenistic` | Sect, dignity, lots, timing. Vettius Valens lineage. |
| `stoic` | Virtue, fate, discipline of assent. |
| `mythological` | Gods, archetypes, hero's journey. |
| `cosmobiological` | Ebertin midpoints + Hellenistic dignities. |

**Size**: `xs` (3-5 sentences) → `s` → `m` → `l` → `xl` (5-10+ pages)

**Add-ons** (layer on any reading): `+Midpoints`, `+Solar Arcs`, `+Sabian`, `+ZR`, `+Transits`

### Computation Pipeline

Every reading runs:
1. Natal chart (planets, angles, lots, depositors, sect)
2. Whole sign houses (computed from ASC)
3. Essential dignities (domicile, exaltation, triplicity, term, face, detriment, fall)
4. Derivative houses (Pelletier system)
5. Current aspects between all planets
6. Profections (annual, lord of year)
7. Zodiacal Releasing (Spirit + Fortune, L1/L2, peak periods)
8. Transits to natal
9. Knowledge graph queries (grounded in 26-text corpus)

**Key principle:** Dignity score drives narrative weight. The strongest planet dominates.
A peregrine chart ruler means the ASC archetype is CONDITIONAL.

### Narrative Standard

Oliver Sacks meets James Hillman. Clinical precision + archetypal depth. Joan Didion voice.
Every paragraph specific to THIS chart. Include shadow/defense mechanisms. No Hallmark cards.

---

## 9 Star Ki

Japanese divination system based on the I Ching / Lo Shu magic square.

- `get_ki(name)` — Calculate 3 Ki numbers from birth date
- `get_ki_cycle(name)` — Current Ki cycle position
- `get_ki_reading(name)` — Full narrative reading

**The 3 Numbers:**
1. **Essence** (1st) — invisible to self, iceberg below water
2. **Emotion** (2nd) — internal processing, heart, stress shadow
3. **Life Path** (3rd) — how people see you, career, societal lessons

---

## Tools Reference (30+)

### Emergent System
| Tool | Description |
|------|-------------|
| `discover` | Pattern detection — all techniques at once, ranked by significance |
| `reflect` | Store insight/prediction/event with technique tags + resonance rating |
| `recall` | Search chart memory by type, technique, tag, rating |
| `validate` | Confirm/deny predictions (adjusts technique scores) |
| `chart_memory_stats` | Technique rankings, placement memory, tag cloud |

### Chart Reading
| Tool | Description |
|------|-------------|
| `chart_reading` | Full computation + knowledge graph + narrative. 3-axis. |
| `full_chart_computation` | Raw computation only (all data, no narrative) |

### Ephemeris (Helios Bridge)
| Tool | Description |
|------|-------------|
| `get_current_moon` | Current moon phase and sign |
| `get_planet_positions` | Current positions of all planets |
| `get_planet_aspects` | Current aspects between planets |
| `get_weekly_moon_phase` | This week's major moon phase |
| `get_natal_chart` | Full natal chart calculation |
| `generate_chart` | Generate and save a natal chart |
| `get_chart` | Retrieve a stored chart by name |
| `list_charts` | List all stored charts |
| `get_profections` | Annual profections |
| `get_zodiacal_releasing` | ZR L1/L2 periods with peak detection |
| `get_transits_now` | Current transits to natal chart |
| `get_transit_summary` | High-level transit summary with timing |
| `get_dignity_score` | Essential dignity score for a planet |
| `get_current_dignities` | Dignity scores for all current planets |

### Ki & I Ching
| Tool | Description |
|------|-------------|
| `get_ki` | 9 Star Ki numbers for a chart |
| `get_ki_cycle` | Current Ki cycle position |
| `get_ki_reading` | Full Ki narrative reading |
| `get_daily_ki` | Traditional daily Ki (days-since-Lichun cascade) — **authoritative** |
| `get_convergence_ki` | Experimental Moon-socket daily Ki model (day Ki is experimental) |
| `cast_hexagram` | I Ching divination (coins or yarrow) |
| `retrieve_wisdom` | Search I Ching wisdom texts |

### Knowledge Graph
| Tool | Description |
|------|-------------|
| `knowledge_search` | Semantic search across 38 texts (Neo4j) |
| `knowledge_search_json` | Same, returns structured JSON |
| `knowledge_stats` | Collection statistics |
| `interpret_placement` | Multi-layered interpretation |

### Neo4j Graph (optional)
| Tool | Description |
|------|-------------|
| `graph_query` | Direct Cypher queries |
| `graph_rulership_web` | Rulership relationships for a sign |
| `graph_planet_condition` | Planet condition in a sign |
| `graph_stats` | Graph statistics |

---

## Knowledge Graph Sources (38 texts, 10,411 chunks)

Across 5 layers:
- **Technical** — Brennan, Lehman, Hand, Ebertin
- **Psychological** — Sasportas, Pelletier, Greene
- **Archetypal** — Tarnas, Hillman, Moore, Coppock
- **Philosophical** — Agrippa (Three Books of Occult Philosophy), Cosmos & Psyche
- **Reference** — Planet PDFs, delineation texts, Crowley (777 Revised)
- **Hermetic** — Agrippa (magic squares, sigils, geomancy, Kabbalistic paths), Crowley (correspondence tables)

**Primary store: Neo4j** (`bolt://localhost:7687`). 10,741 nodes, 93,183 relationships.
ChromaDB was secondary and is currently broken on Python 3.14 — all queries route through Neo4j.

Key texts by chunk count: Hellenistic Astrology (621), Venus (786), Gnostic I Ching (735+67), Planets in Transit (534), Mars (537), Sun (529), Moon (608), Agrippa (1,356), Saturn (471), Pluto (451), Jupiter (432), Pelletier Houses (419), Mercury (410), Uranus (405+82), 36 Faces (215), Ebertin COSI (147), Crowley 777 (121), KWML (118), Houses: Temples of the Sky (123).

---

## File Structure

```
stella/
├── stella_server.py           # Main MCP server (all 8 sections)
├── ki.py                      # 9 Star Ki calculation
├── ki_reading.py              # Ki narrative generator
├── zr_report.py               # Zodiacal Releasing reports
├── CHART_WORKFLOW.md           # Reading generation guide
├── SETUP.md                   # Installation guide
├── setup.sh                   # Automated setup script
├── docker-compose.yml          # Neo4j container (optional)
├── build_graph.py             # Neo4j graph builder
├── data/                      # Structured reference data
│   └── 777-correspondences.json  # Crowley's 777: 35 rows, all 4 colour scales, tarot, Hebrew, paths
├── charts/                    # Chart JSON files (gitignored)
│   ├── memory/                # Per-chart learning memory (gitignored)
│   └── readings/              # Generated readings (gitignored)
├── elections/                 # 2026 electional data
├── graph/                     # Neo4j graph scripts
│   ├── build_graph.py         # Phase 2-3 structural graph + knowledge migration
│   ├── ingest_missing.py      # Ingest new texts to ChromaDB + sync to Neo4j
│   ├── ingest_books.py        # PDF book ingestion (Agrippa, Crowley) — uses .ingest-venv
│   ├── enrich_interpretations.py  # INTERPRETS_* edge creation
│   ├── seed_charts.py         # Seed natal charts from Helios
│   ├── seed_wuxing.py         # Wu Xing elemental relationships
│   ├── neo4j_tools.py         # Graph traversal utilities
│   ├── synthesize.py          # Narrative scaffold generation
│   └── fix_references.py      # Reference cleanup
├── .ingest-venv/              # Python 3.13 venv for ingestion (ChromaDB broken on 3.14)
└── docs/                      # Reference materials
    ├── KI_REFERENCE.md
    └── ZR_REFERENCE.md
```

---

## For AI Assistants (VA Guide)

If you're an AI assistant using Stella, here's how to get the most out of it:

### First: Generate the chart
```bash
stella.generate_chart name="person" date="YYYY-MM-DD" time="HH:MM" lat=XX.XX lon=XX.XX location="City, State"
```

### For a reading: Use `chart_reading`
```bash
stella.chart_reading name="person" size="l" report_type="narrative" framework="psychological"
```

### For current transits: Use `discover` first
`discover` surfaces what's most active RIGHT NOW — tightest orbs, convergence zones,
solar arc peaks. Use this BEFORE writing a transit reading to know where to focus.
```bash
stella.discover name="person"
```

### After a reading lands: Use `reflect`
When the human confirms an insight resonated, store it. Over time the system learns
which techniques work best for each chart.

### Before a new reading: Use `recall`
Check what's already been learned about this chart. Don't rediscover what's known.
Build on accumulated insight.

### Key principles
- **Dignity drives narrative.** The strongest planet by score gets the most space.
- **Whole sign houses always.** Hellenistic baseline regardless of framework.
- **No cookbook readings.** Every sentence must be specific to THIS chart.
- **Shadow included.** Debilitated planets = shadows named directly, not softened.
- **Synthesis over summary.** One unified portrait, not sections stitched together.
- **The Sabian symbols** add imaginal depth. Midpoint gives the principle, Sabian gives the image.

### The narrative standard
Oliver Sacks meets James Hillman. Clinical precision + archetypal depth.
Joan Didion voice. No empty aphorisms. No recycled phrasing. No astro jargon in
narrative prose — astrology is invisible scaffolding, only the human portrait shows.

---

## Environment Variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `OPENAI_API_KEY` | **Yes** | — | Knowledge graph embeddings |
| `SWEPH_API_BASE` | No | `http://baratie:3000` | Helios ephemeris API |
| `NEO4J_URI` | No | `bolt://localhost:7687` | Optional graph DB |
| `NEO4J_USER` | No | `neo4j` | Neo4j auth |
| `NEO4J_PASS` | No | `stella_gnosis` | Neo4j auth |

---

## Known Issues

- **ChromaDB broken on Python 3.14** — pydantic v1 incompatible. The `.ingest-venv` (Python 3.13) works for ingestion. All runtime queries use Neo4j directly via `_knowledge_query_neo4j()`.
- **Poneglyph cron uses `convergence_ki` for day Ki** — should use `get_daily_ki` (traditional cascade). Pending update.

## Roadmap

- [x] Emergent pattern detection (`discover`)
- [x] Learning memory system (`reflect` / `recall` / `validate`)
- [x] Solar arc directions (in `discover`)
- [x] Midpoint transit detection (in `discover`)
- [x] Convergence zone mapping (in `discover`)
- [x] Traditional daily Ki tool (`get_daily_ki` — days-since-Lichun cascade)
- [x] 777 Revised structured correspondence data (`data/777-correspondences.json`)
- [x] Agrippa's Three Books of Occult Philosophy ingested (1,356 chunks)
- [x] Crowley's 777 Revised ingested (121 chunks + structured JSON)
- [ ] 777 correspondence lookup tool (reverse lookups by planet/tarot/colour)
- [ ] Sabian symbol lookup tool (automated, not manual)
- [ ] `discover` reads chart memory to weight findings
- [ ] Solar arc calculation as standalone tool
- [ ] Midpoint pictures as standalone tool
- [ ] Cross-chart pattern detection
- [ ] Temporal tracking (log predictions, check against events)
- [ ] Evolutionary Astrology framework
- [ ] Framework auto-detection from chart signatures
- [ ] Geomancy casting tool (rapid-tap or manual count)
- [ ] Seven Strings seed moment calculator (tiered election system)
