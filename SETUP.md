# Stella Setup Guide

Quick setup for running Stella on a new OpenClaw instance.

## Prerequisites

- Python 3.11+
- Git access to `PoweredbyPugs/Stella` (private repo)
- Network access to Helios (sweph API) at `baratie:3000` (or wherever it's hosted)
- An OpenAI API key (for knowledge graph embeddings/search)
- mcporter installed (`npx mcporter`)

## 1. Clone the Repo

```bash
cd ~/clawd
git clone https://github.com/PoweredbyPugs/Stella.git stella
```

## 2. Set Up the Knowledge Graph Store

The ChromaDB store (~300MB) contains 6,500+ embedded chunks from 25 astrological texts. It's NOT in the git repo — you need to copy it from atlas.

```bash
# From the machine with access to atlas:
mkdir -p ~/clawd/astro-knowledge
scp -r atlas:~/clawd/astro-knowledge/chromadb_store ~/clawd/astro-knowledge/
```

Or if on the same tailnet:
```bash
rsync -avz atlas:~/clawd/astro-knowledge/chromadb_store/ ~/clawd/astro-knowledge/chromadb_store/
```

## 3. Create the Python Virtual Environment

```bash
cd ~/clawd/astro-knowledge
python3 -m venv .venv
source .venv/bin/activate
pip install mcp chromadb openai httpx pydantic neo4j
```

## 4. Environment Variables

Stella needs these (set in your shell, `.env`, or mcporter config):

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `OPENAI_API_KEY` | **Yes** | — | For knowledge graph search (text-embedding-3-large) |
| `SWEPH_API_BASE` | No | `http://baratie:3000` | Helios ephemeris API URL |
| `NEO4J_URI` | No | `bolt://localhost:7687` | Only if using Neo4j graph (optional) |
| `NEO4J_USER` | No | `neo4j` | Neo4j auth |
| `NEO4J_PASS` | No | `stella_gnosis` | Neo4j auth |

If you're on the same tailnet as atlas, `baratie:3000` should resolve. Otherwise use the tailnet IP:
```
SWEPH_API_BASE=http://100.102.99.117:3000
```

## 5. Configure mcporter

```bash
npx mcporter config edit
```

Add this to the `mcpServers` block:

```json
"stella": {
  "type": "stdio",
  "command": "/path/to/clawd/astro-knowledge/.venv/bin/python",
  "args": ["/path/to/clawd/stella/stella_server.py"],
  "env": {
    "OPENAI_API_KEY": "sk-..."
  }
}
```

Replace paths with your actual install location.

## 6. Verify It Works

```bash
# List all tools
npx mcporter list stella

# Test ephemeris connection
npx mcporter call stella.get_current_moon

# Test knowledge graph
npx mcporter call stella.knowledge_search query="essential dignities"

# Test a chart (if charts are set up)
npx mcporter call stella.list_charts
```

## 7. Charts

Chart JSON files live in `stella/charts/`. To generate a new one:

```bash
npx mcporter call stella.generate_chart \
  name=lisa \
  date="1994-12-18" \
  time="20:00" \
  lat=37.3541 \
  lon=-121.9552 \
  location="Santa Clara, CA"
```

Charts are stored as JSON with full planetary positions, houses, aspects, and dignity scores.

## File Structure

```
~/clawd/
├── stella/                    # Git repo
│   ├── stella_server.py       # Main MCP server
│   ├── charts/                # Stored chart JSONs
│   │   ├── chris.json
│   │   ├── lisa.json
│   │   └── ...
│   ├── charts/readings/       # Generated readings
│   ├── elections/             # Electional astrology data
│   └── CHART_WORKFLOW.md      # Reading generation guide
├── astro-knowledge/
│   ├── .venv/                 # Python virtual environment
│   └── chromadb_store/        # Knowledge graph (~300MB)
```

## Troubleshooting

- **"No OPENAI_API_KEY found"** → Set it in mcporter env config or export it
- **Connection refused on baratie:3000** → Check if Helios Docker container is running on atlas, or use the tailnet IP
- **ChromaDB errors** → Make sure `~/clawd/astro-knowledge/chromadb_store/` exists and was copied correctly
- **Neo4j connection errors** → These are non-fatal; Neo4j is optional. Stella falls back gracefully.
- **Import errors** → Make sure you're using the venv: check that mcporter command points to `.venv/bin/python`
