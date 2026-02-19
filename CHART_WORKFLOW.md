# Chart Reading Workflow

## Trigger
When user says "run a chart" → **read this file first**, then follow the conversational steps below.

**Interaction Style:** Ask one question at a time, wait for answer. No buttons — this workflow should work in any context (Telegram, CLI, other MCP clients).

---

## Baseline (Always Present)
**Hellenistic + Whole Sign Houses** — the backbone of all readings. Sect, dignity, lots, depositors, timing techniques. This isn't a framework choice — it's how we do astrology. All frameworks layer ON TOP of this.

---

## Step 1: Chart Selection

Ask: *"Which chart? (name one from the list, or say 'new' to create one)"*

Then list stored charts.

If **new** → collect: Name, Date (YYYY-MM-DD), Time (HH:MM), Location
Then: `stella.generate_chart` with `save=true`

---

## Step 2: Type (output format)

Ask: *"What type of reading?"*

| Type | Format |
|------|--------|
| **Technical** | Math first, full astrological architecture, astro jargon fine |
| **Narrative** | Portrait first, NO astro jargon in prose, math as appendix |
| **Poem** | Pure poetry in the body — NO astro jargon in the poem itself. Symbolism and imagery only. Technical appendix still included at end. |
| **Ki** | Pure 9 Star Ki + I Ching — trigrams, hexagrams, elemental cycles. NO Western astrology blended in. |
| **Cosmobiogram** | 90° dial midpoint analysis — midpoint trees, pictures, wiring diagram. Ebertin method. Can layer dignities/depositors. |

**Note:** Ki as *Type* = standalone Ki reading. Ki as *Framework* (Step 3) = Ki meanings woven INTO astrological interpretation.

---

## Step 3: Framework (interpretive lens)

**ALWAYS ask this step, regardless of type.** Frameworks apply to ALL types including Ki and Poem.

Ask: *"Which framework(s)? You can pick multiple."*

| Framework | Approach |
|-----------|----------|
| **Psychological** | Attachment, shadow, IFS, developmental. Non-deterministic. Include outer planets as psychological themes. |
| **Archetypal** | Moore/Gillette four-archetype model (King/Warrior/Magician/Lover) mapped to planetary dignities. Fullness = integrated archetype, debility = shadow pole. Aristotle's golden mean as structural principle. Gender-neutral — archetypes are human energies, not gendered roles. |
| **GTEI** | Absolute Self-Consistency, 5 Primordial Categories, deterministic. |
| **Ki** | Blend 5.9.1 (or whatever the natal pattern is) INTO the astrological interpretation. Essence shapes identity themes, Emotion shapes Moon/Venus themes, Life Path shapes nodal/career themes. Full synthesis. |
| **ZR** | Zodiacal Releasing as primary timing lens — life chapters, peak periods. |
| **Stoic** | Virtue, fate, dichotomy of control. *(needs more books)* |
| **Cosmobiological** | Midpoint pictures as structural framework, fleshed out with dignities, depositors, houses. Ebertin + Hellenistic synthesis. |

**Frameworks are mixable:** Psychological + Ki ✓ | GTEI + ZR ✓ | Archetypal + Cosmobiological ✓ | etc.

### Ki Framework Integration Guide
When Ki is selected as a **framework** (not type):
- **Essence (1st number)** → weave into Sun/ASC/identity interpretation
- **Emotion (2nd number)** → weave into Moon/Venus/emotional core interpretation  
- **Life Path (3rd number)** → weave into Node/MC/career/external perception interpretation
- Element relationships (productive/controlling cycles) inform planetary relationships

This is NOT a separate Ki section — it's a lens that colors the entire reading.

### Archetypal Framework Integration Guide (Moore/Gillette + Aristotle's Golden Mean)

**Source:** *King, Warrior, Magician, Lover* (Moore & Gillette), ingested into knowledge graph (160 chunks, layer: archetypal, tradition: jungian).

**Core principle:** Each archetype has a **fullness** (the integrated, mature form) and a **bipolar shadow system** (active/inflated pole + passive/deflated pole). This maps directly to essential dignities:

| Archetype | Planets | Fullness (Golden Mean) | Active Shadow (Inflation) | Passive Shadow (Deflation) |
|-----------|---------|----------------------|--------------------------|---------------------------|
| **King** | Sun, Jupiter, Saturn | Order, blessing, centeredness, generativity | Tyrant (exploits, destroys) | Weakling (abdicates, impotent) |
| **Warrior** | Mars, Saturn, Pluto | Discipline, courage, loyalty, mindfulness | Sadist (cruelty, domination) | Masochist (self-punishment, paralysis) |
| **Magician** | Mercury, Uranus, Pluto | Awareness, insight, transformation | Detached Manipulator (uses knowledge as power) | Denying "Innocent" One (refuses to see/know) |
| **Lover** | Venus, Moon, Neptune | Empathy, aliveness, connectedness, embodiment | Addicted Lover (boundary-less, lost in sensation) | Impotent Lover (numbed out, disconnected) |

**Dignity → Archetype mapping:**
- **Domicile/Exalted** (+5 to +8): Planet expresses the archetype's **fullness**. The golden mean — power with restraint, strength without cruelty, feeling without drowning.
- **Peregrine** (0): Archetype is **unanchored** — could express well in favorable conditions but lacks inherent stability. Swings between shadow poles depending on context.
- **Detriment/Fall** (-5 to -8): Planet gravitates toward one **shadow pole**. Which pole depends on other chart factors (sect, aspects, house). Detriment often → active shadow (wrong expression). Fall often → passive shadow (collapse of function).

**Aristotle's Golden Mean as structural principle:**
Every virtue sits between two vices — excess and deficiency. Courage between recklessness and cowardice. Generosity between prodigality and stinginess. This IS Moore's bipolar shadow system, and it IS the dignity spectrum. The chart shows where someone has natural access to the mean (dignified planets) and where they'll need conscious work to find it (debilitated planets).

**Gender-neutral application:**
These are *human* archetypes, not gendered roles. A woman's Mars in domicile accesses Warrior fullness — disciplined, boundaried, purposeful. A man's Venus in exaltation accesses Lover fullness — alive, empathic, aesthetically attuned. The shadow poles apply equally regardless of gender. Moore wrote about the "mature masculine" but the energies themselves are universal.

**In practice:**
1. Identify which archetypes are strongest (highest dignity planets in that archetype's domain)
2. Identify which are in shadow (debilitated planets)
3. For shadow planets: name BOTH poles, then use aspects/house/sect to indicate which pole dominates
4. Pull KWML material from knowledge graph: `knowledge_search(query="[archetype] shadow integration", tradition="jungian")`
5. Synthesize: the chart shows the *wiring*, Moore shows the *developmental task*

---

## Step 4: Size

Ask: *"What size?"*

| Size | Length | Depth |
|------|--------|-------|
| **XS** | 3-5 sentences | Core pattern, one quote max |
| **S** | 2-3 paragraphs | 2-3 dominant themes |
| **M** | 1-2 pages | All lenses, moderate depth |
| **L** | 3-5 pages | Full narrative, all sections |
| **XL** | 5-10+ pages | Exhaustive, planet-by-planet |

---

## Step 5: Add-ons

Ask: *"Any add-ons? (ZR section, Transits, Ki cycle) Or ready to generate?"*

- **+ZR** — Zodiacal Releasing appendix (L1/L2 chapters, peak periods)
- **+Transits** — Current transits to natal appendix
- **+Ki** — 9 Star Ki cycle appendix (current personal year/month, hexagram)
- **+Midpoints** — Natal midpoint pictures (90° dial, Ebertin delineations + dignity synthesis)
- **+Solar Arcs** — Solar arc directions to natal midpoints (~1°/year timing method)
- **+Sabian** — Sabian symbols for key degrees (midpoint degrees, planet degrees, angles)

*Don't offer an add-on if it's already selected as framework.*

---

## Step 6: Generate

Confirm the full spec, then generate.

### Narrative/Poem Format Rules:
1. **No astro jargon in the portrait** — pure psychology, behavior, felt experience
2. **Non-deterministic language** (unless GTEI) — "may," "likely," "suggests"
3. **Second person** — "you" not "they"
4. **Technical summary as appendix** — tables at END with placements, dignities, scores
5. **Knowledge graph material synthesized** — absorbed into prose, not cited as astrology
6. **Quote rules per size** — XS/S: max 1. M: 1-2 section + 1 closing. L/XL: 2-4 total.

### Key Interpretation Points:
1. **Strongest planet** (highest dignity score) = actual power, lead with this
2. **Chart ruler** (ASC ruler) = appearance — but check its dignity!
3. **Final dispositor** (if any) = where all roads lead
4. **Sect** = which planets are "on their team"

### Calibration:
Dignity score drives narrative weight more than ASC archetype. Lead with strongest planet's lived experience.

### Uniqueness Rule:
Each reading must be interpretively fresh. NO recycling phrases, structures, or openings from previous readings. Same quality, unique expression.

---

## Output

**Save to:** `stella/charts/readings/[name]_[type]_[framework]_[size].md`

**Export as .md file** — don't dump text, send the file.

---

## Stored Charts

Location: `stella/charts/` (JSON files)

Current: chris, micheal, betsy, megan, kelsea, lisa, erica, will, dad

### Bios
Each chart can include an optional `bio` field — what is known about the person, what they've shared about themselves, life context. Stored alongside chart JSON in `stella/charts/`. Bios ground readings in lived reality: the chart says what the wiring is, the bio says how it's lived.

### Cosmobiological Tools (LIVE)
Full design doc: `stella/COSMOBIOLOGY.md`

- **`get_midpoint_interpretation(body_1, body_2)`** — Direct Ebertin COSI lookup for any pair
- **`get_midpoint_pictures(name, orb, top)`** — Full natal cosmobiogram (90° dial, midpoint trees, Ebertin delineations + dignity context)
- **`get_midpoint_transits(name, orb, top)`** — Current transits activating natal midpoints
- **`get_solar_arcs(name, orb, top)`** — Solar arc directions to natal midpoints (~1°/year timing)
- **Sabian symbols**: pending book scan from Buckley — imagery for key degrees (midpoints, angles, planets)

### Knowledge Graph Sources (8,892 chunks)
- 25 astrological texts (Brennan, Tarnas, Lehman, Sasportas, planet PDFs, etc.)
- Ebertin COSI — 78 midpoint pairs (tradition: cosmobiology)
- Moore & Gillette KWML — 160 chunks (tradition: jungian, layer: archetypal)
- I Ching / 9 Star Ki materials

---

## MCP Tools Reference

| Tool | Use |
|------|-----|
| `stella.generate_chart` | Create + save new chart |
| `stella.load_chart` | Load stored chart |
| `stella.list_stored_charts` | List available charts |
| `stella.get_zr_report` | Full ZR report (Brennan format) |
| `stella.get_transits_now` | Current transits to natal |
| `stella.get_ki_reading` | 9 Star Ki + I Ching reading |
| `stella.knowledge_search` | Search texts for deeper material |
| `stella.get_midpoint_interpretation` | Ebertin COSI lookup for a midpoint pair |
| `stella.get_midpoint_pictures` | Natal cosmobiogram (90° dial) |
| `stella.get_midpoint_transits` | Current transits to natal midpoints |
| `stella.get_solar_arcs` | Solar arc directions to natal midpoints |
| `stella.discover` | What's most active in a chart right now |
| `stella.reflect` | Generate insight from chart patterns |
| `stella.recall` | Retrieve stored chart memories |
