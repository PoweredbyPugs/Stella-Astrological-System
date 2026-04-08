# Autopoietic Chart Reading

## What It Is

An autopoietic chart is a **self-creating reading** that emerges through iterative divergence and convergence. Instead of one framework producing one interpretation, multiple maximally distant frameworks independently read the same chart, and the overlap between their readings — what they arrive at independently — becomes the signal.

The word *autopoietic* means "self-creating." The reading creates itself through the process. No single framework authors the final statement — it emerges from the collision.

## The Cycle

```
Round 1: DIVERGE (Framework A + Framework B, temp 9)
              ↓
         CONVERGE (find overlap, temp 5)
              ↓
Round 2: DIVERGE (Framework C + Framework D, temp 7, seeded with convergence)
              ↓
         CONVERGE (find overlap, temp 3)
              ↓
Round N: DIVERGE → CONVERGE → ... until convergence produces nothing new
              ↓
         TERMINAL STATEMENT
```

---

## ⚠️ CRITICAL: Isolation Protocol

### Diverge passes MUST be biographically blind.

Each diverge reading runs in an **isolated sub-agent session** (`sessions_spawn`). The sub-agent receives ONLY:
1. **Chart data** — placements, dignities, houses, aspects, lots (JSON from `load_chart`)
2. **Midpoint pictures** — 90° dial output from `get_midpoint_pictures`
3. **Knowledge graph material** — queried BEFORE spawning, specific to the assigned framework's tradition/layer
4. **Framework instructions** — lens, vocabulary, temperature, output type
5. **Convergence seed** (rounds 2+) — the previous round's convergence statement

The sub-agent does **NOT** receive:
- ❌ MEMORY.md or any memory files
- ❌ USER.md or biographical context
- ❌ SOUL.md or IDENTITY.md
- ❌ Conversation history
- ❌ The other diverge reading from the same round
- ❌ Any knowledge of who the person IS beyond their chart

**WHY:** If the operator knows the person, biographical knowledge contaminates the reading. The operator unconsciously steers toward conclusions they already believe. Convergence becomes manufactured rather than discovered. The entire value of the autopoietic process — that independent frameworks arrive at the same signal from the math alone — is destroyed.

### Mandatory Knowledge Graph Grounding

Every diverge pass MUST be built from source material:

1. **Before spawning** each sub-agent, the main session queries the knowledge graph with framework-specific searches:
   - Archetypal → `tradition=jungian`, layer=archetypal
   - Psychological → `layer=psychological`, relevant planet/house queries
   - GTEI → query for self-consistency, primordial categories
   - Stoic → `layer=philosophical`, Stoic-specific terms
   - Ki → Ki/I Ching materials
   - Cosmobiological → `tradition=cosmobiology`, Ebertin COSI lookups
2. **The knowledge graph results are included in the sub-agent's task prompt.**
3. **Every claim in the reading must trace back to** either chart geometry (a placement, dignity, midpoint picture) or a knowledge graph chunk. No claims from general knowledge.
4. If the knowledge graph has insufficient material for a framework, note the gap — don't fill it with improvisation.

### Convergence stays in the main session

Convergence passes are synthesis — they compare the diverge outputs and extract overlap. The main session operator handles convergence because:
- They need to read both diverge passages
- They need prior convergence history for termination checks
- Biographical knowledge doesn't contaminate convergence (you're comparing two blind readings, not generating claims)

---

## Diverge Phase

Two readings of the same chart, using **maximally distant** frameworks. Each reading is independent — it does not reference or respond to the other. The frameworks are chosen to have maximum conceptual distance (different distance groups in the config).

### Sub-Agent Task Template

```
You are generating an astrological reading. You have NO information about who this person is 
beyond the chart data below. Do not speculate about their life, personality, or circumstances 
from anything other than the chart geometry and the source material provided.

FRAMEWORK: {framework_name} ({lens} lens)
VOCABULARY: {vocabulary}
OUTPUT TYPE: {type} (narrative/technical/poem/cosmobiogram)
TEMPERATURE: {temperature}

CHART DATA:
{chart_json}

MIDPOINT PICTURES:
{midpoint_output}

KNOWLEDGE GRAPH MATERIAL:
{kg_results}

{SEED (if round 2+):}
Previous convergence found: "{convergence_text}"
Explore this through your framework's lens — do NOT restate it. Find what your framework 
adds or challenges.

RULES:
- Every claim must trace to chart geometry or the source material above
- Do not invent biographical details
- Do not reference any other framework
- Write in the assigned output type and temperature
```

## Converge Phase

Read both diverge passages. State **ONLY** what both arrived at independently. Rules:
- No framework vocabulary
- Plain language only
- If they don't overlap, say so — that's data too
- Be as brief or as long as the truth requires
- **PRESERVE CONCRETENESS.** If a diverge terminal describes a person doing something — keep the person doing the thing. Do not abstract "sits down in his own chair" into "reclaims inner authority." The image IS the insight. The composite terminal must pass the falsifiability test: could you watch this person for a week and confirm or deny each claim?

## Temperature Descent

The temperature curve controls creative range across passes:

```
Pass:  D1  D2  C1  D3  D4  C2  D5  D6  C3
Temp:   9   9   5   7   7   3   5   5   1
```

Early rounds are feral (temp 9) — maximum creative divergence. Later rounds cool toward precision. The final convergence at temp 1 is maximally coherent.

## Framework Selection

Frameworks have **distance groups** (A, B, C, D). Divergent pairs are always drawn from **different** groups to maximize conceptual distance:
- A (structural/geometric): gtei, cosmobiological
- B (developmental/mythic): psychological, archetypal
- C (ethical): stoic
- D (energetic): ki

Round 1 might pair gtei (A) with psychological (B). Round 2 might pair stoic (C) with ki (D). The goal is maximum distance between each pair.

## Termination

The process terminates when a convergence pass produces **no new claims** not already present in the previous convergence. At that point, the signal has been fully extracted — further divergence would just be noise.

## Adding New Frameworks

Edit `stella/autopoietic/config.json`. Add a new entry to `frameworks`:

```json
"vedic": { "lens": "karmic", "vocabulary": "dashas, nakshatras, yogas", "distance_group": "E" }
```

That's it. The selection algorithm will incorporate it automatically. New distance groups create new pairing possibilities.

## Results → Emergent Triad

The final convergence statement feeds back into the chart's memory — but ONLY after user validation:
- Presented to the user first. Always.
- Stored as `validated: false` until the user confirms resonance
- Once validated, saved as an insight in `charts/memory/{name}.json`
- Tagged with all frameworks used and `autopoietic` technique
- Never auto-validated. The system proposes. The human confirms.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `autopoietic_init` | Start a session, get first framework pair |
| `autopoietic_submit` | Submit a diverge or converge pass |
| `autopoietic_converge` | Get the convergence prompt for current round |
| `autopoietic_status` | Check progress, get next assignment or termination |

## Session Files

Sessions stored in `stella/autopoietic/sessions/{session_id}.json`. Each session tracks all rounds, frameworks used/remaining, and convergence statements.

---

## Lessons Learned

### 2026-02-24 — First Test (Sonnet)
- Sonnet produced flat thematic summaries — needs a heavier model for diverge phases
- Terminal statements must describe a PERSON, not a CONCEPT — concrete, behavioral, falsifiable
- Global insights about Stella tools belong in the protocol, not individual chart memory

### 2026-02-25 — Second Test (Opus, contaminated)
- Biographical knowledge contaminated all 8 diverge passes — operator knew the person and steered toward pre-existing conclusions
- Knowledge graph was used inconsistently — some passes barely touched it, others not at all
- Convergence appeared strong but was manufactured, not discovered
- **Fix:** Isolation protocol added. Diverge passes run as blind sub-agents. Knowledge graph queries are mandatory and pre-loaded.

### 2026-02-25 — Third Test (Opus, blind, v3)
- Isolation protocol worked — diverge passes were genuinely blind, produced novel findings
- **Convergence operator FLATTENED good diverge terminals into abstraction.** The diverge sub-agents wrote concrete, behavioral, falsifiable terminals. The convergence pass and final composite replaced them with theme statements and astro-jargon disguised as person-descriptions.
- ANTI-PATTERN: "The discipline is real and exalted" — astro concept, not a person. "The depth perception is structural and permanent" — abstract property, not observable behavior. These describe a chart, not a human.
- GOOD EXAMPLES from the diverge passes that the convergence SHOULD have preserved:
  - Stoic: "the day this person recognizes their solitude as a choice they've been making every single day"
  - Archetypal: "the day he sits down in his own chair — not earns it, not deserves it, sits"
  - Ki: "someone who appears calm at the center of complexity and periodically mistakes their own structural patience for paralysis"
- **Fix:** Convergence passes must PRESERVE the concreteness of diverge terminals. The composite terminal must describe what a person DOES, how they BEHAVE, what you would SEE watching them — not what their chart means. If a diverge pass wrote something concrete and the convergence abstracts it, the convergence failed.
