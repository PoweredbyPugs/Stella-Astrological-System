#!/usr/bin/env python3
"""Shared Stella configuration.

Keeps setup, runtime, and graph-build paths/auth in one place so the repo can
be moved between machines without hidden drift.
"""

from __future__ import annotations

import os
from pathlib import Path

from neo4j import GraphDatabase

from neo4j import GraphDatabase


STELLA_DIR = Path(__file__).resolve().parent
ENV_FILE = STELLA_DIR / ".env"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_file(ENV_FILE)


def _resolve_chroma_dir() -> Path:
    env_value = os.environ.get("CHROMA_DIR")
    if env_value:
        return Path(env_value).expanduser()

    candidates = [
        STELLA_DIR / "chromadb_store",
        STELLA_DIR.parent / "astro-knowledge" / "chromadb_store",  # legacy layout
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


CHROMA_DIR = _resolve_chroma_dir()
SWEPH_API_BASE = os.environ.get("SWEPH_API_BASE", "http://baratie:3000")
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "stella_gnosis")


def neo4j_password_candidates() -> list[str]:
    candidates: list[str] = []
    for password in [NEO4J_PASS, "selene_gnosis"]:
        if password and password not in candidates:
            candidates.append(password)
    return candidates


def open_neo4j_driver():
    last_exc = None
    for password in neo4j_password_candidates():
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, password))
        try:
            driver.verify_connectivity()
            return driver, password
        except Exception as exc:
            last_exc = exc
            try:
                driver.close()
            except Exception:
                pass
    if last_exc:
        raise last_exc
    raise RuntimeError("Unable to open Neo4j driver")


def neo4j_password_candidates() -> list[str]:
    candidates: list[str] = []
    for password in [NEO4J_PASS, "selene_gnosis"]:
        if password and password not in candidates:
            candidates.append(password)
    return candidates


def open_neo4j_driver():
    last_exc = None
    for password in neo4j_password_candidates():
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, password))
        try:
            driver.verify_connectivity()
            return driver, password
        except Exception as exc:
            last_exc = exc
            try:
                driver.close()
            except Exception:
                pass
    if last_exc:
        raise last_exc
    raise RuntimeError("Unable to open Neo4j driver")


def chroma_has_store(path: Path | None = None) -> bool:
    target = path or CHROMA_DIR
    return target.exists() and (target / "chroma.sqlite3").exists()


def has_openai_key() -> bool:
    if os.environ.get("OPENAI_API_KEY"):
        return True

    config_path = Path.home() / ".clawdbot" / "clawdbot.json"
    if not config_path.exists():
        return False

    try:
        import json

        config = json.loads(config_path.read_text())
        skills = config.get("skills", {}).get("entries", {})
        for skill_name in ["openai-image-gen", "openai-whisper-api"]:
            if skills.get(skill_name, {}).get("apiKey"):
                return True
    except Exception:
        return False

    return False
