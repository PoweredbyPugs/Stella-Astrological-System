#!/usr/bin/env python3
"""
Ingest Crowley's Book of Thoth into Stella's Neo4j knowledge graph and ChromaDB.

Run with: /home/atlas/clawd/stella/.ingest-venv/bin/python3.13 ingest_thoth.py
"""

import re
import hashlib
from pathlib import Path

from neo4j import GraphDatabase

# ── Config ──
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "selene_gnosis")

MAX_CHUNK_CHARS = 3200
MIN_CHUNK_CHARS = 100
OVERLAP_CHARS = 200

TEXT_PATH = Path("/home/atlas/clawd/stella/ingest-tmp-thoth.txt")

BOOK = {
    "title": "The Book of Thoth",
    "author": "Aleister Crowley",
    "trust_tier": 2,
    "layer": "reference",
    "tradition": "hermetic",
}

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
    "aries": [r"\baries\b", r"\bram\b"], "taurus": [r"\btaurus\b", r"\bbull\b"],
    "gemini": [r"\bgemini\b", r"\btwins\b"], "cancer": [r"\bcancer\b", r"\bcrab\b"],
    "leo": [r"\bleo\b", r"\blion\b"], "virgo": [r"\bvirgo\b", r"\bvirgin\b"],
    "libra": [r"\blibra\b", r"\bscales\b"], "scorpio": [r"\bscorpio\b", r"\bscorpion\b"],
    "sagittarius": [r"\bsagittarius\b", r"\barcher\b"], "capricorn": [r"\bcapricorn\b", r"\bgoat\b"],
    "aquarius": [r"\baquarius\b", r"\bwater.bearer\b"], "pisces": [r"\bpisces\b", r"\bfishes\b"],
}

ASPECTS = {
    "conjunction": [r"\bconjunction\b", r"\bconjunct\b"],
    "opposition": [r"\bopposition\b", r"\boppose\b"],
    "trine": [r"\btrine\b"], "square": [r"\bsquare\b"],
    "sextile": [r"\bsextile\b"],
}

TECHNIQUES = {
    "essential_dignities": [r"\bdomicile\b", r"\bexaltation\b", r"\bdetriment\b", r"\bfall\b", r"\bperegrine\b", r"\bdignit"],
    "lots": [r"\blot of\b", r"\bfortune\b.*lot", r"\bspirit\b.*lot"],
    "transits": [r"\btransit\b", r"\bprogress"],
    "houses": [r"\bhouse\b", r"\bhous"],
    "midpoints": [r"\bmidpoint\b"],
    "magic_squares": [r"\bmagic square\b", r"\bkamea\b"],
    "kabbalah": [r"\bkabbal\b", r"\bqabal\b", r"\bsephir\b", r"\bsephirot\b", r"\btree of life\b"],
    "tarot": [r"\btarot\b", r"\btrump\b", r"\barcana\b", r"\batu\b"],
    "elements": [r"\belement\b.*\bfire\b", r"\belement\b.*\bwater\b", r"\belement\b.*\bearth\b", r"\belement\b.*\bair\b"],
}

PLANET_NAMES = {
    "sun": "Sun", "moon": "Moon", "mercury": "Mercury", "venus": "Venus",
    "mars": "Mars", "jupiter": "Jupiter", "saturn": "Saturn",
    "uranus": "Uranus", "neptune": "Neptune", "pluto": "Pluto",
}

SIGN_NAMES = {
    "aries": "Aries", "taurus": "Taurus", "gemini": "Gemini", "cancer": "Cancer",
    "leo": "Leo", "virgo": "Virgo", "libra": "Libra", "scorpio": "Scorpio",
    "sagittarius": "Sagittarius", "capricorn": "Capricorn", "aquarius": "Aquarius",
    "pisces": "Pisces",
}


def tag_chunk(text):
    text_lower = text.lower()
    tags = {"planets": [], "signs": [], "aspects": [], "techniques": []}
    for entity_id, patterns in PLANETS.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                tags["planets"].append(entity_id)
                break
    for entity_id, patterns in SIGNS.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                tags["signs"].append(entity_id)
                break
    for entity_id, patterns in ASPECTS.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                tags["aspects"].append(entity_id)
                break
    for entity_id, patterns in TECHNIQUES.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                tags["techniques"].append(entity_id)
                break
    return tags


def chunk_text(text, max_chars=MAX_CHUNK_CHARS, overlap=OVERLAP_CHARS):
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 > max_chars and len(current) >= MIN_CHUNK_CHARS:
            chunks.append(current.strip())
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:] + "\n\n" + para
            else:
                current = para
        else:
            current = current + "\n\n" + para if current else para
    if current.strip() and len(current.strip()) >= MIN_CHUNK_CHARS:
        chunks.append(current.strip())
    return chunks


def ingest_neo4j(driver, chunks, book_info):
    title = book_info["title"]
    author = book_info["author"]

    with driver.session() as s:
        existing = s.run(
            "MATCH (i:Interpretation {source_title: $t}) RETURN count(i) as c",
            t=title
        ).single()["c"]
        if existing > 0:
            print(f"  SKIP: '{title}' already has {existing} chunks in Neo4j")
            return 0

    with driver.session() as s:
        s.run("MERGE (a:Author {name: $author})", author=author)
        s.run("MERGE (l:Layer {name: $layer})", layer=book_info["layer"])

        for idx, chunk in enumerate(chunks):
            chunk_id = hashlib.md5(f"{title}:{idx}:{chunk[:50]}".encode()).hexdigest()
            tags = tag_chunk(chunk)
            all_tags = []
            for tag_list in tags.values():
                all_tags.extend(tag_list)
            tags_str = ",".join(all_tags) if all_tags else ""

            s.run("""
                MERGE (i:Interpretation {chunk_id: $cid})
                SET i.source_title = $title,
                    i.text = $text,
                    i.trust_tier = $tier,
                    i.layer = $layer,
                    i.tradition = $tradition,
                    i.tags = $tags,
                    i.chunk_index = $idx
            """, cid=chunk_id, title=title, text=chunk,
                tier=book_info["trust_tier"], layer=book_info["layer"],
                tradition=book_info["tradition"], tags=tags_str, idx=idx)

            s.run("""
                MATCH (i:Interpretation {chunk_id: $cid})
                MATCH (a:Author {name: $author})
                MERGE (i)-[:AUTHORED_BY]->(a)
            """, cid=chunk_id, author=author)

            s.run("""
                MATCH (i:Interpretation {chunk_id: $cid})
                MATCH (l:Layer {name: $layer})
                MERGE (i)-[:IN_LAYER]->(l)
            """, cid=chunk_id, layer=book_info["layer"])

            for p_key in tags["planets"]:
                p_name = PLANET_NAMES.get(p_key)
                if p_name:
                    s.run("""
                        MATCH (i:Interpretation {chunk_id: $cid}), (p:Planet {name: $name})
                        MERGE (i)-[:DESCRIBES]->(p)
                    """, cid=chunk_id, name=p_name)

            for s_key in tags["signs"]:
                s_name = SIGN_NAMES.get(s_key)
                if s_name:
                    s.run("""
                        MATCH (i:Interpretation {chunk_id: $cid}), (sign:Sign {name: $name})
                        MERGE (i)-[:DESCRIBES]->(sign)
                    """, cid=chunk_id, name=s_name)

            for a_key in tags["aspects"]:
                a_name = a_key.strip().title()
                s.run("""
                    MATCH (i:Interpretation {chunk_id: $cid}), (a:Aspect {name: $name})
                    MERGE (i)-[:DESCRIBES]->(a)
                """, cid=chunk_id, name=a_name)

            if (idx + 1) % 50 == 0:
                print(f"  Neo4j: {idx + 1}/{len(chunks)} chunks...")

    print(f"  ✓ {len(chunks)} chunks ingested into Neo4j")
    return len(chunks)


def enrich_edges(driver, title):
    with driver.session() as s:
        result = s.run("""
            MATCH (i:Interpretation {source_title: $title})-[:DESCRIBES]->(p:Planet)
            MATCH (i)-[:DESCRIBES]->(sign:Sign)
            WHERE NOT (i)-[:INTERPRETS_PLACEMENT]->()
            RETURN i.chunk_id AS cid, p.name AS planet, sign.name AS sign
        """, title=title)

        placement_count = 0
        for r in result:
            s.run("""
                MATCH (i:Interpretation {chunk_id: $cid})
                MATCH (p:Planet {name: $planet})
                MERGE (i)-[:INTERPRETS_PLACEMENT {planet: $planet, sign: $sign}]->(p)
            """, cid=r["cid"], planet=r["planet"], sign=r["sign"])
            placement_count += 1

        result = s.run("""
            MATCH (i:Interpretation {source_title: $title})-[:DESCRIBES]->(p1:Planet)
            MATCH (i)-[:DESCRIBES]->(p2:Planet)
            WHERE p1.name < p2.name
            MATCH (i)-[:DESCRIBES]->(a:Aspect)
            WHERE NOT (i)-[:INTERPRETS_ASPECT]->()
            RETURN i.chunk_id AS cid, p1.name AS p1, p2.name AS p2, a.name AS aspect
        """, title=title)

        aspect_count = 0
        for r in result:
            s.run("""
                MATCH (i:Interpretation {chunk_id: $cid})
                MATCH (p1:Planet {name: $p1})
                MERGE (i)-[:INTERPRETS_ASPECT {planet1: $p1, planet2: $p2, aspect: $aspect}]->(p1)
            """, cid=r["cid"], p1=r["p1"], p2=r["p2"], aspect=r["aspect"])
            aspect_count += 1

        print(f"  Enrichment: {placement_count} INTERPRETS_PLACEMENT, {aspect_count} INTERPRETS_ASPECT")


def ingest_chromadb(chunks, book_info):
    """Ingest into ChromaDB using the ingest venv (Python 3.13)."""
    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(
            path=str(Path.home() / "clawd/astro-knowledge/chromadb_store"),
            settings=Settings(anonymized_telemetry=False)
        )

        collection = client.get_or_create_collection(
            name="astro_knowledge",
            metadata={"hnsw:space": "cosine"}
        )

        # Check if already ingested
        existing = collection.get(where={"source": book_info["title"]})
        if existing and len(existing["ids"]) > 0:
            print(f"  SKIP ChromaDB: '{book_info['title']}' already has {len(existing['ids'])} chunks")
            return 0

        ids = []
        documents = []
        metadatas = []

        for idx, chunk in enumerate(chunks):
            chunk_id = hashlib.md5(f"{book_info['title']}:{idx}:{chunk[:50]}".encode()).hexdigest()
            ids.append(chunk_id)
            documents.append(chunk)
            tags = tag_chunk(chunk)
            metadatas.append({
                "source": book_info["title"],
                "author": book_info["author"],
                "trust_tier": book_info["trust_tier"],
                "layer": book_info["layer"],
                "tradition": book_info["tradition"],
                "chunk_index": idx,
                "planets": ",".join(tags["planets"]),
                "signs": ",".join(tags["signs"]),
            })

        # Batch insert (ChromaDB handles embedding internally)
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            collection.add(
                ids=ids[i:end],
                documents=documents[i:end],
                metadatas=metadatas[i:end],
            )
            if end % 100 == 0:
                print(f"  ChromaDB: {end}/{len(ids)} chunks...")

        print(f"  ✓ {len(ids)} chunks ingested into ChromaDB")
        return len(ids)

    except Exception as e:
        print(f"  ⚠ ChromaDB ingestion failed: {e}")
        return 0


def main():
    print(f"Loading text from {TEXT_PATH}")
    raw_text = TEXT_PATH.read_text()
    print(f"  Raw text: {len(raw_text):,} chars")

    chunks = chunk_text(raw_text)
    print(f"  Chunks: {len(chunks)}")

    # Neo4j
    print(f"\n{'='*60}")
    print(f"Ingesting: {BOOK['title']} by {BOOK['author']}")
    print(f"  Layer: {BOOK['layer']} | Tier: {BOOK['trust_tier']} | Tradition: {BOOK['tradition']}")
    print(f"{'='*60}")

    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    count = ingest_neo4j(driver, chunks, BOOK)

    if count > 0:
        print("\nEnriching edges...")
        enrich_edges(driver, BOOK["title"])

    # ChromaDB
    print(f"\n{'='*60}")
    print("ChromaDB ingestion")
    print(f"{'='*60}")
    ingest_chromadb(chunks, BOOK)

    # Final stats
    print(f"\n{'='*60}")
    print("FINAL STATS")
    print(f"{'='*60}")
    with driver.session() as s:
        n = s.run("MATCH (n) RETURN count(n) as c").single()["c"]
        r = s.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
        i = s.run("MATCH (i:Interpretation) RETURN count(i) as c").single()["c"]
        print(f"Nodes: {n:,} | Relationships: {r:,} | Interpretations: {i:,}")

        titles = s.run("""
            MATCH (i:Interpretation)
            RETURN DISTINCT i.source_title AS t, count(i) AS c
            ORDER BY c DESC
        """)
        print("\nAll texts:")
        for t in titles:
            print(f"  {t['c']:>4} | {t['t']}")

    driver.close()


if __name__ == "__main__":
    main()
