import json
import sys

# Claude step — the engine sends this prompt template to Claude with context injected.
# This script defines the prompt and extracts relevant context for the LLM.

PROMPT_TEMPLATE = """You are a concise daily briefing assistant. Summarize the following GitHub activity into a clear, actionable morning briefing.

## Pull Requests Awaiting Review ({pr_count})
{prs_summary}

## Open Issues Assigned to You ({issue_count})
{issues_summary}

## Recent Notifications ({notification_count})
{notifications_summary}

---

Format the briefing as:
1. **Priority Actions** — things that need attention today (stale PRs, urgent issues, direct mentions)
2. **Review Queue** — PRs to review, ordered by age
3. **Issues Overview** — grouped by repo, with any notable activity
4. **FYI** — notifications that are informational only

Keep it concise. Use bullet points. Highlight anything that looks time-sensitive."""


def run(context: dict) -> dict:
    """Build the prompt for Claude summarization from upstream step outputs."""
    prs = context.get("prs", [])
    issues = context.get("issues", [])
    notifications = context.get("notifications", [])

    # Format PRs
    if prs:
        prs_summary = "\n".join(
            f"- [{pr['title']}]({pr['url']}) by @{pr['author']} in {pr['repo']}"
            for pr in prs
        )
    else:
        prs_summary = "No PRs awaiting your review."

    # Format issues
    if issues:
        issues_summary = "\n".join(
            f"- [{issue['title']}]({issue['url']}) in {issue['repo']} ({issue['comments']} comments)"
            for issue in issues
        )
    else:
        issues_summary = "No open issues assigned to you."

    # Format notifications
    if notifications:
        notifications_summary = "\n".join(
            f"- [{n['type']}] {n['title']} in {n['repo']} (reason: {n['reason']})"
            for n in notifications
        )
    else:
        notifications_summary = "No new notifications."

    prompt = PROMPT_TEMPLATE.format(
        pr_count=len(prs),
        prs_summary=prs_summary,
        issue_count=len(issues),
        issues_summary=issues_summary,
        notification_count=len(notifications),
        notifications_summary=notifications_summary,
    )

    return {"prompt": prompt}


if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
