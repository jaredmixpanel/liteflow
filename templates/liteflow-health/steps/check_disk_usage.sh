#!/usr/bin/env bash
# Report disk usage for all liteflow data directories and files.

set -euo pipefail

LITEFLOW_DIR="$HOME/.liteflow"

if [ ! -d "$LITEFLOW_DIR" ]; then
    echo '{"disk_usage": {}, "total": "0B", "error": "liteflow directory not found"}'
    exit 0
fi

# Get per-item disk usage
USAGE=$(du -sh "$LITEFLOW_DIR"/* 2>/dev/null | sort -rh)
TOTAL=$(du -sh "$LITEFLOW_DIR" 2>/dev/null | cut -f1)

# Convert to JSON
ITEMS="[]"
if [ -n "$USAGE" ]; then
    ITEMS=$(echo "$USAGE" | jq -R -s '
        split("\n") | map(select(length > 0)) | map(
            split("\t") | {size: .[0], path: .[1]}
        )
    ')
fi

jq -n \
    --argjson items "$ITEMS" \
    --arg total "${TOTAL:-0B}" \
    '{
        "disk_usage": $items,
        "total": $total
    }'
