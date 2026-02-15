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
| **GTEI** | Absolute Self-Consistency, 5 Primordial Categories, deterministic. |
| **Ki** | Blend 5.9.1 (or whatever the natal pattern is) INTO the astrological interpretation. Essence shapes identity themes, Emotion shapes Moon/Venus themes, Life Path shapes nodal/career themes. Full synthesis. |
| **ZR** | Zodiacal Releasing as primary timing lens — life chapters, peak periods. |
| **Stoic** | Virtue, fate, dichotomy of control. *(needs more books)* |
| **Cosmobiological** | Midpoint pictures as structural framework, fleshed out with dignities, depositors, houses. Ebertin + Hellenistic synthesis. |

**Frameworks are mixable:** Psychological + Ki ✓ | GTEI + ZR ✓ | etc.

### Ki Framework Integration Guide
When Ki is selected as a **framework** (not type):
- **Essence (1st number)** → weave into Sun/ASC/identity interpretation
- **Emotion (2nd number)** → weave into Moon/Venus/emotional core interpretation  
- **Life Path (3rd number)** → weave into Node/MC/career/external perception interpretation
- Element relationships (productive/controlling cycles) inform planetary relationships

This is NOT a separate Ki section — it's a lens that colors the entire reading.

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

### Cosmobiological Forecasting (TODO)
- **Solar arc directions**: natal position + (age × ~0.9856°) — primary cosmobiological timing
- **Transit midpoint pictures**: transiting planet hitting natal midpoints
- **Midpoint transit pictures**: two transiting planets forming midpoint on natal planet
- **Knowledge source**: Ebertin, *The Combination of Stellar Influences* (OCR'd, ~/clawd/ebertin-cosi-full.txt)
- **Sabian symbols**: pending book scan from Buckley — imagery for key degrees (midpoints, angles, planets)
- Integrate into Stella as tools: `get_midpoint_pictures`, `get_solar_arcs`, `get_midpoint_transits`

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
