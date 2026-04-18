#!/bin/bash
# Stella — Automated Setup Script
# Run from the stella repo root: bash setup.sh
set -e

STELLA_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$STELLA_DIR/.venv"

echo "🌙 Stella Setup"
echo "==============="
echo ""

# ── 1. Python venv ──
if [ -d "$VENV_DIR" ]; then
    echo "✓ Python venv already exists at $VENV_DIR"
else
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✓ Venv created"
fi

source "$VENV_DIR/bin/activate"
echo "✓ Venv activated ($(python --version))"

# ── 2. Dependencies ──
echo ""
echo "Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q -r "$STELLA_DIR/requirements.txt"
echo "✓ Dependencies installed"

# ── 3. Optional legacy knowledge note ──
echo ""
echo "Note: legacy Chroma knowledge import is optional and not required for Stella MCP setup."
echo "If you ever want the old Chroma migration path later, install git-lfs + chromadb then run:"
echo "  ./.venv/bin/python build_graph.py --with-knowledge"

# ── 4. OpenAI API Key ──
echo ""
if [ -n "$OPENAI_API_KEY" ]; then
    echo "✓ OPENAI_API_KEY is set"
else
    echo "⚠ OPENAI_API_KEY not found in environment."
    echo "  Optional: some Stella features use it, but basic setup/MCP does not require it."
    read -p "  Enter your OpenAI API key (or press Enter to skip): " API_KEY
    if [ -n "$API_KEY" ]; then
        export OPENAI_API_KEY="$API_KEY"
        echo "✓ Key set for this session"
        echo "  To persist, add to your shell profile:"
        echo "    export OPENAI_API_KEY=\"$API_KEY\""
    else
        echo "  Skipped — set OPENAI_API_KEY before running Stella"
    fi
fi

# ── 5. Helios (sweph API) check ──
echo ""
SWEPH_URL="${SWEPH_API_BASE:-http://baratie:3000}"
echo "Checking Helios at $SWEPH_URL..."
if curl -s --connect-timeout 3 "$SWEPH_URL/api-info" > /dev/null 2>&1; then
    echo "✓ Helios is reachable"
else
    echo "⚠ Helios not reachable at $SWEPH_URL"
    echo "  Stella will work but ephemeris tools will fail."
    echo "  Set SWEPH_API_BASE to override (e.g. http://100.102.99.117:3000)"
fi

# ── 6. Neo4j (optional) ──
echo ""
echo "Neo4j is optional (structural knowledge graph)."
if command -v docker &> /dev/null; then
    if docker ps 2>/dev/null | grep -q stella-neo4j; then
        echo "✓ Neo4j container already running"
    else
        read -p "Start Neo4j via Docker? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker compose -f "$STELLA_DIR/docker-compose.yml" up -d
            echo "Waiting for Neo4j to initialize..."
            sleep 10
            echo "Building knowledge graph..."
            python "$STELLA_DIR/build_graph.py"
            echo "✓ Neo4j running and graph built"
        else
            echo "  Skipped — Stella works fine without Neo4j"
        fi
    fi
else
    echo "  Docker not found — skipping Neo4j"
    echo "  Install Docker and run: docker compose up -d"
fi

# ── 7. mcporter config ──
echo ""
echo "─── mcporter Configuration ───"
echo ""
echo "Add this to your mcporter config (npx mcporter config edit):"
echo ""
echo "  \"stella\": {"
echo "    \"type\": \"stdio\"," 
echo "    \"command\": \"$VENV_DIR/bin/python\"," 
echo "    \"args\": [\"$STELLA_DIR/stella_server.py\"],"
echo "    \"env\": {"
echo "      \"SWEPH_API_BASE\": \"${SWEPH_API_BASE:-http://100.102.99.117:3000}\""
echo "    }"
echo "  }"
echo ""

echo "─── Claude Desktop Configuration ───"
echo ""
echo "{"
echo "  \"mcpServers\": {"
echo "    \"stella\": {"
echo "      \"command\": \"$VENV_DIR/bin/python\"," 
echo "      \"args\": [\"$STELLA_DIR/stella_server.py\"],"
echo "      \"env\": {"
echo "        \"SWEPH_API_BASE\": \"${SWEPH_API_BASE:-http://100.102.99.117:3000}\""
echo "      }"
echo "    }"
echo "  }"
echo "}"
echo ""

# ── 8. Verify ──
echo "─── Verification ───"
echo ""
echo "Running Stella doctor..."
if "$VENV_DIR/bin/python" "$STELLA_DIR/stella_doctor.py"; then
    echo ""
else
    echo ""
    echo "⚠ Doctor found one or more setup issues above."
fi

echo ""
echo "🌙 Setup complete!"
echo ""
echo "Quick test:"
echo "  npx mcporter call stella.get_current_moon"
echo "  npx mcporter call stella.list_charts"
echo "  ./.venv/bin/python build_graph.py"
