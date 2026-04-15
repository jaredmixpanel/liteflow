# Command Reference

Complete reference for all 16 plugin commands, 3 agents, 2 skills, and 1 hook that make up the liteflow plugin surface.

---

## Quick Reference Table

| Command | Description | Key Arguments |
|---------|-------------|---------------|
| `flow-setup` | Install dependencies and initialize databases | -- |
| `flow-new` | Create workflow from natural language description | `<name> [description]` |
| `flow-build` | Interactive conversational workflow builder | -- |
| `flow-list` | List all workflows with last run status | -- |
| `flow-show` | Display workflow structure and Mermaid diagram | `<workflow-name>` |
| `flow-run` | Execute a workflow | `<workflow-name> [--dry-run] [--context '{...}']` |
| `flow-history` | Show execution history | `[workflow-name] [--limit N]` |
| `flow-inspect` | Inspect a specific run in detail | `<run-id \| 'last'>` |
| `flow-status` | System status dashboard | -- |
| `flow-edit` | Modify workflow steps and connections | `<workflow-name> <action>` |
| `flow-visualize` | Generate Mermaid diagram | `<workflow-name>` |
| `flow-auth` | Manage service credentials | `<service \| 'list' \| 'test' \| 'remove'>` |
| `flow-schedule` | Schedule workflow execution | `<workflow-name> <cadence> [--method ...]` |
| `flow-on-github` | Create GitHub event-triggered Routine | `<event-type> <workflow-name>` |
| `flow-on-api` | Create API-triggered Routine | `<workflow-name>` |
| `flow-templates` | List and create from workflow templates | `[template-name]` |

---

## Core Commands

### flow-setup

Install all required dependencies and initialize the liteflow databases.

- **Tools**: Bash, Read
- **Arguments**: None
- **Runs**: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py setup`

Creates the `~/.liteflow/` directory with five database files:

| Database | Purpose |
|----------|---------|
| `workflows.db` | Graph definitions (workflows, steps, edges) |
| `execution.db` | Run history and step execution records |
| `queue.db` | Execution queue for step scheduling |
| `credentials.db` | Encrypted service tokens |
| `config.db` | Plugin settings |

Installs the following Python packages:

- `simple-graph-sqlite` -- graph storage for workflow DAGs
- `litequeue` -- queue-driven step execution
- `sqlite-utils` -- state and history tracking
- `sqlitedict` -- encrypted credential storage

After setup completes, confirms that all database files exist and reports installed package versions. If errors occur, diagnoses common problems (missing Python 3, pip issues, permission errors).

> **See also**: [Installation Guide](../getting-started/installation.md)

---

### flow-new

Create a new workflow from a natural language description in one shot.

- **Tools**: Bash, Write, Read, Glob
- **Arguments**: `<name> [description]`

If only a name is given without a description, prompts for what the workflow should do before proceeding.

When both name and description are provided:

1. **Parses the description** to identify individual steps, their types, data flow, and any conditional branches or parallel paths.
2. **Designs the workflow graph** -- determines steps and edges forming the DAG.
3. **Generates step scripts** at `~/.liteflow/steps/<workflow-name>/`, each following the [step contract](step-types/index.md) (reads JSON from stdin, has a `run(context)` function, outputs JSON to stdout).
4. **Registers the workflow** in the graph database with all steps and edges.
5. **Displays the created structure** -- each step with its type, the edges connecting them, and a Mermaid diagram for workflows with 3 or more steps.

**Example**:
```
/liteflow:flow-new pr-monitor "Check GitHub PRs, filter failing CI, send Slack summary"
```

---

### flow-build

Interactively build a workflow through guided conversation.

- **Tools**: Bash, Write, Read, Glob, Agent
- **Arguments**: None

Starts a conversational builder that asks questions one at a time:

1. **What should this workflow accomplish?** -- overall goal and expected outcome
2. **What services/APIs does it need?** -- external dependencies and credentials
3. **Any conditional branches or parallel processing?** -- graph shape

Then iteratively constructs the workflow:

1. **Proposes steps** based on answers -- shows each step's name, type, and purpose. Asks for confirmation or adjustments.
2. **Generates scripts** for each confirmed step following the step contract. Saves to `~/.liteflow/steps/<workflow-name>/`.
3. **Creates the graph** -- registers workflow, steps, and edges via the CLI.
4. **Confirms each step** with the user before proceeding.

After the workflow is fully built, displays the complete structure and suggests next steps:

- Set up credentials: `/liteflow:flow-auth`
- Do a dry run: `/liteflow:flow-run <name> --dry-run`
- Schedule it: `/liteflow:flow-schedule`

---

### flow-list

List all registered workflows with their last run status.

- **Tools**: Bash
- **Arguments**: None
- **Runs**: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py list`

Displays a table with these columns:

| Column | Description |
|--------|-------------|
| **Name** | Workflow name |
| **Steps** | Number of steps in the workflow |
| **Last Run** | Timestamp of most recent execution, or "Never" |
| **Status** | Last run status: success, failed, running, or -- |
| **Created** | When the workflow was created |

If no workflows exist, suggests creating one with `/liteflow:flow-new` or `/liteflow:flow-build`.

---

### flow-show

Display a workflow's structure and generate a visualization.

- **Tools**: Bash, Read
- **Arguments**: `<workflow-name>`
- **Runs**: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py show <workflow-name>`

If no workflow name is provided, lists available workflows and asks the user to choose.

Displays three sections:

1. **Step details** -- for each step: step ID, step type (script, shell, claude, query, http, transform, gate, fan-out, fan-in), and configuration summary.
2. **Edge connections** -- source step to target step, with any condition labels on edges.
3. **Mermaid diagram** -- a flowchart of the workflow graph with appropriate shapes for different step types and labeled edges.

---

### flow-run

Execute a workflow.

- **Tools**: Bash, Read
- **Arguments**: `<workflow-name> [--dry-run] [--context '{...}']`
- **Runs**: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py run <workflow-name> [flags]`

If no workflow name is provided, lists available workflows and asks the user to choose.

**Flags**:

| Flag | Description |
|------|-------------|
| `--dry-run` | Validate the workflow graph and credentials without executing steps |
| `--context '{...}'` | Pass initial context as a JSON object |

Streams progress output showing each step as it executes with its status (running, completed, failed, skipped).

On completion, displays a summary:
- Total execution time
- Number of steps completed
- Final output data

On failure, shows error details and suggests running `/liteflow:flow-inspect last` for a detailed breakdown.

**Example**:
```
/liteflow:flow-run data-sync --context '{"source": "prod", "target": "staging"}'
```

---

### flow-history

Show execution history for workflows.

- **Tools**: Bash
- **Arguments**: `[workflow-name] [--limit N]`
- **Runs**: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py history [--workflow <name>] [--limit N]`

If a workflow name is provided, filters history to that workflow only. Default limit is 20.

Displays a table with these columns:

| Column | Description |
|--------|-------------|
| **Run ID** | Unique identifier for the execution |
| **Workflow** | Workflow name |
| **Status** | success, failed, or running |
| **Started** | Start timestamp |
| **Duration** | How long the run took |
| **Steps Completed** | Steps completed successfully out of total |

If no history exists, suggests running a workflow with `/liteflow:flow-run`.

---

### flow-inspect

Inspect a specific workflow run in detail.

- **Tools**: Bash, Read
- **Arguments**: `<run-id | 'last'>`
- **Runs**: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py inspect <run-id>`

If the argument is `last` or no argument is provided, retrieves the most recent run.

Displays four sections:

1. **Run metadata** -- workflow name, run ID, overall status, start time, end time, total duration.
2. **Step-by-step execution** -- for each step in execution order:
   - Step name and type
   - Status (completed, failed, skipped)
   - Duration
   - Input context (summarized if large)
   - Output data (summarized if large)
3. **Failure analysis** -- for any failed steps:
   - Full error message
   - Analysis of what likely went wrong
   - Suggestions for fixing the issue
4. **Recommendations** -- suggested next actions:
   - Re-run with fixes
   - Edit the workflow: `/liteflow:flow-edit`
   - Check credentials: `/liteflow:flow-auth test`

---

### flow-status

Show a system status dashboard for liteflow.

- **Tools**: Bash, Read
- **Arguments**: None
- **Runs**: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py status`

Displays five sections:

| Section | Content |
|---------|---------|
| **Installed Dependencies** | Python packages and their versions |
| **Database Sizes** | File sizes of each database under `~/.liteflow/` |
| **Queue Depth** | Number of pending items in the execution queue |
| **Recent Runs** | Last 5 workflow executions with status |
| **Configured Credentials** | List of services with credentials configured (names only, never values) |

If liteflow is not set up yet, suggests running `/liteflow:flow-setup` first.

---

### flow-edit

Edit a workflow -- add, remove, or modify steps and connections.

- **Tools**: Bash, Write, Read, Glob
- **Arguments**: `<workflow-name> <action>`

If no action is specified, displays the current workflow structure and asks what the user would like to change.

**Actions**:

#### `add-step <step-description>`

Add a new step to the workflow:

1. Determines step type and configuration from the description
2. Generates a step script following the step contract
3. Saves the script to `~/.liteflow/steps/<workflow-name>/`
4. Registers the step in the graph and asks where to connect it
5. Creates the appropriate edges

#### `remove-step <step-id>`

Remove a step from the workflow:

1. Identifies incoming and outgoing edges
2. Reconnects edges around the removed step to maintain graph continuity
3. Removes the step from the graph and deletes its script file

#### `connect <step-a> <step-b> [--condition '...']`

Create a new edge between two steps. If a condition is provided, adds it as an edge label/condition.

#### `edit-step <step-id>`

Modify an existing step:

1. Reads the current step configuration and script
2. Asks the user what to change
3. Updates the script and/or configuration
4. Saves changes

After any edit, displays the updated workflow structure.

---

### flow-visualize

Generate a Mermaid diagram of a workflow.

- **Tools**: Bash, Read
- **Arguments**: `<workflow-name>`

If no workflow name is provided, lists available workflows and asks the user to choose.

Generates a Mermaid flowchart using distinct node shapes and colors by step type:

| Step Type | Node Shape | Color |
|-----------|-----------|-------|
| `script` | Rectangle `[Name]` | Blue |
| `shell` | Rectangle `[Name]` | Blue |
| `claude` | Stadium `([Name])` | Purple |
| `query` | Subroutine `[[Name]]` | Green |
| `http` | Parallelogram `[/Name/]` | Orange |
| `transform` | Hexagon `{{Name}}` | Teal |
| `gate` | Diamond `{Name}` | Yellow |
| `fan-out` | Double circle `(((Name)))` | Pink |
| `fan-in` | Double circle `(((Name)))` | Pink |

Labels edges with condition text where applicable. Outputs a complete Mermaid code block renderable in any Mermaid-compatible viewer.

---

## Credential Commands

### flow-auth

Manage service credentials for workflow integrations.

- **Tools**: Bash, Read
- **Arguments**: `<service | 'list' | 'test' | 'remove'> [service-name]`

**CRITICAL**: Never displays actual credential values. Shows masked versions only (e.g., `sk-****abcd`).

If no argument is provided, defaults to `list`.

**Actions**:

#### `list`

Show all configured services with their credential type and status. Never shows actual secret values.

```
/liteflow:flow-auth list
```

#### `<service-name>` (set up credentials)

Interactively set up credentials for a service:

1. Asks for the credential type: token, webhook URL, or service account JSON
2. Asks for the credential value
3. Stores via `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py auth set --service <service-name> --token <value>`
4. Confirms storage and suggests testing

#### `test <service-name>`

Validate stored credentials by making an API call to the service. Reports whether the credential is valid, invalid, or expired.

```
/liteflow:flow-auth test github
```

#### `remove <service-name>`

Delete stored credentials for a service. Confirms with the user before removing.

```
/liteflow:flow-auth remove slack
```

> **See also**: [Credential Management Guide](../getting-started/credentials.md)

---

## Trigger Commands

### flow-schedule

Schedule a workflow to run automatically.

- **Tools**: Bash, CronCreate, CronList, CronDelete
- **Arguments**: `<workflow-name> <cadence> [--method session|desktop|cron|cloud]`

If no method is specified, recommends one based on the user's needs.

#### Cadence shortcuts

| Shortcut | Cron Expression | Description |
|----------|----------------|-------------|
| `every 5m` | `*/5 * * * *` | Every 5 minutes |
| `every 30m` | `*/30 * * * *` | Every 30 minutes |
| `hourly` | `0 * * * *` | Top of every hour |
| `daily` / `nightly` | `0 9 * * *` | 9 AM local daily |
| `weekdays` | `0 9 * * 1-5` | 9 AM Mon--Fri |
| `weekly` | `0 9 * * 1` | Monday 9 AM |

#### Scheduling methods

**1. In-Session** (default) -- via `CronCreate`

Session-scoped scheduling using Claude Code's built-in cron tool. The schedule is lost when the session ends. Best for development, polling, and short-lived monitoring.

- Creates a cron trigger with the specified cadence
- The prompt runs `/liteflow:flow-run <workflow-name>`
- Tasks expire after 7 days automatically
- Manage via `CronList` / `CronDelete`

**2. Desktop Scheduled Tasks** -- persistent local

Persistent local schedules that survive session restarts. Requires the Claude Code Desktop app.

- Created via the Desktop sidebar: Schedule > New task > New local task
- Has access to local files and `~/.liteflow/` databases
- Runs even without an open session (Desktop app must be running)
- Supports missed-run catch-up (one catch-up run on wake)
- Minimum interval: 1 minute

**3. System Cron** -- persistent, no Claude Code required

Runs the workflow directly via Python using the `scripts/cron-runner.sh` wrapper. Best for workflows that do not use `claude` step types (pure automation like data sync, health checks, notification pipelines).

```
<cron-expression> ${CLAUDE_PLUGIN_ROOT}/scripts/cron-runner.sh <workflow-name>
```

- Does NOT require Claude Code to be running
- Workflows with `claude` step types will fail (no Claude CLI available)
- Logs written to `~/.liteflow/cron.log`
- Machine must be awake for cron to fire

**4. Cloud Routines** -- persistent remote

Runs on Anthropic's cloud infrastructure, even when the user's machine is off.

- Requires Claude Code's Routines feature to be enabled
- Runs against a fresh clone, not the local checkout
- Minimum interval: 1 hour

#### Method selection guide

| Need | Recommended Method |
|------|--------------------|
| Poll while working | In-session (CronCreate) |
| Run every day | Desktop scheduled task or system cron |
| Run without Claude Code | System cron |
| Run when laptop is closed | Cloud Routine |

#### One-shot scheduling

For one-time delayed execution (e.g., "run in 30 minutes"), use `CronCreate` with `recurring: false`.

> **See also**: [Scheduling Guide](../getting-started/scheduling.md)

---

### flow-on-github

Create a GitHub event-triggered Routine for a workflow.

- **Tools**: Bash
- **Arguments**: `<event-type> <workflow-name>`

If no event type or workflow name is provided, asks for both.

**Supported event types**:

| Event | Trigger |
|-------|---------|
| `pr-opened` | Pull request is opened |
| `pr-merged` | Pull request is merged |
| `push` | Push to a branch (asks which branch, default: `main`) |
| `issue-created` | New issue is created |
| `release-published` | Release is published |

The created Routine:

1. Is triggered by the specified GitHub event
2. Runs `/liteflow:flow-run <workflow-name>` with the event payload passed as context via `--context`
3. Includes the event payload so workflow steps can access event data (PR number, branch, issue body, etc.)

Requirements:
- Claude Code's Routines feature must be enabled
- GitHub integration must be configured for event triggers

---

### flow-on-api

Create an API-triggered Routine for a workflow.

- **Tools**: Bash
- **Arguments**: `<workflow-name>`

If no workflow name is provided, asks the user which workflow to expose via API.

Creates a Routine with an API trigger that:

1. Accepts HTTP POST requests
2. Runs `/liteflow:flow-run <workflow-name>` with the POST body passed as context
3. Returns execution results

After creation, returns:

- **Endpoint URL** for triggering the workflow
- **Bearer token** for authentication
- **Example curl command**:

```bash
curl -X POST <endpoint-url> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'
```

Requires Claude Code's Routines feature to be enabled.

---

## Template Commands

### flow-templates

List available workflow templates or create a workflow from a template.

- **Tools**: Bash, Read, Write, Glob
- **Arguments**: `[template-name]`

#### Without arguments -- list templates

Lists all templates from `${CLAUDE_PLUGIN_ROOT}/templates/`, showing:

- **Name** -- template identifier
- **Description** -- what the workflow does
- **Required Credentials** -- services that need authentication configured

Reads each template's `manifest.json` to extract this information.

#### With template name -- create from template

Creates a workflow from the specified template:

1. **Reads the template** -- loads `manifest.json` and `workflow.json` from `${CLAUDE_PLUGIN_ROOT}/templates/<template-name>/`.
2. **Gathers configuration** -- asks for required values:
   - Credentials for required services (suggests `/liteflow:flow-auth`)
   - Custom values specific to the template (repository names, channel IDs, email addresses, etc.)
3. **Copies step scripts** -- from the template's `steps/` directory to `~/.liteflow/steps/<workflow-name>/`, substituting configuration placeholders.
4. **Registers the workflow** -- adds the workflow graph to the database with all steps and edges.
5. **Confirms and suggests next steps**:
   - Shows the created workflow structure
   - Suggests credential setup: `/liteflow:flow-auth <service>`
   - Suggests a test run: `/liteflow:flow-run <workflow-name> --dry-run`
   - Suggests scheduling if appropriate: `/liteflow:flow-schedule`

---

## Agents

Agents are autonomous specialists triggered by natural language patterns. All three use the Sonnet model.

### workflow-builder

Decomposes natural language descriptions into complete, working workflows.

- **Model**: Sonnet
- **Tools**: Read, Write, Bash, Grep, Glob

**Trigger patterns**:
- "Build me a workflow that..."
- "I need a workflow that monitors..."
- "Create a daily workflow that..."

**Process**:

1. Decomposes the request into discrete steps, identifying what each does, its inputs/outputs, and external dependencies
2. Chooses step types -- selects the lightest type that fits each operation (script, shell, claude, query, http, transform, gate, fan-out, fan-in)
3. Designs the DAG with maximum parallelism
4. Generates step scripts following the step contract
5. Checks for required credentials and reminds the user to configure them
6. Registers the workflow graph
7. Verifies by displaying the structure, generating a Mermaid diagram, and suggesting a dry run

**Design guidelines applied**:
- One operation per step for easier debugging
- Transform steps as adapters between mismatched output/input shapes
- Gate steps for visible branching instead of embedded conditionals
- Descriptive step names (context keys)
- Failure planning with retry/skip/fail-fast policies

---

### workflow-debugger

Diagnoses failed, stuck, or unexpected workflow executions.

- **Model**: Sonnet
- **Tools**: Read, Bash, Grep, Glob

**Trigger patterns**:
- "My workflow failed..."
- "The workflow ran but the result was empty..."
- "My workflow has been running for 2 hours..."

**Process**:

1. Gets run details via `inspect` (most recent if no run ID given)
2. Identifies the failure point -- first step that failed, produced unexpected output, timed out, or is stuck
3. Examines the step script to understand intended behavior
4. Checks input context -- verifies data shape matches expectations
5. Tests the step independently by feeding recorded input context
6. Verifies credentials if the failure appears auth-related
7. Proposes a targeted fix

**Error classification**:

| Category | Examples |
|----------|----------|
| Auth issue | Expired token, missing credentials, insufficient permissions |
| Data shape mismatch | List vs dict, missing keys, NoneType errors |
| Missing context | Key absent because upstream skipped or namespaced differently |
| HTTP/API error | Rate limit (429), server error (500), connection timeout |
| Template substitution failure | Unresolved `{variable}` in command or prompt |
| Logic error | Bug in step Python code |
| Timeout | Step exceeded allowed duration |
| External service issue | Target service down or behaving unexpectedly |

**Reporting format**: Symptom, Root Cause (with evidence), Fix (exact changes), Prevention.

> **See also**: [Debugging Workflows Guide](../guides/debugging-workflows.md)

---

### workflow-optimizer

Analyzes workflow performance and reliability to recommend improvements.

- **Model**: Sonnet
- **Tools**: Read, Bash, Grep, Glob

**Trigger patterns**:
- "My workflow takes too long..."
- "The workflow fails about 30% of the time..."
- "Can you parallelize..."

**Process**:

1. Gathers execution history (last 20 runs) -- collects metrics on duration, per-step timing, failure rates, and data payload sizes
2. Identifies bottlenecks -- determines which steps dominate execution time and whether they are CPU-bound, I/O-bound, or waiting on external services
3. Analyzes failure patterns -- which steps fail most, transient vs persistent errors, time/volume correlations
4. Optimizes data flow -- identifies oversized payloads, redundant API calls, missing caching

**Recommendation categories**:

| Category | Description |
|----------|-------------|
| **Parallelism** | Convert sequential steps with no dependencies into parallel branches via fan-out/fan-in |
| **Caching** | Add caching for expensive API calls returning stable data, with suggested TTL |
| **Error handling** | Retry with backoff for transient failures, fallback paths for non-critical steps, circuit breakers |
| **Gate optimization** | Add early gates to skip unnecessary work; move cheap validation before expensive processing |
| **Step consolidation** | Merge always-together steps; split oversized steps into focused units |
| **Resource efficiency** | Batch API requests, add pagination, set timeouts based on observed durations |

Each recommendation includes what to change, expected impact, trade-offs, and concrete implementation details.

---

## Skills

Skills are knowledge packages loaded into context when relevant tasks arise. They provide specialized guidance without being autonomous agents.

### workflow-building

Loaded when building workflows, creating step scripts, or defining workflow steps.

- **Location**: `skills/workflow-building/SKILL.md`
- **References**: `step-contract.md`, `step-types.md`

**Contents**:
- Workflow structure (nodes, edges, graph storage)
- The step contract (JSON stdin, `run(context)` function, JSON stdout)
- Overview of all 9 step types with selection guidance
- Building process: define inputs/outputs, decompose into steps, choose types, define data flow, add edges, write scripts, register graph
- Context accumulation (outputs namespaced by step ID)
- Template substitution (`{variable}`, dot-path, array index syntax)
- Edge conditions (unconditional, gate-based, expression-based)
- Best practices (small steps, transform adapters, gate branching, independent testing, descriptive naming)

> **See also**: [Step Types Reference](step-types/index.md)

---

### workflow-debugging

Loaded when workflows fail, produce unexpected results, or have stuck runs.

- **Location**: `skills/workflow-debugging/SKILL.md`
- **References**: `error-patterns.md`

**Contents**:
- Inspection workflow (get run details, identify failure, examine step, classify error)
- Common failure patterns:
  - Authentication failures (401/403, expired tokens)
  - Data shape mismatches (TypeError, KeyError)
  - Missing context keys (namespacing issues)
  - Template substitution failures (unresolved placeholders)
  - HTTP errors (rate limits, server errors, timeouts)
  - Queue issues (stuck runs, unacknowledged messages)
- Diagnostic commands (`inspect`, `history`, `status`, `auth test`, direct SQLite queries)
- Fix strategies for each error category
- Prevention techniques (dry-run, credential validation, transform-based data validation, timeouts, independent testing, history monitoring)

---

## Hook

### SessionStart

Runs automatically when a Claude Code session starts with the liteflow plugin loaded.

- **Location**: `hooks/hooks.json`
- **Type**: Command
- **Timeout**: 5 seconds
- **Command**: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py status --quiet 2>/dev/null || true`

Performs a quiet health check of the liteflow system. Non-blocking: errors are suppressed and output is only shown if the system is unhealthy (missing databases, broken dependencies). The `|| true` ensures the hook never blocks session startup even if the status check fails.

---

## Cross-References

- [Step Types Reference](step-types/index.md) -- complete configuration for all 9 step types
- [Python Module Reference](modules/index.md) -- engine, graph, queue, state, steps, creds API docs
- [Installation Guide](../getting-started/installation.md) -- first-time setup walkthrough
- [Credential Management](../getting-started/credentials.md) -- storing and testing service tokens
- [Scheduling Guide](../getting-started/scheduling.md) -- recurring execution setup
- [Debugging Workflows](../guides/debugging-workflows.md) -- troubleshooting failed runs
- [Documentation Home](../index.md) -- docs index
