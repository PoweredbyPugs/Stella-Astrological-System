# Stella Setup Guide

## Quick Start (automated)

```bash
cd ~/clawd
git lfs install
git clone https://github.com/PoweredbyPugs/Stella-mcp.git stella
cd stella
bash setup.sh
```

The setup script handles everything: venv, deps, Neo4j (optional), and prints the mcporter/Claude config.

## Manual Setup

### 1. Clone

```bash
git clone https://github.com/PoweredbyPugs/Stella-mcp.git stella
```

### 2. Python Virtual Environment

```bash
cd stella
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `OPENAI_API_KEY` | No | — | Optional for some features |
| `SWEPH_API_BASE` | No | `http://baratie:3000` | Helios ephemeris API |
| `NEO4J_URI` | No | `bolt://localhost:7687` | Neo4j Bolt endpoint |
| `NEO4J_USER` | No | `neo4j` | Neo4j username |
| `NEO4J_PASS` | No | `stella_gnosis` | Neo4j password |

If you're on the tailnet, `baratie:3000` resolves automatically.
Otherwise use the IP: `http://100.102.99.117:3000`

### 4. Configure mcporter

```bash
npx mcporter config edit
```

Add to `mcpServers`:

```json
"stella": {
  "type": "stdio",
  "command": "/path/to/stella/.venv/bin/python",
  "args": ["/path/to/stella/stella_server.py"],
  "env": {
    "SWEPH_API_BASE": "http://100.102.99.117:3000"
  }
}
```

### 5.5. Run the Doctor

```bash
./.venv/bin/python stella_doctor.py
```

This checks Neo4j auth, Helios reachability, and prints a ready-to-paste local Claude MCP config.

### 5. Verify

```bash
npx mcporter call stella.get_current_moon
npx mcporter call stella.list_charts
npx mcporter call stella.discover name=chris
```

### 6. Generate a Chart

```bash
npx mcporter call stella.generate_chart \
  name=person \
  date="1994-12-18" \
  time="20:00" \
  lat=37.3541 \
  lon=-121.9552 \
  location="Santa Clara, CA"
```

### 7. Neo4j (Optional)

The structural knowledge graph. Not required — Stella works fine without it.

```bash
docker compose up -d                # Start Neo4j
./.venv/bin/python build_graph.py   # Build the structural graph
```

### 8. Optional legacy Chroma knowledge import

Only if you specifically want the old Chroma-based interpretation import:

```bash
pip install chromadb
git lfs install
git lfs pull
./.venv/bin/python build_graph.py --with-knowledge
```

## Troubleshooting

- **Neo4j auth failed** → Ensure password matches `stella_gnosis` or set `NEO4J_PASS`
- **Connection refused on baratie:3000** → Helios container may be stopped, or use tailnet IP
- **Neo4j errors** → Non-fatal. Stella falls back gracefully without it.
- **Import errors** → Ensure mcporter command points to `.venv/bin/python`

## File Structure

```
stella/
├── stella_server.py        # Main MCP server
├── ki.py                   # 9 Star Ki calculation
├── ki_reading.py           # Ki narrative generator
├── zr_report.py            # ZR report generator
├── setup.sh                # Automated setup
├── docker-compose.yml      # Neo4j (optional)
├── build_graph.py          # Neo4j graph builder
├── chromadb_store/         # Optional legacy Chroma knowledge store
├── charts/                 # Your chart JSONs (local, gitignored)
│   ├── memory/             # Per-chart learning memory (local, gitignored)
│   └── readings/           # Generated readings (local, gitignored)
├── elections/              # 2026 electional data
├── docs/                   # Reference materials
├── CHART_WORKFLOW.md       # Reading generation guide
└── README.md               # Full documentation
```

Charts, readings, and memory files are gitignored — each Stella instance builds its own.
