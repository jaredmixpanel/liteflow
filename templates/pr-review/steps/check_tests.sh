#!/usr/bin/env bash
# Check PR CI status and test results using gh CLI.
# Reads repo and pr_number from JSON stdin context.

set -euo pipefail

INPUT=$(cat)
REPO=$(echo "$INPUT" | jq -r '.repo // empty')
PR_NUMBER=$(echo "$INPUT" | jq -r '.pr_number // empty')

if [ -z "$REPO" ] || [ -z "$PR_NUMBER" ]; then
    echo '{"error": "Missing repo or pr_number in context"}'
    exit 1
fi

# Fetch check status as JSON
CHECKS=$(gh pr checks "$PR_NUMBER" --repo "$REPO" --json name,state,description,detailsUrl 2>&1) || {
    echo "{\"checks\": [], \"error\": \"Failed to fetch checks: $(echo "$CHECKS" | head -1)\"}"
    exit 1
}

# Summarize check results
TOTAL=$(echo "$CHECKS" | jq 'length')
PASSING=$(echo "$CHECKS" | jq '[.[] | select(.state == "SUCCESS")] | length')
FAILING=$(echo "$CHECKS" | jq '[.[] | select(.state == "FAILURE")] | length')
PENDING=$(echo "$CHECKS" | jq '[.[] | select(.state == "PENDING")] | length')

jq -n \
    --argjson checks "$CHECKS" \
    --argjson total "$TOTAL" \
    --argjson passing "$PASSING" \
    --argjson failing "$FAILING" \
    --argjson pending "$PENDING" \
    '{
        "checks": $checks,
        "check_summary": {
            "total": $total,
            "passing": $passing,
            "failing": $failing,
            "pending": $pending
        }
    }'
