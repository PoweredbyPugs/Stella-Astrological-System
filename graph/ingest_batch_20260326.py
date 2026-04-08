#!/usr/bin/env python3
"""
Batch ingest 8 English books into Neo4j + ChromaDB.
Run with: /home/atlas/clawd/stella/.ingest-venv/bin/python3.13 ingest_batch_20260326.py

2026-03-26: Navamsa/Nakshatra/Moon research texts
"""

import re
import hashlib
import zipfile
import html
import subprocess
import sys
from pathlib import Path
from neo4j import GraphDatabase
import chromadb

# ── Config ──
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "selene_gnosis")
CHROMA_PATH = "/home/atlas/clawd/astro-knowledge/chromadb_store"
CHROMA_COLLECTION = "astro_knowledge"

MAX_CHUNK_CHARS = 3200
MIN_CHUNK_CHARS = 100
OVERLAP_CHARS = 200

DOWNLOADS = Path.home() / "Downloads"

import glob as _glob

def _find(pattern):
    """Find file by glob pattern in Downloads."""
    matches = _glob.glob(str(DOWNLOADS / pattern))
    return Path(matches[0]) if matches else Path(f"NOT_FOUND_{pattern}")

BOOKS = [
    {
        "file": _find("The Nakshatras*lunar mansions*Harness*"),
        "title": "The Nakshatras: The Lunar Mansions of Vedic Astrology",
        "author": "Dennis Harness",
        "trust_tier": 1,
        "layer": "vedic",
        "tradition": "vedic",
        "format": "pdf",
    },
    {
        "file": _find("*nakshatras*stars beyond*Komilla Sutton*"),
        "title": "The Nakshatras: The Stars Beyond the Zodiac",
        "author": "Komilla Sutton",
        "trust_tier": 1,
        "layer": "vedic",
        "tradition": "vedic",
        "format": "epub",
    },
    {
        "file": _find("Light on life*Defouw*"),
        "title": "Light on Life: An Introduction to the Astrology of India",
        "author": "Hart de Fouw & Robert Svoboda",
        "trust_tier": 1,
        "layer": "vedic",
        "tradition": "vedic",
        "format": "pdf",
    },
    {
        "file": _find("*Lunar Nodes*Crisis*Komilla Sutton*"),
        "title": "The Lunar Nodes: Crisis and Redemption",
        "author": "Komilla Sutton",
        "trust_tier": 1,
        "layer": "vedic",
        "tradition": "vedic",
        "format": "pdf",
    },
    {
        "file": _find("27 Stars*Zodiac*Nakshatras*Jyotish*"),
        "title": "27 Stars of the Zodiac: The Nakshatras",
        "author": "The Astrology Network",
        "trust_tier": 2,
        "layer": "vedic",
        "tradition": "vedic",
        "format": "pdf",
    },
    {
        "file": _find("*book of the moon*Forrest*"),
        "title": "The Book of the Moon",
        "author": "Steven Forrest",
        "trust_tier": 2,
        "layer": "psychological",
        "tradition": "modern_western",
        "format": "pdf",
    },
    {
        "file": _find("*Beautifully Rational*DiCara*"),
        "title": "The Beautifully Rational Philosophy of Astrology",
        "author": "Vic DiCara",
        "trust_tier": 2,
        "layer": "vedic",
        "tradition": "vedic",
        "format": "epub",
    },
    {
        "file": _find("Healing the soul*Jones*"),
        "title": "Healing the Soul: Pluto, Uranus and the Lunar Nodes",
        "author": "Mark Jones",
        "trust_tier": 2,
        "layer": "psychological",
        "tradition": "modern_western",
        "format": "epub",
    },
    {
        "file": _find("*Book of Enoch*Dover*"),
        "title": "The Book of Enoch",
        "author": "R.H. Charles (translator)",
        "trust_tier": 1,
        "layer": "hermetic",
        "tradition": "judaic",
        "format": "epub",
    },
]

# ── Ontology tagging ──
PLANETS = {
    "Sun": [r"\bsun\b", r"\bsolar\b", r"\bsurya\b"],
    "Moon": [r"\bmoon\b", r"\blunar\b", r"\bchandra\b", r"\bsoma\b"],
    "Mercury": [r"\bmercury\b", r"\bbudha\b"],
    "Venus": [r"\bvenus\b", r"\bshukra\b"],
    "Mars": [r"\bmars\b", r"\bmangal\b", r"\bkuja\b"],
    "Jupiter": [r"\bjupiter\b", r"\bguru\b", r"\bbrihaspati\b"],
    "Saturn": [r"\bsaturn\b", r"\bshani\b"],
    "Rahu": [r"\brahu\b", r"\bnorth\s*node\b", r"\bdragon'?s?\s*head\b"],
    "Ketu": [r"\bketu\b", r"\bsouth\s*node\b", r"\bdragon'?s?\s*tail\b"],
}

SIGNS = {
    "Aries": [r"\baries\b", r"\bmesha\b"],
    "Taurus": [r"\btaurus\b", r"\bvrishabha\b"],
    "Gemini": [r"\bgemini\b", r"\bmithuna\b"],
    "Cancer": [r"\bcancer\b", r"\bkarkata?\b"],
    "Leo": [r"\bleo\b", r"\bsimha\b"],
    "Virgo": [r"\bvirgo\b", r"\bkanya\b"],
    "Libra": [r"\blibra\b", r"\btula\b"],
    "Scorpio": [r"\bscorpio\b", r"\bvrishchika?\b"],
    "Sagittarius": [r"\bsagittarius\b", r"\bdhanus?\b"],
    "Capricorn": [r"\bcapricorn\b", r"\bmakara\b"],
    "Aquarius": [r"\baquarius\b", r"\bkumbha\b"],
    "Pisces": [r"\bpisces\b", r"\bmeena\b"],
}

ASPECTS = {
    "Conjunction": [r"\bconjunction\b", r"\bconjunct\b"],
    "Opposition": [r"\bopposition\b"],
    "Trine": [r"\btrine\b"],
    "Square": [r"\bsquare\b"],
    "Sextile": [r"\bsextile\b"],
}

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira",
    "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha",
    "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati",
    "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
    "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

VEDIC_TERMS = {
    "navamsa": [r"\bnavamsa\b", r"\bnavamsha\b", r"\bd-?9\b"],
    "nakshatra": [r"\bnakshatra\b", r"\blunar\s*mansion\b"],
    "pada": [r"\bpada\b", r"\bpadas\b"],
    "dasha": [r"\bdasha\b", r"\bdasa\b", r"\bvimshottari\b"],
    "varga": [r"\bvarga\b", r"\bdivisional\s*chart\b"],
    "yoga": [r"\byoga\b", r"\byogas\b"],
    "karaka": [r"\bkaraka\b"],
    "bhava": [r"\bbhava\b"],
    "rashi": [r"\brashi\b"],
    "graha": [r"\bgraha\b"],
    "lagna": [r"\blagna\b", r"\bascendant\b"],
    "mahadasha": [r"\bmahadasha\b", r"\bmaha\s*dasha\b"],
    "antardasha": [r"\bantardasha\b", r"\bantar\s*dasha\b"],
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


def extract_pdf_text(pdf_path):
    """Extract text from PDF using pdftotext."""
    try:
        result = subprocess.run(
            ['pdftotext', str(pdf_path), '-'],
            capture_output=True, text=True, timeout=120
        )
        text = result.stdout
        if len(text.strip()) < 500:
            # Try layout mode
            result = subprocess.run(
                ['pdftotext', '-layout', str(pdf_path), '-'],
                capture_output=True, text=True, timeout=120
            )
            text = result.stdout
        return text
    except Exception as e:
        return f"EXTRACTION ERROR: {e}"


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
            words = current.split()
            overlap_text = ' '.join(words[-overlap // 6:]) if len(words) > overlap // 6 else ''
            current = overlap_text + '\n\n' + para
        else:
            current = current + '\n\n' + para if current else para

    if current.strip() and len(current.strip()) >= min_chars:
        chunks.append(current.strip())

    return chunks


def detect_tags(text):
    """Detect astrological ontology references including Vedic terms."""
    lower = text.lower()
    tags = {
        "planets": [], "signs": [], "aspects": [],
        "nakshatras": [], "vedic_terms": [],
    }

    for name, patterns in PLANETS.items():
        if any(re.search(p, lower) for p in patterns):
            tags["planets"].append(name)
    for name, patterns in SIGNS.items():
        if any(re.search(p, lower) for p in patterns):
            tags["signs"].append(name)
    for name, patterns in ASPECTS.items():
        if any(re.search(p, lower) for p in patterns):
            tags["aspects"].append(name)
    for nak in NAKSHATRAS:
        if re.search(r'\b' + re.escape(nak.lower()) + r'\b', lower):
            tags["nakshatras"].append(nak)
        # Also check without spaces (PurvaPhalguni etc.)
        no_space = nak.replace(' ', '').lower()
        if no_space != nak.lower() and re.search(r'\b' + re.escape(no_space) + r'\b', lower):
            tags["nakshatras"].append(nak)
    for term, patterns in VEDIC_TERMS.items():
        if any(re.search(p, lower) for p in patterns):
            tags["vedic_terms"].append(term)

    # Deduplicate
    tags["nakshatras"] = list(set(tags["nakshatras"]))
    return tags


def ingest_to_neo4j(session, book_info, chunks):
    """Ingest chunks into Neo4j."""
    title = book_info["title"]
    author = book_info["author"]
    trust_tier = book_info["trust_tier"]
    layer = book_info["layer"]
    tradition = book_info["tradition"]

    # Ensure Author node
    session.run("MERGE (a:Author {name: $name})", name=author)
    # Ensure Layer node
    session.run("MERGE (l:Layer {name: $name})", name=layer)

    stats = {"chunks": 0, "placements": 0, "aspects": 0, "nakshatras": 0}

    for i, chunk_text_content in enumerate(chunks):
        chunk_id = hashlib.md5(f"{title}_{i}_{chunk_text_content[:100]}".encode()).hexdigest()
        tags = detect_tags(chunk_text_content)

        # Create Interpretation node
        session.run("""
            MERGE (c:Interpretation {chunk_id: $cid})
            SET c.text = $text,
                c.source_title = $title,
                c.trust_tier = $tier,
                c.tradition = $tradition,
                c.layer = $layer,
                c.chunk_index = $idx
        """, cid=chunk_id, text=chunk_text_content, title=title,
             tier=trust_tier, tradition=tradition, layer=layer, idx=i)

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

        # INTERPRETS_PLACEMENT edges
        for planet in tags["planets"]:
            session.run("""
                MATCH (c:Interpretation {chunk_id: $cid})
                MATCH (p:Planet {name: $planet})
                MERGE (c)-[:INTERPRETS_PLACEMENT]->(p)
            """, cid=chunk_id, planet=planet)
            stats["placements"] += 1

        for sign in tags["signs"]:
            session.run("""
                MATCH (c:Interpretation {chunk_id: $cid})
                MATCH (s:Sign {name: $sign})
                MERGE (c)-[:INTERPRETS_PLACEMENT]->(s)
            """, cid=chunk_id, sign=sign)

        # INTERPRETS_ASPECT edges
        for aspect in tags["aspects"]:
            session.run("""
                MATCH (c:Interpretation {chunk_id: $cid})
                MATCH (a:Aspect {name: $aspect})
                MERGE (c)-[:INTERPRETS_ASPECT]->(a)
            """, cid=chunk_id, aspect=aspect)
            stats["aspects"] += 1

        stats["chunks"] += 1
        if (i + 1) % 100 == 0:
            print(f"  ... {i + 1}/{len(chunks)} chunks")

    return stats


def ingest_to_chromadb(collection, book_info, chunks):
    """Ingest chunks into ChromaDB."""
    title = book_info["title"]
    author = book_info["author"]
    trust_tier = book_info["trust_tier"]
    layer = book_info["layer"]
    tradition = book_info["tradition"]

    ids = []
    documents = []
    metadatas = []

    for i, chunk_text_content in enumerate(chunks):
        chunk_id = hashlib.md5(f"{title}_{i}_{chunk_text_content[:100]}".encode()).hexdigest()
        tags = detect_tags(chunk_text_content)

        ids.append(chunk_id)
        documents.append(chunk_text_content)
        metadatas.append({
            "source_title": title,
            "author": author,
            "trust_tier": trust_tier,
            "layer": layer,
            "tradition": tradition,
            "chunk_index": i,
            "planets": ",".join(tags["planets"]) if tags["planets"] else "",
            "signs": ",".join(tags["signs"]) if tags["signs"] else "",
            "nakshatras": ",".join(tags["nakshatras"]) if tags["nakshatras"] else "",
            "vedic_terms": ",".join(tags["vedic_terms"]) if tags["vedic_terms"] else "",
        })

    # Batch upsert (ChromaDB handles batching internally but let's be safe)
    BATCH_SIZE = 200
    for start in range(0, len(ids), BATCH_SIZE):
        end = min(start + BATCH_SIZE, len(ids))
        collection.upsert(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )

    return len(ids)


def main():
    print("Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    print("Connecting to ChromaDB...")
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )
    print(f"ChromaDB collection '{CHROMA_COLLECTION}': {collection.count()} existing documents")

    total_chunks = 0
    total_neo4j = 0
    total_chroma = 0

    for book in BOOKS:
        filepath = book["file"]
        if not filepath.exists():
            print(f"\n❌ MISSING: {book['title']} — {filepath}")
            continue

        print(f"\n{'='*70}")
        print(f"📚 {book['title']}")
        print(f"   Author: {book['author']} | Tier: {book['trust_tier']} | Layer: {book['layer']}")
        print(f"{'='*70}")

        # Extract
        if book["format"] == "epub":
            text = extract_epub_text(filepath)
        else:
            text = extract_pdf_text(filepath)

        if text.startswith("EXTRACTION ERROR"):
            print(f"  ❌ {text}")
            continue

        char_count = len(text.strip())
        print(f"  Extracted: {char_count:,} chars")

        if char_count < 500:
            print(f"  ❌ SKIPPING — insufficient text extracted")
            continue

        # Chunk
        chunks = chunk_text(text)
        print(f"  Chunked: {len(chunks)} chunks")
        total_chunks += len(chunks)

        # Neo4j
        print(f"  → Neo4j ingesting...")
        with driver.session() as session:
            stats = ingest_to_neo4j(session, book, chunks)
            print(f"    ✅ {stats['chunks']} chunks, {stats['placements']} placement edges, {stats['aspects']} aspect edges")
            total_neo4j += stats['chunks']

        # ChromaDB
        print(f"  → ChromaDB ingesting...")
        chroma_count = ingest_to_chromadb(collection, book, chunks)
        print(f"    ✅ {chroma_count} documents upserted")
        total_chroma += chroma_count

    # Final stats
    print(f"\n{'='*70}")
    print(f"INGESTION COMPLETE")
    print(f"{'='*70}")
    print(f"  Books processed: {len(BOOKS)}")
    print(f"  Total chunks: {total_chunks}")
    print(f"  Neo4j chunks: {total_neo4j}")
    print(f"  ChromaDB docs: {total_chroma}")

    with driver.session() as session:
        r = session.run("MATCH (n) RETURN count(n) AS nodes")
        nodes = r.single()["nodes"]
        r = session.run("MATCH ()-[r]->() RETURN count(r) AS rels")
        rels = r.single()["rels"]
        r = session.run("MATCH (c:Interpretation) RETURN count(c) AS interps")
        interps = r.single()["interps"]
        print(f"\n  Neo4j totals: {nodes:,} nodes, {rels:,} relationships, {interps:,} interpretations")

    print(f"  ChromaDB total: {collection.count():,} documents")

    driver.close()
    print("\nDone! ✨")


if __name__ == "__main__":
    main()
