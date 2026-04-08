#!/usr/bin/env python3
"""
Ingest EPUBs into Stella's Neo4j knowledge graph.
Run with: /home/atlas/clawd/stella/.ingest-venv/bin/python3.13 ingest_epubs.py

Handles: Tao Te Ching (Hinton), Sepher Yetzirah (Warwick)
"""

import re
import hashlib
import zipfile
import html
from pathlib import Path
from neo4j import GraphDatabase

# ── Config ──
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "selene_gnosis")

MAX_CHUNK_CHARS = 3200
MIN_CHUNK_CHARS = 100
OVERLAP_CHARS = 200

BOOKS = [
    {
        "epub": Path("/home/atlas/clawd/stella/ingest-tmp-tao.epub"),
        "title": "Tao Te Ching",
        "author": "Lao Tzu (David Hinton translation)",
        "trust_tier": 1,
        "layer": "philosophical",
        "tradition": "taoist",
    },
    {
        "epub": Path("/home/atlas/clawd/stella/ingest-tmp-sepher.epub"),
        "title": "The Sepher Yetzirah",
        "author": "Unknown (Tarl Warwick edition)",
        "trust_tier": 1,
        "layer": "hermetic",
        "tradition": "kabbalistic",
    },
]

# ── Ontology tagging ──
PLANETS = {
    "sun": [r"\bsun\b", r"\bsolar\b", r"\bsol\b"],
    "moon": [r"\bmoon\b", r"\blunar\b", r"\bluna\b"],
    "mercury": [r"\bmercury\b", r"\bmercurial\b"],
    "venus": [r"\bvenus\b", r"\bvenusian\b"],
    "mars": [r"\bmars\b", r"\bmartial\b"],
    "jupiter": [r"\bjupiter\b", r"\bjovial\b"],
    "saturn": [r"\bsaturn\b", r"\bsaturnine\b"],
    "uranus": [r"\buranus\b", r"\buranian\b"],
    "neptune": [r"\bneptune\b", r"\bneptunian\b"],
    "pluto": [r"\bpluto\b", r"\bplutonian\b"],
}

SIGNS = {
    "aries": [r"\baries\b"], "taurus": [r"\btaurus\b"],
    "gemini": [r"\bgemini\b"], "cancer": [r"\bcancer\b"],
    "leo": [r"\bleo\b"], "virgo": [r"\bvirgo\b"],
    "libra": [r"\blibra\b"], "scorpio": [r"\bscorpio\b"],
    "sagittarius": [r"\bsagittarius\b"], "capricorn": [r"\bcapricorn\b"],
    "aquarius": [r"\baquarius\b"], "pisces": [r"\bpisces\b"],
}

ASPECTS = {
    "conjunction": [r"\bconjunction\b", r"\bconjunct\b"],
    "opposition": [r"\bopposition\b", r"\boppose\b"],
    "trine": [r"\btrine\b"], "square": [r"\bsquare\b"],
    "sextile": [r"\bsextile\b"],
}

# Hebrew letters for Sepher Yetzirah
HEBREW = {
    "aleph": r"\baleph?\b", "beth": r"\bbeth?\b", "gimel": r"\bgimel\b",
    "daleth": r"\bdaleth?\b", "he": r"\bh[eé]\b", "vav": r"\bvav\b",
    "zayin": r"\bzayin\b", "cheth": r"\bcheth?\b", "teth": r"\bteth?\b",
    "yod": r"\byod\b", "kaph": r"\bkaph?\b", "lamed": r"\blamed\b",
    "mem": r"\bmem\b", "nun": r"\bnun\b", "samekh": r"\bsamekh\b",
    "ayin": r"\bayin\b", "pe": r"\bpe[h]?\b", "tzaddi": r"\btzaddi\b",
    "qoph": r"\bqoph\b", "resh": r"\bresh\b", "shin": r"\bshin\b",
    "tau": r"\btau\b",
}

SEPHIROTH = {
    "kether": r"\bkether\b", "chokmah": r"\bchokmah\b", "binah": r"\bbinah\b",
    "chesed": r"\bchesed\b", "geburah": r"\bgeburah\b", "tiphareth": r"\btiphareth\b",
    "netzach": r"\bnetzach\b", "hod": r"\bhod\b", "yesod": r"\byesod\b",
    "malkuth": r"\bmalkuth\b",
}


def extract_epub_text(epub_path):
    """Extract text from EPUB."""
    with zipfile.ZipFile(epub_path) as z:
        parts = []
        for name in sorted(z.namelist()):
            if name.endswith(('.html', '.xhtml', '.htm')):
                raw = z.read(name).decode('utf-8', errors='ignore')
                clean = re.sub(r'<[^>]+>', ' ', raw)
                clean = html.unescape(clean)
                clean = re.sub(r'\s+', ' ', clean).strip()
                if len(clean) > 50:
                    parts.append(clean)
    return '\n\n'.join(parts)


def chunk_text(text, max_chars=MAX_CHUNK_CHARS, min_chars=MIN_CHUNK_CHARS, overlap=OVERLAP_CHARS):
    """Split text into overlapping chunks at paragraph boundaries."""
    paragraphs = re.split(r'\n{2,}', text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 > max_chars and len(current) >= min_chars:
            chunks.append(current.strip())
            # Overlap: keep last portion
            words = current.split()
            overlap_text = ' '.join(words[-overlap // 6:]) if len(words) > overlap // 6 else ''
            current = overlap_text + '\n\n' + para
        else:
            current = current + '\n\n' + para if current else para

    if current.strip() and len(current.strip()) >= min_chars:
        chunks.append(current.strip())

    return chunks


def detect_tags(text):
    """Detect astrological ontology references."""
    lower = text.lower()
    tags = {"planets": [], "signs": [], "aspects": [], "hebrew": [], "sephiroth": []}

    for name, patterns in PLANETS.items():
        if any(re.search(p, lower) for p in patterns):
            tags["planets"].append(name)
    for name, patterns in SIGNS.items():
        if any(re.search(p, lower) for p in patterns):
            tags["signs"].append(name)
    for name, patterns in ASPECTS.items():
        if any(re.search(p, lower) for p in patterns):
            tags["aspects"].append(name)
    for name, pattern in HEBREW.items():
        if re.search(pattern, lower):
            tags["hebrew"].append(name)
    for name, pattern in SEPHIROTH.items():
        if re.search(pattern, lower):
            tags["sephiroth"].append(name)

    return tags


def ingest_book(session, book_info, chunks):
    """Ingest chunks into Neo4j."""
    title = book_info["title"]
    author = book_info["author"]
    trust_tier = book_info["trust_tier"]
    layer = book_info["layer"]
    tradition = book_info["tradition"]

    # Ensure Author node
    session.run(
        "MERGE (a:Author {name: $name})",
        name=author,
    )

    # Ensure Layer node
    session.run(
        "MERGE (l:Layer {name: $name})",
        name=layer,
    )

    stats = {"chunks": 0, "placements": 0, "aspects": 0}

    for i, chunk_text_content in enumerate(chunks):
        chunk_id = hashlib.md5(f"{title}_{i}_{chunk_text_content[:100]}".encode()).hexdigest()
        tags = detect_tags(chunk_text_content)

        # Create Interpretation node
        session.run("""
            MERGE (c:Interpretation {chunk_id: $cid})
            SET c.text = $text,
                c.source_title = $title,
                c.trust_tier = $tier,
                c.tradition = $tradition
        """, cid=chunk_id, text=chunk_text_content, title=title, tier=trust_tier, tradition=tradition)

        # Link to Author
        session.run("""
            MATCH (c:Interpretation {chunk_id: $cid})
            MATCH (a:Author {name: $author})
            MERGE (c)-[:AUTHORED_BY]->(a)
        """, cid=chunk_id, author=author)

        # Link to Layer
        session.run("""
            MATCH (c:Interpretation {chunk_id: $cid})
            MATCH (l:Layer {name: $layer})
            MERGE (c)-[:IN_LAYER]->(l)
        """, cid=chunk_id, layer=layer)

        # INTERPRETS_PLACEMENT edges (planet + sign combos)
        for planet in tags["planets"]:
            session.run("""
                MATCH (c:Interpretation {chunk_id: $cid})
                MATCH (p:Planet {name: $planet})
                MERGE (c)-[:INTERPRETS_PLACEMENT]->(p)
            """, cid=chunk_id, planet=planet.capitalize())
            stats["placements"] += 1

            for sign in tags["signs"]:
                session.run("""
                    MATCH (c:Interpretation {chunk_id: $cid})
                    MATCH (s:Sign {name: $sign})
                    MERGE (c)-[:INTERPRETS_PLACEMENT]->(s)
                """, cid=chunk_id, sign=sign.capitalize())

        # INTERPRETS_ASPECT edges
        for aspect in tags["aspects"]:
            session.run("""
                MATCH (c:Interpretation {chunk_id: $cid})
                MATCH (a:Aspect {name: $aspect})
                MERGE (c)-[:INTERPRETS_ASPECT]->(a)
            """, cid=chunk_id, aspect=aspect.capitalize())
            stats["aspects"] += 1

        # DESCRIBES edges for topics
        topics = tags["planets"] + tags["signs"] + tags["hebrew"] + tags["sephiroth"]
        for topic in topics:
            session.run("""
                MATCH (c:Interpretation {chunk_id: $cid})
                MERGE (c)-[:DESCRIBES {topic: $topic}]->()
            """, cid=chunk_id, topic=topic)

        stats["chunks"] += 1
        if (i + 1) % 50 == 0:
            print(f"  ... {i + 1}/{len(chunks)} chunks")

    return stats


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    for book in BOOKS:
        print(f"\n{'='*60}")
        print(f"Ingesting: {book['title']}")
        print(f"  Source: {book['epub']}")
        print(f"  Trust tier: {book['trust_tier']}, Layer: {book['layer']}")
        print(f"{'='*60}")

        # Extract
        text = extract_epub_text(book["epub"])
        print(f"  Extracted {len(text)} chars")

        # Chunk
        chunks = chunk_text(text)
        print(f"  Split into {len(chunks)} chunks")

        # Ingest
        with driver.session() as session:
            stats = ingest_book(session, book, chunks)
            print(f"\n  Results:")
            print(f"    Chunks: {stats['chunks']}")
            print(f"    INTERPRETS_PLACEMENT edges: {stats['placements']}")
            print(f"    INTERPRETS_ASPECT edges: {stats['aspects']}")

    # Final stats
    with driver.session() as session:
        r = session.run("MATCH (n) RETURN count(n) AS nodes")
        nodes = r.single()["nodes"]
        r = session.run("MATCH ()-[r]->() RETURN count(r) AS rels")
        rels = r.single()["rels"]
        r = session.run("MATCH (c:Interpretation) RETURN count(c) AS interps")
        interps = r.single()["interps"]
        print(f"\n{'='*60}")
        print(f"FINAL TOTALS: {nodes} nodes, {rels} relationships, {interps} interpretations")
        print(f"{'='*60}")

    driver.close()


if __name__ == "__main__":
    main()
