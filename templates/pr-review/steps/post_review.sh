#!/usr/bin/env bash
# Post the generated review as a comment on the PR.
# Reads repo, pr_number, and review body from JSON stdin context.

set -euo pipefail

INPUT=$(cat)
REPO=$(echo "$INPUT" | jq -r '.repo // empty')
PR_NUMBER=$(echo "$INPUT" | jq -r '.pr_number // empty')
REVIEW_BODY=$(echo "$INPUT" | jq -r '.review // .response // empty')

if [ -z "$REPO" ] || [ -z "$PR_NUMBER" ]; then
    echo '{"error": "Missing repo or pr_number in context"}'
    exit 1
fi

if [ -z "$REVIEW_BODY" ]; then
    echo '{"error": "No review body available to post"}'
    exit 1
fi

# Post the review as a PR comment
RESULT=$(gh pr review "$PR_NUMBER" --repo "$REPO" --comment --body "$REVIEW_BODY" 2>&1) || {
    echo "{\"error\": \"Failed to post review: $(echo "$RESULT" | head -1)\"}"
    exit 1
}

echo '{"posted": true, "message": "Review posted successfully"}'
