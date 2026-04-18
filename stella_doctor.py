#!/usr/bin/env python3
"""Lightweight Stella environment doctor."""

from __future__ import annotations

import subprocess
import sys
import urllib.request

from stella_config import (
    NEO4J_URI,
    NEO4J_USER,
    STELLA_DIR,
    SWEPH_API_BASE,
    has_openai_key,
    neo4j_password_candidates,
    open_neo4j_driver,
)


def check_neo4j() -> tuple[bool, str]:
    try:
        driver, password = open_neo4j_driver()
        driver.close()
        source = "configured" if password == neo4j_password_candidates()[0] else "legacy fallback"
        return True, f"Neo4j reachable at {NEO4J_URI} ({source} password)"
    except Exception as exc:
        return False, f"Neo4j auth/connect failed: {exc}"


def check_helios() -> tuple[bool, str]:
    url = f"{SWEPH_API_BASE}/api-info"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return True, f"Helios reachable ({resp.status}) at {SWEPH_API_BASE}"
    except Exception as exc:
        return False, f"Helios unreachable at {SWEPH_API_BASE}: {exc}"


def print_local_mcp_config() -> None:
    print("\nClaude / MCP config:")
    print("{")
    print('  "mcpServers": {')
    print('    "stella": {')
    print(f'      "command": "{STELLA_DIR / ".venv/bin/python"}",')
    print(f'      "args": ["{STELLA_DIR / "stella_server.py"}"],')
    print('      "env": {')
    print(f'        "SWEPH_API_BASE": "{SWEPH_API_BASE}"')
    print('      }')
    print('    }')
    print('  }')
    print("}")


def main() -> int:
    print("🌙 Stella Doctor")
    print("===============")
    print(f"Repo:   {STELLA_DIR}")
    print(f"Neo4j:  {NEO4J_URI} ({NEO4J_USER})")
    print(f"Helios: {SWEPH_API_BASE}")
    print(f"OpenAI key present: {'yes' if has_openai_key() else 'no (optional for basic use)'}")
    print("Knowledge import: optional legacy Chroma path (disabled by default)")
    print("")

    checks = [
        ("Neo4j", check_neo4j),
        ("Helios", check_helios),
    ]

    all_ok = True
    for label, fn in checks:
        ok, message = fn()
        icon = "✓" if ok else "✗"
        print(f"{icon} {label}: {message}")
        all_ok = all_ok and ok

    print_local_mcp_config()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
