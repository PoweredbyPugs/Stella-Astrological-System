#!/usr/bin/env python3
"""
Ingest missing texts into ChromaDB and sync ALL ChromaDB chunks to Neo4j.

Two operations:
1. Ingest Ebertin COSI + KWML from ~/clawd/reference/ into ChromaDB
2. Sync all ChromaDB chunks that aren't in Neo4j yet
"""

import os
import re
import json
import hashlib
from pathlib import Path

import chromadb
from openai import OpenAI
from neo4j import GraphDatabase

# Config
CHROMA_DIR = Path("/home/atlas/clawd/astro-knowledge/chromadb_store")
COLLECTION_NAME = "astro_knowledge"
EMBEDDING_MODEL = "text-embedding-3-large"
MAX_CHUNK_CHARS = 3200
MIN_CHUNK_CHARS = 100
OVERLAP_CHARS = 200

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "selene_gnosis")

# New texts to ingest
NEW_TEXTS = [
    {
        "path": Path("/home/atlas/clawd/reference/ebertin/ebertin-cosi-full.txt"),
        "author": "Reinhold Ebertin",
        "title": "The Combination of Stellar Influences",
        "trust_tier": 1,
        "layer": "technical",
        "tradition": "cosmobiology",
    },
    {
        "path": Path("/home/atlas/clawd/reference/kwml/kwml-full.txt"),
        "author": "Robert Moore and Douglas Gillette",
        "title": "King Warrior Magician Lover",
        "trust_tier": 2,
        "layer": "archetypal",
        "tradition": "jungian",
    },
]

# Ontology entities for tagging
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
    "synastry": [r"\bsynastry\b", r"\bcomposite\b"],
    "houses": [r"\bhouse\b", r"\bhous"],
    "midpoints": [r"\bmidpoint\b", r"\b90.*dial\b", r"\bcosmobiolog"],
}


def tag_chunk(text):
    """Extract ontology tags from chunk text."""
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
    """Split text into overlapping chunks at paragraph boundaries."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        if len(current) + len(para) + 2 > max_chars and len(current) >= MIN_CHUNK_CHARS:
            chunks.append(current.strip())
            # Keep overlap
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:] + "\n\n" + para
            else:
                current = para
        else:
            current = current + "\n\n" + para if current else para
    
    if current.strip() and len(current.strip()) >= MIN_CHUNK_CHARS:
        chunks.append(current.strip())
    
    return chunks


def ingest_new_texts():
    """Ingest Ebertin and KWML into ChromaDB."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col = client.get_collection(COLLECTION_NAME)
    openai = OpenAI()
    
    total_new = 0
    
    for text_info in NEW_TEXTS:
        path = text_info["path"]
        if not path.exists():
            print(f"  SKIP: {path} not found")
            continue
        
        title = text_info["title"]
        author = text_info["author"]
        
        # Check if already ingested
        existing = col.get(where={"source_title": title}, limit=1)
        if existing and existing["ids"]:
            print(f"  SKIP: '{title}' already in ChromaDB ({len(existing['ids'])} chunks found)")
            continue
        
        print(f"\nIngesting: {title} by {author}")
        print(f"  Source: {path}")
        
        raw_text = path.read_text(encoding="utf-8", errors="ignore")
        print(f"  Raw text: {len(raw_text):,} chars, {len(raw_text.splitlines()):,} lines")
        
        chunks = chunk_text(raw_text)
        print(f"  Chunks: {len(chunks)}")
        
        # Embed and store
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            # Get embeddings
            response = openai.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch
            )
            
            ids = []
            embeddings = []
            metadatas = []
            documents = []
            
            for j, (chunk, emb_data) in enumerate(zip(batch, response.data)):
                idx = i + j
                chunk_id = hashlib.md5(f"{title}:{idx}:{chunk[:50]}".encode()).hexdigest()
                
                tags = tag_chunk(chunk)
                
                meta = {
                    "source_title": title,
                    "author": author,
                    "trust_tier": text_info["trust_tier"],
                    "layer": text_info["layer"],
                    "tradition": text_info["tradition"],
                    "chunk_index": idx,
                    "chunk_id": chunk_id,
                }
                
                # Add tags as comma-separated strings (ChromaDB metadata)
                for tag_type, tag_list in tags.items():
                    if tag_list:
                        meta[tag_type] = ",".join(tag_list)
                
                ids.append(chunk_id)
                embeddings.append(emb_data.embedding)
                metadatas.append(meta)
                documents.append(chunk)
            
            col.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
            print(f"  Embedded batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1} ({len(batch)} chunks)")
        
        total_new += len(chunks)
        print(f"  ✓ {len(chunks)} chunks ingested for '{title}'")
    
    print(f"\nTotal new chunks: {total_new}")
    print(f"ChromaDB total: {col.count()}")
    return total_new


def sync_to_neo4j():
    """Sync all ChromaDB chunks to Neo4j that aren't there yet."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col = client.get_collection(COLLECTION_NAME)
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    
    # Get all ChromaDB chunks
    all_data = col.get(include=["metadatas", "documents", "embeddings"], limit=15000)
    total = len(all_data["ids"])
    print(f"\nChromaDB has {total} chunks total")
    
    # Get existing Neo4j interpretation chunk_ids
    with driver.session() as s:
        existing = set()
        for r in s.run("MATCH (i:Interpretation) RETURN i.chunk_id AS cid"):
            existing.add(r["cid"])
        print(f"Neo4j has {len(existing)} Interpretation nodes")
    
    # Find missing
    missing = []
    for i in range(total):
        cid = all_data["metadatas"][i].get("chunk_id", all_data["ids"][i])
        if cid not in existing:
            missing.append(i)
    
    print(f"Missing from Neo4j: {len(missing)} chunks")
    
    if not missing:
        print("Nothing to sync!")
        driver.close()
        return
    
    # Planet/Sign/House/Aspect name mappings for DESCRIBES edges
    PLANET_NAMES = {"sun": "Sun", "moon": "Moon", "mercury": "Mercury", "venus": "Venus",
                    "mars": "Mars", "jupiter": "Jupiter", "saturn": "Saturn",
                    "uranus": "Uranus", "neptune": "Neptune", "pluto": "Pluto"}
    SIGN_NAMES = {"aries": "Aries", "taurus": "Taurus", "gemini": "Gemini", "cancer": "Cancer",
                  "leo": "Leo", "virgo": "Virgo", "libra": "Libra", "scorpio": "Scorpio",
                  "sagittarius": "Sagittarius", "capricorn": "Capricorn", "aquarius": "Aquarius",
                  "pisces": "Pisces"}
    
    with driver.session() as s:
        batch_count = 0
        for idx in missing:
            meta = all_data["metadatas"][idx]
            doc = all_data["documents"][idx]
            cid = meta.get("chunk_id", all_data["ids"][idx])
            
            # Create Interpretation node
            s.run("""
                MERGE (i:Interpretation {chunk_id: $cid})
                SET i.source_title = $title,
                    i.text = $text,
                    i.trust_tier = $tier,
                    i.layer = $layer,
                    i.tradition = $tradition
            """, cid=cid, title=meta.get("source_title", ""),
                 text=doc, tier=meta.get("trust_tier", 4),
                 layer=meta.get("layer", "reference"),
                 tradition=meta.get("tradition", "unknown"))
            
            # AUTHORED_BY edge
            author = meta.get("author", "unknown")
            s.run("""
                MATCH (i:Interpretation {chunk_id: $cid})
                MERGE (a:Author {name: $author})
                MERGE (i)-[:AUTHORED_BY]->(a)
            """, cid=cid, author=author)
            
            # IN_LAYER edge
            layer = meta.get("layer", "reference")
            s.run("""
                MATCH (i:Interpretation {chunk_id: $cid})
                MERGE (l:Layer {name: $layer})
                MERGE (i)-[:IN_LAYER]->(l)
            """, cid=cid, layer=layer)
            
            # DESCRIBES edges to planets
            planets_str = meta.get("planets", "")
            if planets_str:
                for p_key in planets_str.split(","):
                    p_name = PLANET_NAMES.get(p_key.strip())
                    if p_name:
                        s.run("""
                            MATCH (i:Interpretation {chunk_id: $cid}), (p:Planet {name: $name})
                            MERGE (i)-[:DESCRIBES]->(p)
                        """, cid=cid, name=p_name)
            
            # DESCRIBES edges to signs
            signs_str = meta.get("signs", "")
            if signs_str:
                for s_key in signs_str.split(","):
                    s_name = SIGN_NAMES.get(s_key.strip())
                    if s_name:
                        s.run("""
                            MATCH (i:Interpretation {chunk_id: $cid}), (sign:Sign {name: $name})
                            MERGE (i)-[:DESCRIBES]->(sign)
                        """, cid=cid, name=s_name)
            
            # DESCRIBES edges to aspects
            aspects_str = meta.get("aspects", "")
            if aspects_str:
                for a_key in aspects_str.split(","):
                    a_name = a_key.strip().title()
                    s.run("""
                        MATCH (i:Interpretation {chunk_id: $cid}), (a:Aspect {name: $name})
                        MERGE (i)-[:DESCRIBES]->(a)
                    """, cid=cid, name=a_name)
            
            # DESCRIBES edges to houses (from text)
            houses_str = meta.get("houses", "")  # May not be tagged
            
            batch_count += 1
            if batch_count % 100 == 0:
                print(f"  Synced {batch_count}/{len(missing)} chunks...")
    
    print(f"  ✓ Synced {batch_count} chunks to Neo4j")
    
    # Run enrichment on new chunks
    print("\nEnriching new chunks with INTERPRETS_PLACEMENT edges...")
    with driver.session() as s:
        # Only for chunks that don't have INTERPRETS_PLACEMENT yet
        result = s.run("""
            MATCH (i:Interpretation)-[:DESCRIBES]->(p:Planet)
            MATCH (i)-[:DESCRIBES]->(sign:Sign)
            WHERE NOT (i)-[:INTERPRETS_PLACEMENT]->()
            RETURN i.chunk_id AS cid, p.name AS planet, sign.name AS sign
        """)
        
        enrich_count = 0
        for r in result:
            s.run("""
                MATCH (i:Interpretation {chunk_id: $cid})
                MATCH (p:Planet {name: $planet})
                MERGE (i)-[:INTERPRETS_PLACEMENT {planet: $planet, sign: $sign}]->(p)
            """, cid=r["cid"], planet=r["planet"], sign=r["sign"])
            enrich_count += 1
        
        print(f"  ✓ Created {enrich_count} INTERPRETS_PLACEMENT edges")
        
        # INTERPRETS_HOUSE
        result = s.run("""
            MATCH (i:Interpretation)-[:DESCRIBES]->(p:Planet)
            MATCH (i)-[:DESCRIBES]->(h:House)
            WHERE NOT (i)-[:INTERPRETS_HOUSE]->()
            RETURN i.chunk_id AS cid, p.name AS planet, h.name AS house
        """)
        
        house_count = 0
        for r in result:
            s.run("""
                MATCH (i:Interpretation {chunk_id: $cid})
                MATCH (p:Planet {name: $planet})
                MERGE (i)-[:INTERPRETS_HOUSE {planet: $planet, house: $house}]->(p)
            """, cid=r["cid"], planet=r["planet"], house=r["house"])
            house_count += 1
        
        print(f"  ✓ Created {house_count} INTERPRETS_HOUSE edges")
        
        # INTERPRETS_ASPECT
        result = s.run("""
            MATCH (i:Interpretation)-[:DESCRIBES]->(p1:Planet)
            MATCH (i)-[:DESCRIBES]->(p2:Planet)
            WHERE p1.name < p2.name
            MATCH (i)-[:DESCRIBES]->(a:Aspect)
            WHERE NOT (i)-[:INTERPRETS_ASPECT]->()
            RETURN i.chunk_id AS cid, p1.name AS p1, p2.name AS p2, a.name AS aspect
        """)
        
        aspect_count = 0
        for r in result:
            s.run("""
                MATCH (i:Interpretation {chunk_id: $cid})
                MATCH (p1:Planet {name: $p1})
                MERGE (i)-[:INTERPRETS_ASPECT {planet1: $p1, planet2: $p2, aspect: $aspect}]->(p1)
            """, cid=r["cid"], p1=r["p1"], p2=r["p2"], aspect=r["aspect"])
            aspect_count += 1
        
        print(f"  ✓ Created {aspect_count} INTERPRETS_ASPECT edges")
    
    # Final stats
    with driver.session() as s:
        n = s.run("MATCH (n) RETURN count(n) as c").single()["c"]
        r = s.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
        interps = s.run("MATCH (i:Interpretation) RETURN count(i) as c").single()["c"]
        titles = s.run("MATCH (i:Interpretation) RETURN DISTINCT i.source_title AS t ORDER BY t")
        title_list = [t["t"] for t in titles]
        
        print(f"\nFINAL: {n} nodes, {r} relationships, {interps} interpretations")
        print(f"Texts: {len(title_list)}")
        for t in title_list:
            c = s.run("MATCH (i:Interpretation {source_title: $t}) RETURN count(i) as c", t=t).single()["c"]
            print(f"  {c:>4} | {t}")
    
    driver.close()


if __name__ == "__main__":
    print("=" * 60)
    print("STEP 1: Ingest new texts to ChromaDB")
    print("=" * 60)
    ingest_new_texts()
    
    print("\n" + "=" * 60)
    print("STEP 2: Sync ChromaDB → Neo4j")
    print("=" * 60)
    sync_to_neo4j()
