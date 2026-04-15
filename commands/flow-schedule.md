---
name: flow-schedule
description: Create a scheduled Routine to trigger a workflow
argument-hint: "<workflow-name> <cadence>"
allowed-tools: ["Bash"]
---

Create a Claude Code Routine that runs the specified workflow on a schedule.

If no workflow name or cadence is provided, ask the user for both.

Supported cadence options:
- `hourly` — every hour
- `nightly` — once per day at midnight
- `weekly` — once per week on Monday at 9am
- A cron expression (e.g., `*/30 * * * *` for every 30 minutes)

The Routine's prompt should be: `Run /liteflow:flow-run <workflow-name>`

Create the Routine using Claude Code's Routines feature if available.

Inform the user that Routines require Claude Code's Routines feature to be enabled and available.

If Routines are not available, suggest using system cron as a fallback:
1. Explain the fallback approach
2. Provide the crontab entry: run `crontab -e` and add an entry like:
   ```
   0 * * * * claude -p "/liteflow:flow-run <workflow-name>"
   ```
   (adjusted for the selected cadence)
3. Warn that the cron fallback requires `claude` CLI to be in the system PATH.
