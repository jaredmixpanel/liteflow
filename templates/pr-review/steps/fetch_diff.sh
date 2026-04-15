#!/usr/bin/env bash
# Fetch the PR diff using gh CLI.
# Expects PR_URL or REPO and PR_NUMBER in the environment/context.
# Context is passed as JSON on stdin; we extract variables with jq.

set -euo pipefail

INPUT=$(cat)
REPO=$(echo "$INPUT" | jq -r '.repo // empty')
PR_NUMBER=$(echo "$INPUT" | jq -r '.pr_number // empty')
PR_URL=$(echo "$INPUT" | jq -r '.pr_url // empty')

# Parse pr_url if repo/number not provided directly
if [ -z "$REPO" ] || [ -z "$PR_NUMBER" ]; then
    if [ -n "$PR_URL" ]; then
        # Handle formats: owner/repo#123 or https://github.com/owner/repo/pull/123
        if echo "$PR_URL" | grep -q '#'; then
            REPO=$(echo "$PR_URL" | cut -d'#' -f1)
            PR_NUMBER=$(echo "$PR_URL" | cut -d'#' -f2)
        else
            REPO=$(echo "$PR_URL" | sed -E 's|https://github.com/([^/]+/[^/]+)/pull/.*|\1|')
            PR_NUMBER=$(echo "$PR_URL" | sed -E 's|.*/pull/([0-9]+).*|\1|')
        fi
    fi
fi

if [ -z "$REPO" ] || [ -z "$PR_NUMBER" ]; then
    echo '{"error": "Could not determine repo and PR number from pr_url variable"}'
    exit 1
fi

DIFF=$(gh pr diff "$PR_NUMBER" --repo "$REPO" 2>&1) || {
    echo "{\"error\": \"Failed to fetch diff: $(echo "$DIFF" | head -1)\"}"
    exit 1
}

# Output as JSON with diff content, repo, and pr_number for downstream steps
jq -n \
    --arg diff "$DIFF" \
    --arg repo "$REPO" \
    --arg pr_number "$PR_NUMBER" \
    '{"diff": $diff, "repo": $repo, "pr_number": $pr_number}'
