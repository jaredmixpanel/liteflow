# Scheduling Workflows

liteflow supports four scheduling methods for recurring workflow execution, plus event-driven and manual triggers. This guide covers each method, when to use it, and how to set it up.

---

## Scheduling Methods Overview

| Method | Persistence | Runs On | Best For |
|--------|------------|---------|----------|
| In-session cron (`CronCreate`) | Session-scoped | Local | Development, polling |
| Desktop scheduled tasks | Persistent | Local | Daily/weekly with local file access |
| System cron (`cron-runner.sh`) | Persistent | Local | Headless scheduling, no Claude Code needed |
| Cloud Routines | Persistent | Remote | Schedule, GitHub events, or API triggers |

All four methods ultimately invoke `/liteflow:flow-run <workflow-name>` to execute the workflow. They differ in where the scheduler lives and how long the schedule persists.

---

## Cadence Shortcuts

When specifying a cadence, you can use natural-language shortcuts instead of raw cron expressions. These shortcuts work across all scheduling methods:

| Shortcut | Cron Expression | Description |
|----------|----------------|-------------|
| `every 5m` | `*/5 * * * *` | Every 5 minutes |
| `every 30m` | `*/30 * * * *` | Every 30 minutes |
| `hourly` | `0 * * * *` | Top of every hour |
| `daily` / `nightly` | `0 9 * * *` | 9 AM local daily |
| `weekdays` | `0 9 * * 1-5` | 9 AM Mon--Fri |
| `weekly` | `0 9 * * 1` | Monday 9 AM |

You can also provide any standard 5-field cron expression directly (minute hour day-of-month month day-of-week).

---

## In-Session Cron (Default)

Uses Claude Code's built-in `CronCreate` tool to schedule the workflow within the current session.

```
/liteflow:flow-schedule my-workflow hourly
```

This is the default method when no `--method` flag is specified.

**How it works**: Creates a recurring cron trigger inside the active Claude Code session. At each interval, it runs `/liteflow:flow-run <workflow-name>` automatically.

**Characteristics**:

- Session-scoped -- the schedule is lost when the session ends
- Tasks expire after 7 days automatically
- No setup beyond the command itself
- Good for development, polling, and short-lived monitoring

**Managing scheduled tasks**:

- **List** active schedules: ask "what scheduled tasks do I have?" or use `CronList`
- **Cancel** a schedule: ask "cancel the my-workflow job" or use `CronDelete` with the task ID
- After creating a schedule, note the task ID returned -- you will need it to cancel or inspect later

**One-shot scheduling**: For a one-time delayed execution (e.g., "run this workflow in 30 minutes"), use `CronCreate` with `recurring: false`. Or use natural language: "in 30 minutes, run `/liteflow:flow-run my-workflow`".

---

## Desktop Scheduled Tasks

Persistent local scheduling that survives session restarts. Requires the Claude Code Desktop app.

```
/liteflow:flow-schedule my-workflow daily --method desktop
```

**How it works**: Creates a scheduled task in the Claude Code Desktop app. The Desktop app manages the schedule independently of any individual session.

**Setup options**:

1. **Via command**: Run `/liteflow:flow-schedule <workflow-name> <cadence> --method desktop`
2. **Via Desktop UI**: Open **Schedule** in the Desktop sidebar, then **New task** > **New local task**. Set the prompt to `/liteflow:flow-run <workflow-name>` and choose the frequency.
3. **Via natural language**: In any Desktop session, ask: "set up a daily task to run `/liteflow:flow-run my-workflow` every morning at 9am"

**Characteristics**:

- Persists across session restarts
- Has access to local files and `~/.liteflow/` databases
- Runs even without an open session (but requires the Desktop app to be running)
- Supports missed-run catch-up -- one catch-up run on wake if a scheduled run was missed
- Minimum interval: 1 minute

---

## System Cron

Persistent scheduling using the operating system's crontab. Does NOT require Claude Code to be running.

```
/liteflow:flow-schedule my-workflow "0 9 * * *" --method cron
```

**How it works**: Adds an entry to your user's crontab that invokes the `scripts/cron-runner.sh` wrapper script. This script handles PATH setup, working directory, and logging, then runs the workflow directly via `python3 -m lib.cli run`.

### The cron-runner.sh Script

The wrapper script at `scripts/cron-runner.sh` handles the details of running a workflow from a bare cron environment:

- Sets up PATH for `python3`
- Changes to the plugin root directory (so Python relative imports work)
- Runs `python3 -m lib.cli run "$@"` with all arguments passed through
- Logs output to `~/.liteflow/cron.log` with UTC timestamps
- Preserves exit codes

The log location defaults to `~/.liteflow/cron.log` but respects the `LITEFLOW_HOME` environment variable if set.

### Example Crontab Entries

```
# Run a workflow every morning at 9 AM
0 9 * * * /path/to/liteflow/scripts/cron-runner.sh my-workflow

# Run a health check every 30 minutes with initial context
*/30 * * * * /path/to/liteflow/scripts/cron-runner.sh health-check --context '{"alert": true}'

# Run a data sync on weekdays at 8 AM
0 8 * * 1-5 /path/to/liteflow/scripts/cron-runner.sh data-sync --context '{"source": "prod"}'
```

Replace `/path/to/liteflow` with the actual path to your liteflow plugin directory.

### Manual Crontab Setup

If you prefer to set up the crontab entry yourself:

1. Open your crontab: `crontab -e`
2. Add the entry with the cron expression and the full path to `cron-runner.sh`
3. Save and exit
4. Verify with `crontab -l`

### Important Limitations

- **Claude step types will fail**: Workflows with `type: "claude"` steps require the `claude` CLI to be available in the cron environment's PATH. Under system cron, the CLI is typically not available, so those steps will fail. System cron is best for workflows using only `script`, `shell`, `http`, `transform`, `query`, `gate`, `fan-out`, and `fan-in` step types.
- **Machine must be awake**: System cron only fires when the machine is running. If the machine is asleep at the scheduled time, the run is skipped (no catch-up).

---

## Cloud Routines

Runs on Anthropic's cloud infrastructure. Works when your laptop is off.

```
/liteflow:flow-schedule my-workflow daily --method cloud
```

**How it works**: Creates a Claude Code Routine with a schedule trigger. The Routine runs against a fresh clone of the repository on Anthropic's infrastructure at each interval.

**Characteristics**:

- Persistent -- survives session restarts and machine shutdowns
- Runs even when your laptop is closed or off
- Operates against a fresh clone, not your local checkout
- Requires Claude Code's Routines feature to be enabled
- Minimum interval: 1 hour
- Most reliable for production schedules

---

## GitHub Event Triggers

Create a Claude Code Routine that triggers a workflow in response to GitHub events.

```
/liteflow:flow-on-github pr-opened my-review-workflow
```

**Supported event types**:

| Event | Trigger |
|-------|---------|
| `pr-opened` | A pull request is opened |
| `pr-merged` | A pull request is merged |
| `push` | Push to a branch (defaults to `main`) |
| `issue-created` | A new issue is created |
| `release-published` | A release is published |

The created Routine passes the GitHub event payload as context via `--context`, so workflow steps can access event data such as PR number, branch name, issue body, and more.

**Requirements**:

- Claude Code's Routines feature must be enabled
- GitHub integration must be configured for event triggers to work

---

## API Triggers

Create an API endpoint that triggers a workflow on demand via HTTP POST.

```
/liteflow:flow-on-api my-workflow
```

After creation, you receive:

- **Endpoint URL** for triggering the workflow
- **Bearer token** for authentication
- **Example curl command** for testing

```bash
curl -X POST <endpoint-url> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'
```

The POST body is passed to the workflow as initial context via `--context`, so any JSON payload you send becomes available to workflow steps.

**Requirements**: Claude Code's Routines feature must be enabled.

---

## The /loop Integration

liteflow includes a `templates/loop.md` template for health-check polling during active sessions. The template runs `/liteflow:flow-status` to check system health, reviews recent failures via `/liteflow:flow-history`, and reports a one-line "all clear" if everything is healthy.

**Setup**: Copy the template to your Claude Code configuration to make the bare `/loop` command run liteflow health checks:

```bash
cp /path/to/liteflow/templates/loop.md ~/.claude/loop.md
```

**Other /loop patterns**:

- `/loop /liteflow:flow-run my-workflow` -- run any workflow on a recurring loop
- `/loop /liteflow:flow-status` -- periodic status checks during a session

The `/loop` integration is session-scoped, similar to in-session cron but driven by the loop command's interval.

---

## Other Trigger Methods

Beyond scheduled and event-driven execution, workflows can be triggered in several additional ways:

| Method | How | Best For |
|--------|-----|----------|
| Manual | `/liteflow:flow-run <name>` | One-off execution |
| Hooks | `SessionStart`, `PostToolUse`, `Stop` events | Session lifecycle automation |
| Chained workflows | One workflow triggers another via a step | Multi-stage pipelines |
| One-shot reminders | "Run this workflow in 30 minutes" | Delayed execution |

---

## Which Method Should I Use?

Use this decision guide to pick the right scheduling method:

| Situation | Recommended Method |
|-----------|--------------------|
| Just testing or developing a workflow | In-session cron (default) |
| Monitoring while you work | In-session cron or `/loop` |
| Need the schedule to persist across sessions | Desktop scheduled tasks or system cron |
| Workflow uses only script/shell/http steps (no `claude` steps) | System cron |
| Need it to run when your laptop is off | Cloud Routines |
| Triggered by GitHub events (PRs, pushes, issues) | `/liteflow:flow-on-github` |
| Triggered by external API calls | `/liteflow:flow-on-api` |
| One-time delayed execution | One-shot via `CronCreate` with `recurring: false` |

**General rule**: Start with in-session cron during development. Once the workflow is stable, move to desktop tasks or system cron for local persistence, or Cloud Routines if the machine might be off.

---

## See Also

- [Installation](installation.md) -- first-time setup
- [Your First Workflow](first-workflow.md) -- creating the workflow to schedule
- [Templates](templates.md) -- template-based workflow creation
- [Command Reference: flow-schedule, flow-on-github, flow-on-api](../reference/commands.md#trigger-commands) -- detailed command documentation
- [Architecture Overview](../concepts/architecture.md) -- system design
- [Documentation Home](../index.md) -- docs index
