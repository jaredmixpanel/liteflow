import json
import sys

# Claude step — the engine sends this prompt to Claude with context injected.

PROMPT_TEMPLATE = """You are an expert code reviewer. Analyze the following pull request diff and provide a detailed review.

## PR Diff
```diff
{diff}
```

## Analysis Instructions

Review the diff for:

1. **Bugs and Logic Errors** — Off-by-one errors, null/undefined access, race conditions, missing error handling, incorrect boolean logic.

2. **Security Issues** — Hardcoded secrets, SQL injection, XSS, path traversal, insecure deserialization, missing input validation.

3. **Performance Concerns** — N+1 queries, unnecessary allocations, missing pagination, unbounded loops, expensive operations in hot paths.

4. **Code Quality** — Naming clarity, dead code, code duplication, overly complex functions, missing or misleading comments.

5. **API Design** — Breaking changes, inconsistent naming, missing validation, unclear error responses.

6. **Testing Gaps** — Untested edge cases, missing error path tests, brittle assertions.

For each finding, provide:
- **File and line range** in the diff
- **Severity**: critical / warning / suggestion / nit
- **Description** of the issue
- **Suggested fix** with code if applicable

Output your analysis as structured JSON with a "findings" array."""


def run(context: dict) -> dict:
    """Build the prompt for Claude analysis from the PR diff."""
    diff = context.get("diff", "")

    if not diff:
        return {"prompt": "", "error": "No diff content available to analyze"}

    # Truncate very large diffs to stay within token limits
    max_diff_chars = 50000
    if len(diff) > max_diff_chars:
        diff = diff[:max_diff_chars] + "\n\n... (diff truncated, showing first 50k characters)"

    prompt = PROMPT_TEMPLATE.format(diff=diff)
    return {"prompt": prompt}


if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
