"""
Seed Wu Xing (Five Elements) framework into Neo4j knowledge graph.

Creates Element nodes, links them to Planet nodes, and establishes
generating (相生) and overcoming (相克) cycles as relationships.
Also creates WuXingCorrespondence nodes for the full association matrix.
"""

from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "selene_gnosis")

# ── Wu Xing Element Data ──

ELEMENTS = {
    "Water": {
        "chinese": "水",
        "pinyin": "Shuǐ",
        "planet": "Mercury",
        "planet_chinese": "水星",
        "direction": "North",
        "season": "Winter",
        "color": "Black / Deep Blue",
        "organs": "Kidneys, Bladder",
        "challenge_emotion": "Fear, Anxiety",
        "wisdom_emotion": "Willpower, Courage",
        "taste": "Salty",
        "climate": "Cold",
        "time_of_day": "Night",
        "stage_of_life": "Old Age / Death & Regeneration",
        "virtue": "Wisdom",
        "sacred_animal": "Black Tortoise",
        "description": "Water is the most yin element — formless, penetrating, foundational. The kidneys store jing (essence), the deepest vital substance. Fear and willpower are two faces of the same Water energy.",
    },
    "Metal": {
        "chinese": "金",
        "pinyin": "Jīn",
        "planet": "Venus",
        "planet_chinese": "金星",
        "direction": "West",
        "season": "Autumn",
        "color": "White / Silver / Gold",
        "organs": "Lungs, Large Intestine",
        "challenge_emotion": "Grief, Sadness",
        "wisdom_emotion": "Righteousness, Integrity",
        "taste": "Pungent / Spicy",
        "climate": "Dry",
        "time_of_day": "Evening / Dusk",
        "stage_of_life": "Late Adulthood / Harvest",
        "virtue": "Righteousness",
        "sacred_animal": "White Tiger",
        "description": "Metal cuts away what is unnecessary to reveal what is essential. The lungs govern breath — the most fundamental letting-go process. Grief unprocessed constricts the lungs; grief fully felt becomes integrity.",
    },
    "Fire": {
        "chinese": "火",
        "pinyin": "Huǒ",
        "planet": "Mars",
        "planet_chinese": "火星",
        "direction": "South",
        "season": "Summer",
        "color": "Red",
        "organs": "Heart, Small Intestine",
        "challenge_emotion": "Agitation, Excess Excitement",
        "wisdom_emotion": "Joy, Warmth, Clarity",
        "taste": "Bitter",
        "climate": "Hot",
        "time_of_day": "Noon",
        "stage_of_life": "Youth / Peak Expression",
        "virtue": "Propriety / Right Action",
        "sacred_animal": "Vermilion Bird (Phoenix)",
        "description": "The heart is the emperor organ, housing the shen (spirit/consciousness). Agitation is Fire without direction; joy is Fire in rightful expression — warmth without combustion.",
    },
    "Wood": {
        "chinese": "木",
        "pinyin": "Mù",
        "planet": "Jupiter",
        "planet_chinese": "木星",
        "direction": "East",
        "season": "Spring",
        "color": "Green / Blue-Green",
        "organs": "Liver, Gallbladder",
        "challenge_emotion": "Frustration, Resentment, Anger",
        "wisdom_emotion": "Kindness, Benevolence, Vision",
        "taste": "Sour",
        "climate": "Windy",
        "time_of_day": "Morning / Dawn",
        "stage_of_life": "Childhood / New Beginnings",
        "virtue": "Benevolence / Humaneness",
        "sacred_animal": "Azure Dragon",
        "description": "The liver governs smooth flow of qi. When blocked: frustration and resentment (qi stuck). When free: benevolence and vision moving outward like branches toward light.",
    },
    "Earth": {
        "chinese": "土",
        "pinyin": "Tǔ",
        "planet": "Saturn",
        "planet_chinese": "土星",
        "direction": "Center",
        "season": "Late Summer / Inter-seasonal transitions",
        "color": "Yellow / Brown",
        "organs": "Spleen, Stomach",
        "challenge_emotion": "Worry, Overthinking, Rumination",
        "wisdom_emotion": "Trust, Groundedness, Centeredness",
        "taste": "Sweet",
        "climate": "Damp",
        "time_of_day": "Midday transition",
        "stage_of_life": "Middle Age / Transitions",
        "virtue": "Faithfulness / Integrity",
        "sacred_animal": "Yellow Dragon / Qilin",
        "description": "Saturn holds the center — no cardinal direction, the axis around which all others rotate. The spleen-stomach axis transforms food into qi; an imbalanced Earth mind chews on problems it can't digest.",
    },
}

# Generating Cycle (相生): Mother feeds Child
GENERATING_CYCLE = [
    ("Wood", "Fire"),      # Wood feeds Fire
    ("Fire", "Earth"),     # Fire creates Earth (ash)
    ("Earth", "Metal"),    # Earth bears Metal
    ("Metal", "Water"),    # Metal collects Water
    ("Water", "Wood"),     # Water nourishes Wood
]

# Overcoming Cycle (相克): Controller checks Controlled
OVERCOMING_CYCLE = [
    ("Wood", "Earth"),     # Wood parts Earth (roots)
    ("Earth", "Water"),    # Earth dams Water
    ("Water", "Fire"),     # Water extinguishes Fire
    ("Fire", "Metal"),     # Fire melts Metal
    ("Metal", "Wood"),     # Metal cuts Wood
]


def seed_wuxing():
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    with driver.session() as s:
        # ── Create Element nodes ──
        for name, data in ELEMENTS.items():
            s.run("""
                MERGE (e:Element {name: $name})
                SET e.chinese = $chinese,
                    e.pinyin = $pinyin,
                    e.direction = $direction,
                    e.season = $season,
                    e.color = $color,
                    e.organs = $organs,
                    e.challenge_emotion = $challenge_emotion,
                    e.wisdom_emotion = $wisdom_emotion,
                    e.taste = $taste,
                    e.climate = $climate,
                    e.time_of_day = $time_of_day,
                    e.stage_of_life = $stage_of_life,
                    e.virtue = $virtue,
                    e.sacred_animal = $sacred_animal,
                    e.description = $description,
                    e.planet_chinese = $planet_chinese,
                    e.framework = 'wuxing',
                    e.source = 'Wu xing zhan (五星占), pre-168 BCE'
            """, name=name, **data)
            print(f"  ✓ Element: {name} ({data['chinese']} {data['pinyin']})")

        # ── Link Elements to Planet nodes ──
        for name, data in ELEMENTS.items():
            result = s.run("""
                MATCH (e:Element {name: $element})
                MATCH (p:Planet {name: $planet})
                MERGE (p)-[:EMBODIES_ELEMENT]->(e)
                MERGE (e)-[:MANIFESTS_AS]->(p)
                RETURN p.name
            """, element=name, planet=data["planet"])
            rec = result.single()
            if rec:
                print(f"  ✓ {data['planet']} ↔ {name}")
            else:
                print(f"  ⚠ Planet node '{data['planet']}' not found — link skipped")

        # ── Generating Cycle (相生) ──
        print("\nGenerating Cycle (相生):")
        for mother, child in GENERATING_CYCLE:
            s.run("""
                MATCH (m:Element {name: $mother})
                MATCH (c:Element {name: $child})
                MERGE (m)-[:GENERATES {cycle: 'shēng', chinese: '相生', meaning: 'mother feeds child'}]->(c)
                MERGE (c)-[:GENERATED_BY]->(m)
            """, mother=mother, child=child)
            print(f"  {mother} → {child}")

        # ── Overcoming Cycle (相克) ──
        print("\nOvercoming Cycle (相克):")
        for controller, controlled in OVERCOMING_CYCLE:
            s.run("""
                MATCH (ct:Element {name: $controller})
                MATCH (cd:Element {name: $controlled})
                MERGE (ct)-[:OVERCOMES {cycle: 'kè', chinese: '相克', meaning: 'controller checks controlled'}]->(cd)
                MERGE (cd)-[:OVERCOME_BY]->(ct)
            """, controller=controller, controlled=controlled)
            print(f"  {controller} → {controlled}")

        # ── Create interpretation nodes for each element ──
        print("\nInterpretation nodes:")
        for name, data in ELEMENTS.items():
            # Body-mind-emotion interpretation
            content = (
                f"Wu Xing {name} ({data['chinese']} {data['pinyin']}): "
                f"{data['description']} "
                f"Organs: {data['organs']}. "
                f"Challenge emotion: {data['challenge_emotion']}. "
                f"Wisdom emotion: {data['wisdom_emotion']}. "
                f"Virtue: {data['virtue']}. "
                f"Direction: {data['direction']}, Season: {data['season']}, "
                f"Sacred animal: {data['sacred_animal']}."
            )
            s.run("""
                MERGE (i:Interpretation {chunk_id: $chunk_id})
                SET i.content = $content,
                    i.source = 'Wu xing zhan',
                    i.author = 'Chinese cosmological tradition',
                    i.layer = 'philosophical',
                    i.framework = 'wuxing',
                    i.element = $element,
                    i.planet = $planet
                WITH i
                MATCH (p:Planet {name: $planet})
                MERGE (i)-[:DESCRIBES]->(p)
                WITH i
                MATCH (e:Element {name: $element})
                MERGE (i)-[:DESCRIBES_ELEMENT]->(e)
            """, chunk_id=f"wuxing_{name.lower()}", content=content,
                element=name, planet=data["planet"])
            print(f"  ✓ Interpretation: {name} ({data['planet']})")

        # ── Transit interaction interpretations ──
        print("\nTransit interaction interpretations:")
        for mother, child in GENERATING_CYCLE:
            m_planet = ELEMENTS[mother]["planet"]
            c_planet = ELEMENTS[child]["planet"]
            content = (
                f"Wu Xing Generating: {m_planet} ({mother}) transit to natal {c_planet} ({child}). "
                f"{mother} feeds {child} — expansion, support, nourishment. "
                f"The {ELEMENTS[mother]['wisdom_emotion'].split(',')[0].strip()} of {mother} "
                f"fuels the {ELEMENTS[child]['wisdom_emotion'].split(',')[0].strip()} of {child}. "
                f"Organ axis: {ELEMENTS[mother]['organs']} supporting {ELEMENTS[child]['organs']}."
            )
            s.run("""
                MERGE (i:Interpretation {chunk_id: $chunk_id})
                SET i.content = $content,
                    i.source = 'Wu xing zhan',
                    i.author = 'Chinese cosmological tradition',
                    i.layer = 'philosophical',
                    i.framework = 'wuxing',
                    i.interaction = 'generating'
            """, chunk_id=f"wuxing_gen_{mother.lower()}_{child.lower()}", content=content)
            print(f"  ✓ {m_planet}({mother}) generates {c_planet}({child})")

        for controller, controlled in OVERCOMING_CYCLE:
            ct_planet = ELEMENTS[controller]["planet"]
            cd_planet = ELEMENTS[controlled]["planet"]
            content = (
                f"Wu Xing Overcoming: {ct_planet} ({controller}) transit to natal {cd_planet} ({controlled}). "
                f"{controller} checks {controlled} — productive tension, discipline, restructuring. "
                f"The {ELEMENTS[controller]['wisdom_emotion'].split(',')[0].strip()} of {controller} "
                f"shapes the {ELEMENTS[controlled]['challenge_emotion'].split(',')[0].strip()} of {controlled}. "
                f"Organ axis: {ELEMENTS[controller]['organs']} constraining {ELEMENTS[controlled]['organs']}."
            )
            s.run("""
                MERGE (i:Interpretation {chunk_id: $chunk_id})
                SET i.content = $content,
                    i.source = 'Wu xing zhan',
                    i.author = 'Chinese cosmological tradition',
                    i.layer = 'philosophical',
                    i.framework = 'wuxing',
                    i.interaction = 'overcoming'
            """, chunk_id=f"wuxing_over_{controller.lower()}_{controlled.lower()}", content=content)
            print(f"  ✓ {ct_planet}({controller}) overcomes {cd_planet}({controlled})")

        # ── Verify ──
        result = s.run("MATCH (e:Element) RETURN count(e) as count").single()
        print(f"\n✅ Total Element nodes: {result['count']}")

        result = s.run("MATCH ()-[r:GENERATES]->() RETURN count(r) as count").single()
        print(f"✅ Generating relationships: {result['count']}")

        result = s.run("MATCH ()-[r:OVERCOMES]->() RETURN count(r) as count").single()
        print(f"✅ Overcoming relationships: {result['count']}")

        result = s.run("MATCH ()-[r:EMBODIES_ELEMENT]->() RETURN count(r) as count").single()
        print(f"✅ Planet-Element links: {result['count']}")

        result = s.run("MATCH (i:Interpretation {framework: 'wuxing'}) RETURN count(i) as count").single()
        print(f"✅ Wu Xing interpretations: {result['count']}")

    driver.close()
    print("\n🌀 Wu Xing seeding complete.")


if __name__ == "__main__":
    seed_wuxing()
