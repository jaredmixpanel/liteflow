import json
import sys

# Claude step — the engine sends this prompt to Claude with context injected.

PROMPT_TEMPLATE = """You are an expert code reviewer writing the final review for a pull request. Combine the code analysis findings with CI/test results into a structured, actionable review.

## Code Analysis Findings
{analysis}

## CI/Test Results
{test_summary}

## Instructions

Write a pull request review that includes:

1. **Summary** — One paragraph overview of the changes and their quality.

2. **Critical Issues** — Must-fix items that should block merge. Include file, line, and specific fix suggestions.

3. **Warnings** — Important issues that should be addressed but may not block merge.

4. **Suggestions** — Nice-to-have improvements for code quality, readability, or performance.

5. **CI Status** — Summary of test results. Flag any failing or missing checks.

6. **Verdict** — One of: APPROVE (no critical issues), REQUEST_CHANGES (has critical issues), or COMMENT (needs discussion).

Format the review in clean Markdown suitable for posting as a GitHub PR comment. Be constructive and specific — every criticism should include a suggested improvement."""


def run(context: dict) -> dict:
    """Build the prompt for Claude review generation from analysis and test results."""
    # Get analysis from the analyze-changes step
    analysis = context.get("analysis", "")
    if not analysis:
        # Try to get findings directly
        findings = context.get("findings", [])
        if findings:
            analysis = json.dumps(findings, indent=2)
        else:
            analysis = "No code analysis findings available."

    # Get test results from the check-tests step
    check_summary = context.get("check_summary", {})
    checks = context.get("checks", [])

    if check_summary:
        test_summary = (
            f"Total checks: {check_summary.get('total', 0)}\n"
            f"Passing: {check_summary.get('passing', 0)}\n"
            f"Failing: {check_summary.get('failing', 0)}\n"
            f"Pending: {check_summary.get('pending', 0)}\n"
        )
        # Add details for failing checks
        failing = [c for c in checks if c.get("state") == "FAILURE"]
        if failing:
            test_summary += "\nFailing checks:\n"
            for c in failing:
                test_summary += f"- {c.get('name')}: {c.get('description', 'No details')}\n"
    else:
        test_summary = "No CI/test results available."

    prompt = PROMPT_TEMPLATE.format(
        analysis=analysis,
        test_summary=test_summary,
    )

    return {"prompt": prompt}


if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
