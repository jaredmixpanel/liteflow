import json
import sys

# Claude step — the engine sends this prompt to Claude with context injected.

PROMPT_TEMPLATE = """You are a system health reporting assistant for liteflow, a workflow automation engine. Compile the following diagnostic results into a clear, actionable health report.

## Database Integrity
{db_section}

## Stale Runs
{stale_section}

## Dead Letter Queue
{dead_letter_section}

## Credentials
{credentials_section}

## Disk Usage
{disk_section}

---

Format the health report as:

1. **Overall Status** — GREEN (all healthy), YELLOW (minor issues), or RED (critical issues). Use a single word verdict.

2. **Issues Found** — List each issue with severity (critical/warning/info) and a recommended action.

3. **Metrics Summary** — Key numbers: database count, stale runs, dead letters, credential status, total disk usage.

4. **Recommended Actions** — Ordered list of things to do, most urgent first. Include specific commands where applicable.

Keep it concise and actionable. Skip sections with no issues (just note them as healthy)."""


def run(context: dict) -> dict:
    """Build the prompt for Claude health report from all diagnostic step outputs."""

    # Database health
    db_health = context.get("db_health", {})
    all_healthy = context.get("all_healthy", True)
    if db_health:
        db_lines = []
        for name, info in db_health.items():
            status = info.get("status", "unknown")
            size = info.get("size_bytes", 0)
            db_lines.append(f"- {name}: {status} ({size} bytes)")
        db_section = "\n".join(db_lines)
        if not all_healthy:
            db_section += "\n\nERRORS: " + "; ".join(context.get("errors", []))
    else:
        db_section = "No databases found or database check did not run."

    # Stale runs
    stale_runs = context.get("stale_runs", [])
    stale_count = context.get("stale_count", 0)
    if stale_runs:
        stale_lines = [f"Found {stale_count} stale run(s):"]
        for run_info in stale_runs:
            stale_lines.append(
                f"- Run {run_info['run_id']}: workflow '{run_info['workflow']}' "
                f"started at {run_info['started_at']}"
            )
        stale_section = "\n".join(stale_lines)
    else:
        stale_section = "No stale runs detected."

    # Dead letters
    dead_letters = context.get("dead_letters", [])
    dead_letter_count = context.get("dead_letter_count", 0)
    if dead_letters:
        dl_lines = [f"Found {dead_letter_count} dead letter message(s):"]
        for dl in dead_letters[:10]:  # Show at most 10
            dl_lines.append(
                f"- Queue '{dl['queue']}': {dl['error']} "
                f"(retries: {dl['retry_count']}, failed: {dl['failed_at']})"
            )
        if dead_letter_count > 10:
            dl_lines.append(f"  ... and {dead_letter_count - 10} more")
        dead_letter_section = "\n".join(dl_lines)
    else:
        dead_letter_section = "No dead letter messages."

    # Credentials
    credentials = context.get("credentials", {})
    invalid = context.get("invalid", [])
    if credentials:
        cred_lines = []
        for service, info in credentials.items():
            cred_lines.append(f"- {service}: {info.get('status', 'unknown')}")
        credentials_section = "\n".join(cred_lines)
        if invalid:
            credentials_section += f"\n\nInvalid credentials: {', '.join(invalid)}"
    else:
        credentials_section = "No credentials configured."

    # Disk usage
    disk_usage = context.get("disk_usage", [])
    total = context.get("total", "unknown")
    if disk_usage:
        disk_lines = [f"Total: {total}"]
        for item in disk_usage:
            disk_lines.append(f"- {item.get('path', '?')}: {item.get('size', '?')}")
        disk_section = "\n".join(disk_lines)
    else:
        disk_section = f"Total usage: {total}"

    prompt = PROMPT_TEMPLATE.format(
        db_section=db_section,
        stale_section=stale_section,
        dead_letter_section=dead_letter_section,
        credentials_section=credentials_section,
        disk_section=disk_section,
    )

    return {"prompt": prompt}


if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
