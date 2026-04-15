#!/usr/bin/env bash
# cron-runner.sh — Run a liteflow workflow from system cron.
#
# Usage in crontab:
#   0 9 * * * /path/to/liteflow/scripts/cron-runner.sh my-workflow
#   */30 * * * * /path/to/liteflow/scripts/cron-runner.sh health-check --context '{"alert": true}'
#
# This wrapper handles:
#   - cd to the plugin root so Python relative imports work
#   - PATH setup for python3
#   - Logging output to ~/.liteflow/cron.log
#   - Exit code passthrough

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="${LITEFLOW_HOME:-$HOME/.liteflow}/cron.log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

{
    echo "--- $(date -u '+%Y-%m-%dT%H:%M:%SZ') | workflow: $* ---"
    cd "$PLUGIN_ROOT"
    python3 -m lib.cli run "$@" 2>&1
    echo "--- exit: $? ---"
    echo ""
} >> "$LOG_FILE" 2>&1
