#!/usr/bin/env bash
# liteflow setup — install dependencies and initialize databases
set -euo pipefail

LITEFLOW_HOME="${LITEFLOW_HOME:-$HOME/.liteflow}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "liteflow setup"
echo "=============="
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 is required but not found."
    echo "Install Python 3.7+ and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python: $PYTHON_VERSION"

# Install core dependencies
echo ""
echo "Installing core dependencies..."
python3 -m pip install -q sqlite-utils simple-graph-sqlite litequeue sqlitedict 2>/dev/null || \
python3 -m pip install -q --user sqlite-utils simple-graph-sqlite litequeue sqlitedict 2>/dev/null || \
python3 -m pip install -q --break-system-packages sqlite-utils simple-graph-sqlite litequeue sqlitedict

echo "  sqlite-utils: $(python3 -c 'import sqlite_utils; print(sqlite_utils.__version__)' 2>/dev/null || echo 'installed')"
echo "  simple-graph-sqlite: installed"
echo "  litequeue: installed"
echo "  sqlitedict: installed"

# Initialize liteflow home
echo ""
echo "Initializing liteflow home: $LITEFLOW_HOME"
mkdir -p "$LITEFLOW_HOME"
mkdir -p "$LITEFLOW_HOME/steps"

# Initialize databases
python3 "$SCRIPT_DIR/lib/cli.py" setup 2>/dev/null && echo "Databases initialized." || echo "Run /liteflow:flow-setup to initialize databases."

echo ""
echo "liteflow is ready. Start with:"
echo "  /liteflow:flow-build     — Build a workflow interactively"
echo "  /liteflow:flow-templates — Create from a template"
echo "  /liteflow:flow-status    — Check system status"
