---
name: flow-schedule
description: Schedule a workflow to run automatically (session, desktop, cron, or cloud)
argument-hint: "<workflow-name> <cadence> [--method session|desktop|cron|cloud]"
allowed-tools: ["Bash", "CronCreate", "CronList", "CronDelete"]
---

Schedule a workflow to run on a recurring cadence. Four scheduling methods are available, each with different trade-offs. If the user doesn't specify a method, recommend based on their needs.

## 1. In-Session Scheduling (default, via CronCreate)

Uses Claude Code's built-in `CronCreate` tool to schedule the workflow within the current session. Session-scoped — the schedule is lost when the session ends. Best for development, polling, and short-lived monitoring.

Use the `CronCreate` tool with:
- **cron expression**: Convert the user's cadence to a 5-field cron expression (minute hour day-of-month month day-of-week). Common conversions:
  - `hourly` → `0 * * * *`
  - `every 5m` → `*/5 * * * *`
  - `every 30m` → `*/30 * * * *`
  - `nightly` / `daily` → `0 9 * * *` (9am local)
  - `weekdays` → `0 9 * * 1-5`
  - `weekly` → `0 9 * * 1` (Monday 9am)
- **prompt**: `/liteflow:flow-run <workflow-name>`
- **recurring**: `true`

After creating, confirm the schedule with the user and show the task ID for later management.

Inform the user they can also:
- List scheduled tasks: ask "what scheduled tasks do I have?" or use `CronList`
- Cancel a task: ask "cancel the <name> job" or use `CronDelete` with the task ID
- Tasks expire after 7 days automatically

## 2. Desktop Scheduled Tasks (persistent local)

For schedules that should survive session restarts but need local file access. Requires Claude Code Desktop app.

Tell the user to create a Desktop scheduled task:
- Open **Schedule** in the Desktop sidebar → **New task** → **New local task**
- Set the prompt to: `/liteflow:flow-run <workflow-name>`
- Choose the frequency (hourly, daily, weekdays, weekly)
- Set permission mode as needed

Or the user can ask Claude in any Desktop session: "set up a daily task to run `/liteflow:flow-run <workflow-name>` every morning at 9am"

Desktop tasks:
- Persist across restarts
- Have access to local files and `~/.liteflow/` databases
- Run even without an open session (but require the Desktop app to be running)
- Support missed-run catch-up (one catch-up run on wake)
- Minimum interval: 1 minute

## 3. System Cron (persistent, no Claude Code required)

For persistent scheduling that runs the workflow directly via Python, without needing Claude Code. Best for workflows that don't use `claude` step types — pure automation like data sync, health checks, and notification pipelines.

Generate a crontab entry for the user. The entry uses the `cron-runner.sh` wrapper script:

```
<cron-expression> ${CLAUDE_PLUGIN_ROOT}/scripts/cron-runner.sh <workflow-name>
```

Convert the user's cadence to a cron expression (same rules as section 1).

Provide the user with:
1. The exact crontab entry to add
2. Instructions: run `crontab -e` and paste the line
3. How to verify: `crontab -l` to list, `crontab -e` to edit

Example output for "run health-check every morning at 9am":
```
0 9 * * * ${CLAUDE_PLUGIN_ROOT}/scripts/cron-runner.sh health-check
```

With initial context:
```
*/30 * * * * ${CLAUDE_PLUGIN_ROOT}/scripts/cron-runner.sh data-sync --context '{"source": "prod"}'
```

Inform the user that:
- System cron does NOT require Claude Code to be running
- Workflows with `claude` step types will fail under system cron (no Claude CLI available)
- Execution logs are written to `~/.liteflow/cron.log`
- The machine must be awake for cron to fire

## 4. Cloud Routines (persistent remote)

For schedules that should run even when the user's machine is off. Uses Anthropic's cloud infrastructure.

Create a Routine using Claude Code's Routines feature with:
- A schedule trigger matching the user's cadence
- The prompt: `Run /liteflow:flow-run <workflow-name>`

Inform the user that:
- Routines run against a fresh clone, not the local checkout
- They require Claude Code's Routines feature to be enabled
- Minimum interval: 1 hour

## One-Shot Scheduling

If the user asks for a one-time delayed execution (e.g., "run this workflow in 30 minutes"), use `CronCreate` with `recurring: false` and the appropriate cron expression. Or suggest natural language: "in 30 minutes, run /liteflow:flow-run <workflow-name>".

## Method Selection Guide

If the user doesn't specify a method, recommend based on:
- **"I want to poll while I work"** → In-session (CronCreate)
- **"I want this to run every day"** → Desktop scheduled task or system cron
- **"I want this to run without Claude Code"** → System cron
- **"I want this to run even when my laptop is closed"** → Cloud Routine
