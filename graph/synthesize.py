"""
Graph-driven interpretation synthesis.
Walk the graph, collect everything, produce a structured narrative scaffold.
The synthesis emerges from the WALK, not from pre-written text.
"""

from neo4j import GraphDatabase
try:
    from graph.neo4j_tools import walk_interpretation, traverse_chain, find_receptions, get_midpoint_pictures
except ImportError:
    from neo4j_tools import walk_interpretation, traverse_chain, find_receptions, get_midpoint_pictures

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "selene_gnosis")


def synthesize_placement(chart_name: str, planet: str) -> str:
    """
    Generate a narrative scaffold for a single placement
    by walking the graph and weaving together everything connected.
    
    This is NOT a finished reading — it's the raw material organized
    for interpretation. The interpreter (human or AI) adds the synthesis.
    """
    walk = walk_interpretation(chart_name, planet)
    
    if "error" in walk:
        return walk["error"]
    
    p = walk["placement"]
    lines = []
    
    # Header
    lines.append(f"# {p['planet']} — Graph Walk Synthesis")
    lines.append(f"*{chart_name} | {p['planet']} in {p['sign']} {p['degree']:.1f}° | House {p['house']} ({walk['house'].get('house_name', '?')})*")
    lines.append("")
    
    # Dignity assessment
    score = p['dignity_score']
    condition = p['condition']
    decan = walk.get('decan', {})
    term = walk.get('term', {})
    
    lines.append("## Essential Condition")
    lines.append(f"- **Score:** {score} ({condition})")
    if decan:
        lines.append(f"- **Decan:** {decan.get('decan', '?')} (face ruler: {decan.get('face_ruler', '?')})")
    if term:
        lines.append(f"- **Term:** {term.get('term', '?')}")
    
    # Check if in own face/term for minor dignity
    if decan.get('face_ruler') == planet:
        lines.append(f"  → *In own face: +1 minor dignity (recognition by appearance)*")
    if term.get('term_ruler') == planet:
        lines.append(f"  → *In own term: +2 minor dignity (operates within own boundaries)*")
    
    lines.append("")
    
    # Sign context from ontology
    sp = walk.get('sign_properties', {})
    if sp:
        lines.append("## Sign Context")
        lines.append(f"- **{sp.get('sign', '?')}** — {sp.get('element', '?')} {sp.get('modality', '?')}")
        lines.append(f"- Ruler: {sp.get('ruler', '?')} | Exalted: {sp.get('exalted_planet', 'none')}")
        lines.append("")
    
    # Depositor chain
    chain = walk['depositor_chain']
    if chain.get('chain'):
        chain_str = " → ".join(
            f"{c['planet']}({'✦' if c.get('dignity_score', 0) >= 4 else '○' if c.get('dignity_score', 0) == 0 else '◐'})"
            for c in chain['chain']
        )
        lines.append("## Depositor Chain")
        lines.append(f"  {chain_str}")
        lines.append(f"  Terminus: **{chain.get('final_dispositor', '?')}**")
        
        # Narrative: how energy flows
        if len(chain['chain']) > 1:
            lines.append(f"  *{planet}'s expression is mediated through {len(chain['chain'])-1} intermediaries before reaching {chain['final_dispositor']}.*")
            lines.append(f"  *Every peregrine step (○) is a wandering — the energy passes through without belonging.*")
        lines.append("")
    
    # Who deposits here
    receives = walk.get('receives_deposits_from', [])
    if receives:
        lines.append("## Receives Deposits From")
        for r in receives:
            lines.append(f"  - **{r['planet']}** in {r['sign']} (score: {r['score']})")
        lines.append(f"  *{planet} serves as conduit for {', '.join(r['planet'] for r in receives)}*")
        lines.append("")
    
    # Aspects
    aspects = walk.get('aspects', [])
    if aspects:
        lines.append("## Aspect Network")
        for a in aspects:
            symbol = {"conjunction": "☌", "sextile": "⚹", "square": "□", "trine": "△", "opposition": "☍"}.get(a['aspect_type'], '?')
            lines.append(f"  {symbol} **{a['planet2']}** ({a['aspect_type']}, {a['orb']}°)")
        lines.append("")
    
    # Midpoint pictures
    midpoints = walk.get('midpoint_pictures', [])
    if midpoints:
        lines.append("## Midpoint Pictures (90° Dial)")
        for mp in midpoints:
            lines.append(f"  {planet} = {mp['axis1']}/{mp['axis2']} ({mp['orb']}°)")
        lines.append("")
    
    # Text interpretations from knowledge base
    interps = walk.get('interpretations', [])
    if interps:
        lines.append("## Source Texts")
        for i, interp in enumerate(interps):
            source = interp.get('source', 'unknown')
            text = (interp.get('text', '') or '')[:300].strip()
            if text:
                lines.append(f"  **[{source}]**: {text}...")
                lines.append("")
    
    # Connected insights (emergent triad)
    insights = walk.get('insights', [])
    if insights:
        lines.append("## Connected Insights")
        for ins in insights:
            validated = "✓" if ins.get('validated') else "○"
            rating = ins.get('rating', 0)
            lines.append(f"  [{validated} {rating}/5] {ins.get('text', '')[:200]}")
        lines.append("")
    
    # Synthesis prompt
    lines.append("## Synthesis Questions")
    lines.append(f"*These emerge from the graph walk — the interpreter addresses them:*")
    
    # Generate questions from the data
    questions = []
    
    if score == 0:
        questions.append(f"How does {planet} peregrine express its sign's qualities WITHOUT belonging there?")
    elif score >= 4:
        questions.append(f"What does {planet} in full dignity DO with that power in house {p['house']}?")
    
    if receives:
        for r in receives:
            if r['score'] == 0:
                questions.append(f"What happens when peregrine {r['planet']}'s wandering energy deposits into {planet}?")
    
    if aspects:
        tightest = aspects[0]
        questions.append(f"The tightest aspect ({tightest['planet2']} {tightest['aspect_type']} at {tightest['orb']}°) — how does this define {planet}'s daily operation?")
    
    if chain.get('chain') and len(chain['chain']) > 2:
        questions.append(f"The chain passes through {len(chain['chain'])-1} steps to reach {chain['final_dispositor']}. What gets lost or transformed along the way?")
    
    if decan.get('face_ruler') == planet:
        questions.append(f"{planet} in its own face — what mask does it wear that matches its nature?")
    
    for q in questions:
        lines.append(f"  - {q}")
    
    return "\n".join(lines)


def synthesize_chart(chart_name: str) -> str:
    """Generate a full chart synthesis scaffold by walking every planet."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    
    lines = [f"# Chart Synthesis — {chart_name}", ""]
    
    with driver.session() as s:
        # Chart metadata
        chart = s.run("MATCH (c:Chart {name: $n}) RETURN c", n=chart_name).single()
        if chart:
            c = dict(chart["c"])
            lines.append(f"*{c.get('date', '?')} {c.get('time', '?')} {c.get('timezone', '?')}*")
            lines.append(f"*Day chart: {c.get('day_chart', '?')} | Final dispositor: {c.get('final_dispositor', '?')}*")
            lines.append("")
        
        # Receptions
        recs = find_receptions(chart_name)
        if recs:
            lines.append("## Mutual Receptions")
            for r in recs:
                lines.append(f"  {r['planet1']} ↔ {r['planet2']} (by {r['reception_type']})")
            lines.append("")
        
        # Walk each traditional planet
        planets = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
        for planet in planets:
            synthesis = synthesize_placement(chart_name, planet)
            lines.append(synthesis)
            lines.append("\n---\n")
    
    driver.close()
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    chart = sys.argv[1] if len(sys.argv) > 1 else "chris"
    planet = sys.argv[2] if len(sys.argv) > 2 else None
    
    if planet:
        print(synthesize_placement(chart, planet))
    else:
        print(synthesize_chart(chart))
