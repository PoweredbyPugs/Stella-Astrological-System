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

### Diverge Phase
Two readings of the same chart, using **maximally distant** frameworks. Each reading is independent — it does not reference or respond to the other. The frameworks are chosen to have maximum conceptual distance (different distance groups in the config).

### Converge Phase
Read both diverge passages. State **ONLY** what both arrived at independently. Rules:
- No framework vocabulary
- Maximum one paragraph
- Plain language only
- If they don't overlap, say so — that's data too

### Temperature Descent
The temperature curve controls creative range across passes:

```
Pass:  D1  D2  C1  D3  D4  C2  D5  D6  C3
Temp:   9   9   5   7   7   3   5   5   1
```

Early rounds are feral (temp 9) — maximum creative divergence. Later rounds cool toward precision. The final convergence at temp 1 is maximally coherent.

### Framework Selection
Frameworks have **distance groups** (A, B, C, D). Divergent pairs are always drawn from **different** groups to maximize conceptual distance:
- A (structural/geometric): gtei, cosmobiological
- B (developmental/mythic): psychological, archetypal
- C (ethical): stoic
- D (energetic): ki

Round 1 might pair gtei (A) with psychological (B). Round 2 might pair stoic (C) with ki (D). The goal is maximum distance between each pair.

### Termination
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

## Example

The first autopoietic process on Chris's chart produced this terminal statement:

> "You don't connect with people by showing up — you connect by building something and handing it to them. The gift IS the bridge. Without it, you're just standing there."

This emerged from GTEI (structural self-consistency analysis), psychological (attachment/developmental), and cosmobiological (midpoint pictures) — three completely different vocabularies arriving at the same claim about Mercury-Saturn-Node wiring.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `autopoietic_init` | Start a session, get first framework pair |
| `autopoietic_submit` | Submit a diverge or converge pass |
| `autopoietic_converge` | Get the convergence prompt for current round |
| `autopoietic_status` | Check progress, get next assignment or termination |

## Session Files

Sessions stored in `stella/autopoietic/sessions/{session_id}.json`. Each session tracks all rounds, frameworks used/remaining, and convergence statements.
