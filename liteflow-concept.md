# liteflow: Workflow Automation as a Claude Code Plugin

## Concept Overview

liteflow is a Claude Code plugin that turns Claude into a conversational workflow automation platform — an n8n-lite that requires zero infrastructure. The entire system runs on Python's standard library SQLite and a handful of pip-installable libraries that build on top of it. There is no server, no Docker, no web UI, no Node.js, no Redis. The user installs the plugin and has a running workflow automation engine immediately, with Claude serving simultaneously as the builder, the orchestrator, the debugger, and — uniquely — a first-class step type within workflows themselves.

The foundational thesis is that SQLite, already present on every developer's machine, can be reshaped by scripting libraries into every data infrastructure primitive a workflow engine needs: a graph database for workflow definitions, a task queue for execution, a relational store for state and history, a key-value store for credentials and configuration, and a full-text search index for workflow discovery. Claude provides the integration knowledge that replaces a static connector catalog, generating step scripts on the fly for any API or service.

### Relationship to Claude Code's Automation Stack

Claude Code has rapidly evolved an automation stack of its own: `/loop` for in-session polling, `/schedule` for recurring tasks, and — as of April 14, 2026 — **Routines** for persistent, cloud-hosted automations triggered by schedules, API calls, or GitHub events. These features, heavily inspired by the OpenClaw autonomous agent project, provide powerful triggering primitives but are inherently flat: a single prompt fires in response to a trigger.

liteflow fills the structural gap. **Routines tell Claude *when* to work. liteflow tells Claude *how* to work through complex, multi-step processes with state, branching, and history.** A Routine is a trigger. A liteflow workflow is a DAG with conditional branching, fan-out/fan-in, execution history, credential management, cross-plugin composition, and Claude reasoning steps. Routines provide the trigger infrastructure that liteflow deliberately does not build. liteflow provides the structured execution engine that Routines deliberately do not include.

### OpenClaw as Precedent and Validation

OpenClaw (formerly Clawdbot/Moltbot) is the open-source autonomous agent project that proved the category and directly inspired Anthropic's `/loop`, `/schedule`, and Routines features. OpenClaw's architectural decisions validate several of liteflow's core design choices:

- **"Everything is markdown and Python scripts"** — OpenClaw uses standalone Python scripts for skills, no framework, no database, no lock-in. This is exactly liteflow's step contract approach.
- **Three-tier memory** — OpenClaw's always-loaded essentials, daily context, and deep knowledge with semantic search map to liteflow's SQLite-backed state layers.
- **Autonomous workflows via cron** — OpenClaw proved that cron-triggered Claude Code sessions are a viable autonomy pattern. Routines are Anthropic's productization of this exact pattern.
- **Self-healing health checks** — OpenClaw's health-check agent that monitors system health, fixes routine issues, and escalates failures is a template liteflow should ship natively.

The key difference in scope: OpenClaw is a maximalist agent operating system — multi-channel messaging gateway, multi-agent routing, system-level access, a dedicated Mac Mini running 24/7. liteflow is a focused workflow engine designed as a Claude Code plugin that composes with Routines for triggering and runs within Claude Code sessions. Different users, different trade-offs, complementary ideas.

---

## Architecture

### Core Primitives

The entire system is built from four Python SQLite libraries composed together:

1. **`simple-graph-sqlite`** — Workflow definitions are graphs. Each workflow is a directed acyclic graph (DAG) stored as nodes (steps) and edges (transitions) in SQLite, using JSON properties on both. This gives us graph traversal via recursive CTEs, conditional branching via edge properties, and the full expressiveness of a graph database for workflow structure.

2. **`litequeue`** — Workflow execution is queue-driven. When a workflow runs, eligible steps are enqueued. A runner loop dequeues, executes, and enqueues successor steps based on graph edges and transition conditions. The queue provides visibility timeouts (for interrupted work), dead-letter handling (for failed steps), and message acknowledgment (for reliable execution).

3. **`sqlite-utils`** — Workflow state and execution history are structured records. A `runs` table tracks each workflow execution. A `step_runs` table tracks individual step executions within a run. A `workflows` table provides metadata and discovery. `sqlite-utils` handles schema inference, full-text search indexing, and the CLI/library duality that makes the data inspectable from both code and the command line.

4. **`sqlitedict`** — Configuration, credential storage, and per-workflow key-value state use a persistent dictionary interface backed by SQLite. This replaces both environment variables for secrets and JSON files for configuration, with the added benefit of transactional guarantees and thread-safe access.

### Database Files

liteflow uses multiple SQLite database files, each with a focused responsibility:

```
~/.liteflow/
├── workflows.db        # Workflow graph definitions (simple-graph-sqlite)
├── execution.db        # Run history, step results (sqlite-utils)
├── queue.db            # Active execution queue (litequeue)
├── credentials.db      # API tokens and secrets (sqlitedict, encrypted)
├── config.db           # Plugin configuration, user preferences (sqlitedict)
└── templates/          # Reusable step script templates
    ├── slack_post.py
    ├── github_issues.py
    ├── http_request.py
    └── ...
```

This separation is intentional. Each database can be backed up, inspected, or reset independently. The workflow definitions are portable — you can copy `workflows.db` to another machine and the structure is intact. Execution history can be pruned without affecting definitions. The credential store can be excluded from version control.

### The Runner

The runner is the execution engine — a Python script of approximately 150-200 lines that implements the core loop:

```
1. Pop a message from the queue (step_id + run_id)
2. Load the step definition from the workflow graph
3. Build execution context from prior step outputs in this run
4. Execute the step (dispatch by step type)
5. Record the result in the step_runs table
6. On success: evaluate outbound edges, enqueue successor steps
7. On failure: handle according to step's error policy
8. Repeat until queue is empty
```

The runner is invoked by Claude (or by a Routine, a hook, or a cron job) and executes to completion. It is not a long-running daemon. This is a deliberate design choice: no background process to manage, no PID files, no restart logic. The queue provides durability — if the runner crashes mid-execution, unacknowledged messages return to the queue and are retried on the next invocation.

### The Step Contract

Every step script, whether hand-written, Claude-generated, or loaded from a template, follows a uniform contract:

```python
import json
import sys

def run(context: dict) -> dict:
    """
    Receives accumulated context from prior steps.
    Returns an output dict to be merged into the run context.
    Raises an exception on failure.
    """
    # ... perform the step's work ...
    return {"result": "value"}

if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
```

This contract is deliberately minimal: JSON in via stdin, JSON out via stdout, exceptions signal failure. No framework dependency. No base class to inherit. No decorator magic. A step script is a standalone Python file that can be tested independently by piping JSON to it. The contract works equally well for scripts that use the standard library only, scripts that import pip-installed SDKs, and scripts that shell out to CLI tools.

---

## Step Types

Each node in the workflow graph has a `type` field that determines how the runner dispatches execution:

### `script`

Execute a Python script that follows the Step Contract. The script receives the accumulated run context as JSON on stdin and returns its output as JSON on stdout. This is the workhorse step type. Scripts can use any Python library, call any API, perform any computation.

```json
{
  "id": "fetch-issues",
  "type": "script",
  "script": "github_issues.py",
  "config": {
    "repo": "simonw/sqlite-utils",
    "labels": ["bug"],
    "since": "{last_run_timestamp}"
  }
}
```

### `shell`

Run a shell command. Input context is available as environment variables. stdout is captured as the step's output. Useful for `git`, `gh`, `curl`, filesystem operations, and wrapping CLI tools.

```json
{
  "id": "check-status",
  "type": "shell",
  "command": "gh pr list --author @me --json number,title,state"
}
```

### `claude`

Send a prompt to Claude with accumulated context from prior steps. This is the step type that makes liteflow fundamentally different from every other workflow engine. Claude can reason about intermediate results, make decisions, summarize data, generate code, draft messages, or classify inputs. The prompt is a template with `{variable}` placeholders filled from the run context.

```json
{
  "id": "triage",
  "type": "claude",
  "prompt": "Given these GitHub issues:\n{issues}\n\nClassify each as: critical, important, or minor. Return JSON array with id and severity.",
  "model": "default"
}
```

The `claude` step type enables workflows that include judgment, interpretation, and natural language processing as first-class operations — not bolted-on LLM integrations, but native workflow capabilities.

### `query`

Run a SQL query against any SQLite database. This lets workflows interact with liteflow's own databases (e.g., querying run history), with other plugin databases (e.g., a knowledge graph plugin), or with any SQLite database on the filesystem. Cross-plugin data composition for free.

```json
{
  "id": "last-run",
  "type": "query",
  "database": "execution.db",
  "sql": "SELECT MAX(started_at) as last_run FROM runs WHERE workflow_id = ?",
  "params": ["{workflow_id}"]
}
```

### `http`

Make an HTTP request. Uses Python's `urllib` from the standard library — no `requests` dependency required. Supports GET, POST, PUT, DELETE. Auto-injects authentication headers from the credential store. Handles JSON request/response serialization.

```json
{
  "id": "webhook",
  "type": "http",
  "method": "POST",
  "url": "https://hooks.slack.com/services/...",
  "headers": {"Content-Type": "application/json"},
  "body": {"text": "{summary}"}
}
```

### `transform`

Pure data transformation with no side effects. Evaluates a Python expression or applies a `jq`-style transformation to reshape data between steps. Useful for extracting fields, filtering arrays, reformatting dates, or preparing data for the next step.

```json
{
  "id": "extract-titles",
  "type": "transform",
  "expression": "[{'id': i['number'], 'title': i['title']} for i in context['issues']]"
}
```

### `gate`

A conditional branch point that routes execution down different paths based on evaluating a Python expression against the run context. The gate itself produces no output — it controls which outbound edges are followed.

```json
{
  "id": "has-critical",
  "type": "gate",
  "condition": "any(i['severity'] == 'critical' for i in context['triage'])"
}
```

Outbound edges from a gate carry `when_true` and `when_false` properties, enabling if/else branching in the workflow graph.

### `fan-out` / `fan-in`

Split execution across multiple items and collect results. `fan-out` takes an array from context and enqueues the next step N times, once per item, with each item injected into that step's context. `fan-in` waits for all parallel executions to complete and merges their outputs into a single array.

```json
{
  "id": "process-each-issue",
  "type": "fan-out",
  "over": "{issues}",
  "item_key": "issue"
}
```

This enables patterns like "for each PR, run the review step" or "for each file, run the analysis step" with automatic parallelism and result collection.

---

## Trigger Integration: liteflow + Claude Code's Automation Stack

liteflow deliberately does not build its own trigger infrastructure. Instead, it composes with Claude Code's graduated automation stack, where each layer serves a different purpose:

### Routines (Primary Trigger Mechanism)

Claude Code Routines, shipped April 14, 2026, are the primary trigger mechanism for liteflow workflows. A Routine is a saved configuration — a prompt, one or more repositories, and a set of connectors — that runs on Anthropic's cloud infrastructure. Routines support three trigger types that can be combined freely:

**Scheduled triggers** fire on a recurring cadence (hourly, nightly, weekly). A Routine's prompt invokes a liteflow workflow:

```
User: /flow schedule "dependency-audit" weekly
```

This creates a Routine on Anthropic's cloud with a weekly schedule. The Routine's prompt tells Claude to run `/flow run "dependency-audit"`. The workflow executes its full DAG — checking lockfiles, querying vulnerability databases, comparing versions, generating a report, posting to Slack — while the Routine simply provided the "when."

**GitHub triggers** fire on repository events (PR opened, push, issue created, workflow run completed, etc.) via webhook. This enables event-driven liteflow workflows:

```
User: /flow on-github pr-opened "pr-review"
```

This creates a Routine with a GitHub trigger subscribed to PR opened events. When a PR arrives, Claude runs the liteflow `pr-review` workflow, which fetches the diff, runs analysis, checks test coverage, and posts a structured review. The Routine provides real-time webhook delivery; liteflow provides the multi-step execution.

**API triggers** fire on an HTTP POST to a per-routine endpoint with a bearer token. This enables integration with external systems:

```
User: /flow on-api "incident-response"
```

This creates a Routine with an API endpoint. When Sentry, PagerDuty, or any external system POSTs an alert payload, the Routine fires and Claude runs the liteflow `incident-response` workflow with the alert data as context.

The key architectural benefit: **Routines handle cloud execution, durability, authentication, and event delivery. liteflow handles multi-step orchestration, conditional branching, state tracking, and execution history.** Neither needs to build what the other provides.

### `/loop` (Development and Monitoring)

`/loop` runs a prompt or slash command on a recurring interval within the current session. It's session-scoped — it dies when the terminal closes. In liteflow's context, `/loop` serves two purposes:

**Workflow development**: Rapid iteration on a workflow under construction:

```
/loop 30s /flow run "my-workflow" --dry-run
```

Modify a step script, see the results 30 seconds later, iterate. When the workflow works, graduate it to a Routine.

**Live monitoring**: Watch a running process or system during an active session:

```
/loop 5m /flow run "deploy-health-check"
```

Poll a deployment every 5 minutes, with Claude interpreting the results and alerting if something looks wrong. This is the "babysit a deploy" pattern that OpenClaw popularized.

### Claude Code Hooks (Session-Lifecycle Triggers)

Hooks trigger workflows at specific points in the Claude Code session lifecycle:

- **SessionStart** — Run a "load context" or "morning briefing" workflow when Claude Code starts
- **PostToolUse** — Trigger a "lint and test" workflow after file edits
- **Stop** — Run a "session summary" workflow when a session ends, capturing what was accomplished

Hook configuration in the plugin:

```yaml
# hooks/session-start.sh
#!/bin/bash
cd ~/.liteflow && python runner.py --workflow "session-init" --trigger hook
```

Hooks are local and session-scoped. They complement Routines (cloud, persistent) for different use cases.

### Manual Invocation

The simplest trigger: `/flow run "workflow-name"`. The user invokes the workflow directly. Always available, requires no configuration.

### Chained Workflows

A workflow's final step can enqueue another workflow. Workflows triggering workflows, with data passed between them via the run context. This enables meta-workflows and pipeline composition.

---

## Credential Management

### The Credential Store

API tokens, webhook URLs, and other secrets are stored in `credentials.db` using `sqlitedict` with an encryption layer. The store maps service names to credential bundles:

```python
# Internal representation
{
    "slack": {
        "type": "webhook",
        "url": "https://hooks.slack.com/services/T.../B.../xxx",
        "added_at": "2025-01-15T10:30:00Z"
    },
    "github": {
        "type": "token",
        "token": "ghp_xxxxxxxxxxxx",
        "scopes": ["repo", "read:org"],
        "added_at": "2025-01-15T10:32:00Z"
    },
    "google-sheets": {
        "type": "service-account",
        "credentials_json": "{...}",
        "added_at": "2025-01-15T10:35:00Z"
    }
}
```

### The `/flow auth` Command

Credential setup happens conversationally through a slash command:

```
User: /flow auth slack
Claude: I can set up Slack access using either:
        1. A webhook URL (simplest — for posting to a specific channel)
        2. A bot token (more flexible — for reading, posting, managing channels)
        Which do you prefer?
User: webhook
Claude: Paste your Slack webhook URL. I'll store it encrypted 
        in the credential store.
User: https://hooks.slack.com/services/T.../B.../xxx
Claude: Stored. I'll use this for any workflow step that posts to Slack.
        You can test it with: /flow test-auth slack
```

### Auth in Step Scripts

The helpers library provides transparent credential injection:

```python
from liteflow.helpers import SecureStore, HTTPStep

store = SecureStore()
http = HTTPStep(auth_store=store)

# Auto-injects the stored Slack webhook URL
http.post("slack", data={"text": "Hello from liteflow"})

# Auto-injects the GitHub token as Bearer header
http.get("github", endpoint="/repos/owner/repo/issues")
```

For SDK-based steps, Claude generates the appropriate credential loading:

```python
from liteflow.helpers import SecureStore
from slack_sdk import WebClient

store = SecureStore()
client = WebClient(token=store.get_token("slack"))
client.chat_postMessage(channel="#bugs", text=message)
```

---

## The Helpers Library

A thin utility module (~200 lines) that ships with the plugin in `lib/`. No pip install required. It smooths the most common patterns without imposing a framework.

### StepContext

Wraps the raw context dict with convenience methods:

```python
class StepContext:
    def __init__(self, raw: dict):
        self.data = raw
    
    def get(self, dotpath: str, default=None):
        """Dot-path access: ctx.get('github.issues.0.title')"""
        ...
    
    def require(self, *keys):
        """Raise a clear, descriptive error if required keys are missing."""
        ...
    
    def merge(self, output: dict):
        """Merge step output into context, namespaced by step_id."""
        ...
```

### SecureStore

SQLite-backed credential storage with basic encryption:

```python
class SecureStore:
    def __init__(self, db_path="~/.liteflow/credentials.db"):
        ...
    
    def get_token(self, service: str) -> str:
        """Retrieve stored API token for a service."""
        ...
    
    def set_token(self, service: str, token: str, metadata: dict = None):
        """Store a token with optional metadata (type, scopes, etc.)."""
        ...
    
    def list_services(self) -> list:
        """List all configured services."""
        ...
    
    def remove(self, service: str):
        """Delete stored credentials for a service."""
        ...
```

### HTTPStep

Minimal HTTP client built on `urllib` — zero external dependencies:

```python
class HTTPStep:
    def __init__(self, auth_store: SecureStore = None):
        self.auth = auth_store
    
    def get(self, url_or_service: str, endpoint: str = "", 
            headers: dict = None, params: dict = None) -> dict:
        """GET request. If url_or_service matches a stored credential,
        auto-injects auth headers and resolves base URL."""
        ...
    
    def post(self, url_or_service: str, data: dict = None, 
             endpoint: str = "", headers: dict = None) -> dict:
        """POST request with JSON body."""
        ...
    
    def put(self, ...): ...
    def delete(self, ...): ...
```

### RunLogger

Structured logging that writes to both console and the execution database:

```python
class RunLogger:
    def __init__(self, run_id: str, step_id: str):
        ...
    
    def info(self, message: str, data: dict = None): ...
    def warn(self, message: str, data: dict = None): ...
    def error(self, message: str, data: dict = None): ...
```

---

## Dependency Management

### The Zero-Install Core

The core plugin runs on nothing but Python's standard library. `sqlite3`, `json`, `urllib`, `os`, `subprocess`, `hashlib`, `datetime`, `pathlib` — all stdlib. This means the plugin works immediately on any machine with Python 3.7+.

The SQLite libraries (`sqlite-utils`, `simple-graph-sqlite`, `litequeue`, `sqlitedict`) are pip-installed on first use via lazy installation. This happens transparently — the user runs a workflow and the plugin detects missing dependencies and installs them silently.

### Lazy Installation Pattern

```python
import subprocess
import importlib

def ensure_deps(*packages):
    """Install missing packages silently on first use."""
    for pkg in packages:
        module_name = pkg.replace("-", "_")
        try:
            importlib.import_module(module_name)
        except ImportError:
            subprocess.check_call(
                ["pip", "install", pkg, "--break-system-packages", "-q"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            importlib.import_module(module_name)

# Called at plugin initialization
ensure_deps("sqlite-utils", "simple-graph-sqlite", "litequeue", "sqlitedict")
```

Alternatively, a `/flow setup` command performs explicit installation with user-visible feedback.

### Optional SDK Tier

Individual service SDKs are installed only when a workflow first needs them. Claude detects whether an SDK is available and either uses it (for richer functionality) or falls back to raw HTTP via `urllib` (for zero-dependency operation).

```python
OPTIONAL_SDKS = {
    "github": "PyGithub",
    "slack": "slack_sdk",
    "google": "google-api-python-client",
    "notion": "notion-client",
    "linear": "linear-sdk",
    "stripe": "stripe",
    "jira": "jira",
    "twilio": "twilio",
    "sendgrid": "sendgrid",
    "aws": "boto3",
}

def ensure_sdk(service: str):
    """Install an SDK for a specific service if not present."""
    if service in OPTIONAL_SDKS:
        ensure_deps(OPTIONAL_SDKS[service])
```

---

## Claude as the Connector Library

### The Reframe

n8n ships 400+ pre-built nodes because a human would otherwise have to figure out each API. In liteflow, Claude already knows every major API — authentication patterns, endpoint structures, rate limits, error codes, data formats. When a user says "add a step that posts to Slack," Claude doesn't look up a pre-built connector. It generates the connector script on the fly, using the right SDK if installed or falling back to raw HTTP.

This is more powerful than a static library because:

- **Infinite flexibility**: n8n's Slack node supports a fixed set of operations. Claude can generate a script for any Slack API operation, with any data transformation.
- **Context-aware generation**: Claude tailors the script to the specific workflow context — the data shape from prior steps, the user's preferred error handling, the available credentials.
- **Self-healing**: When an API changes, Claude generates updated scripts without waiting for a library maintainer to publish a fix.
- **Long-tail coverage**: n8n can't have nodes for every API. Claude can generate connectors for any service with a documented API, including internal company APIs.

### SDK Detection and Fallback

When generating a step script, Claude checks whether the relevant SDK is installed:

1. **SDK available**: Generate a script using the SDK's idiomatic patterns (e.g., `slack_sdk.WebClient` for Slack)
2. **SDK not available**: Generate a script using `urllib` with raw HTTP calls to the service's REST API
3. **SDK install offered**: Claude can offer to install the SDK for richer functionality: "I can use the Slack webhook URL with no extra dependencies, or I can install `slack_sdk` for full channel management. Want me to install it?"

### The Three-Tier Integration Model

**Tier 1: Zero-dependency (stdlib only)**
Raw HTTP via `urllib`. Works immediately. Supports any REST API. Limited to simple request/response patterns. Auth via manual header injection from credential store.

**Tier 2: Lightweight helpers (ships with plugin)**
The `HTTPStep` helper provides auto-auth injection, response parsing, basic retry logic, and error formatting. Still no pip install required.

**Tier 3: Full SDK (pip installed on demand)**
Official service SDKs (`PyGithub`, `slack_sdk`, `notion-client`, etc.) provide the richest API coverage, proper pagination, webhook handling, and type-safe interfaces. Installed lazily when first needed.

---

## Claude's Role

Claude serves multiple roles in the liteflow system, each qualitatively different from what a traditional workflow engine provides:

### Workflow Builder

When a user describes a workflow in natural language, Claude constructs the graph, generates step scripts, configures edges with transition conditions, and stores everything in the workflow database. Claude infers intermediate steps, suggests error handling strategies, and generates appropriate step scripts using its knowledge of APIs and services.

```
User: "Build me a workflow that monitors my GitHub repos for 
       new issues labeled 'urgent', posts them to #incidents in 
       Slack, and creates a Linear ticket for each one."

Claude constructs:
  1. A "fetch-issues" script step (GitHub API, filtered by label)
  2. A "filter-new" query step (compare against last run in execution.db)
  3. A "fan-out" over new issues
  4. A "post-slack" script step (Slack webhook or SDK)
  5. A "create-ticket" script step (Linear API)
  6. A "fan-in" to collect results
  7. Edge connections with appropriate data flow
  8. The scripts themselves, following the Step Contract
```

### Step Type

The `claude` step type makes Claude a participant in workflow execution, not just the builder. Workflows can include Claude reasoning as an intermediate processing step — classification, summarization, decision-making, natural language generation, code review.

This is liteflow's most distinctive capability. No other lightweight workflow engine has "reason about this with an LLM" as a native step type. Use cases include:

- **Triage**: Classify incoming items by severity, topic, or priority
- **Summarization**: Condense data from prior steps into a readable summary
- **Decision-making**: Choose which branch to follow based on judgment, not just conditionals
- **Content generation**: Draft messages, reports, PR descriptions, release notes
- **Code analysis**: Review diffs, suggest improvements, identify patterns
- **Data interpretation**: Explain anomalies, identify trends, provide context

### Debugger

When a workflow fails, Claude can inspect the execution history (querying `execution.db`), examine the failed step's input context, read the error message, look at the step script, and explain what went wrong in plain English. Claude can suggest fixes, modify the step script, and re-run the failed step.

```
User: /flow inspect last
Claude: The "post-slack" step failed at 2025-01-15 10:45:23.
        Error: HTTP 403 Forbidden.
        
        Looking at the request, the webhook URL is returning 
        a 403. This usually means the webhook has been revoked 
        or the channel was deleted. 
        
        Want me to re-authenticate Slack with /flow auth slack?
```

### Optimizer

Over time, Claude can analyze workflow run history and suggest improvements: steps that consistently take too long, steps that frequently fail, redundant steps, opportunities for parallelization, or better error handling patterns.

---

## Slash Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `/flow new "<n>"` | Create a new workflow, optionally from natural language description |
| `/flow list` | List all workflows with last run status |
| `/flow show <n>` | Display workflow structure as a graph description |
| `/flow run <n>` | Execute a workflow |
| `/flow run <n> --dry-run` | Simulate execution without side effects |
| `/flow history [name]` | Show execution history |
| `/flow inspect <run-id>` | Detailed inspection of a specific run |
| `/flow delete <n>` | Delete a workflow definition |

### Building Commands

| Command | Description |
|---------|-------------|
| `/flow build` | Conversational workflow builder — Claude asks questions and constructs the workflow interactively |
| `/flow add-step <workflow> "<description>"` | Add a step to an existing workflow |
| `/flow connect <step-a> <step-b>` | Create an edge between steps |
| `/flow edit-step <workflow> <step-id>` | Modify a step's configuration or script |
| `/flow remove-step <workflow> <step-id>` | Remove a step and reconnect edges |
| `/flow visualize <workflow>` | Generate a Mermaid diagram of the workflow graph |

### Trigger Commands

| Command | Description |
|---------|-------------|
| `/flow schedule <n> <cadence>` | Create a Routine with a scheduled trigger (hourly/nightly/weekly) |
| `/flow on-github <event> <n>` | Create a Routine with a GitHub event trigger |
| `/flow on-api <n>` | Create a Routine with an API trigger, returns endpoint URL |
| `/flow triggers [name]` | List all triggers (Routines, hooks) for a workflow |
| `/flow triggers remove <id>` | Remove a trigger |

### Credential Commands

| Command | Description |
|---------|-------------|
| `/flow auth <service>` | Interactively configure credentials for a service |
| `/flow auth list` | List configured services |
| `/flow auth test <service>` | Test stored credentials |
| `/flow auth remove <service>` | Remove stored credentials |

### Template Commands

| Command | Description |
|---------|-------------|
| `/flow templates` | List available workflow templates |
| `/flow use <template>` | Create a workflow from a template |
| `/flow save-step <step-id> "<n>"` | Save a step as a reusable template |
| `/flow share <workflow>` | Export a workflow as a portable template bundle |
| `/flow import <path>` | Import a workflow template bundle |

### Administration Commands

| Command | Description |
|---------|-------------|
| `/flow setup` | Install/update dependencies, initialize databases |
| `/flow status` | Show system status (installed deps, DB sizes, queued items) |
| `/flow health` | Run the self-health-check workflow |
| `/flow prune [--older-than 30d]` | Clean up old execution history |
| `/flow export <workflow> <path>` | Export a workflow definition to JSON |
| `/flow reset` | Reset all databases (with confirmation) |

---

## Template System

### Pre-Built Templates

The plugin ships with workflow templates for common developer patterns:

#### Morning Briefing

Check calendar (via Google API or local calendar file), git status across repos, pending PR reviews, open issues assigned to user. Claude summarizes into a daily briefing. Designed to be triggered by a nightly Routine so the briefing is ready when you sit down.

#### PR Review Prep

Fetch a PR's diff, analyze changes with Claude, check test coverage, identify areas of concern, draft review notes. Input: PR URL or number. Designed to be triggered by a GitHub Routine on PR opened events.

#### Dependency Audit

Walk lockfiles (requirements.txt, package.json, Cargo.lock), check for known vulnerabilities (via GitHub Advisory Database API or OSV), check for available updates, generate a report. Designed for a weekly Routine.

#### Release Prep

Run tests, verify changelog has been updated, check version bumps, validate that all PRs since last release are documented, generate release notes with Claude.

#### Research Digest

Check a list of configured sources (GitHub repos for new releases, RSS feeds, specific web pages), summarize what's new using Claude, append to a research dossier.

#### Incident Response

Triggered by an API Routine receiving a Sentry/PagerDuty webhook. Post to Slack, create a Linear ticket, start a timer, check again after interval, post resolution when recovered.

#### liteflow Health (Self-Health-Check Meta-Workflow)

Inspired directly by OpenClaw's autonomous health-check agent, this is a meta-workflow that monitors liteflow itself. It runs on a scheduled Routine (e.g., daily) and performs:

- **Database integrity checks** — Run `PRAGMA integrity_check` on every liteflow SQLite database (`workflows.db`, `execution.db`, `queue.db`, `credentials.db`, `config.db`). Report any corruption immediately.
- **Stale run detection** — Query `execution.db` for runs stuck in `running` status for longer than a configurable threshold. These indicate runner crashes or interrupted executions. Offer to re-queue or mark as failed.
- **Dead letter queue inspection** — Check `queue.db` for messages in the dead letter queue. Claude summarizes what failed and why, and offers to retry or discard.
- **Credential validation** — For each stored credential, make a lightweight authenticated request to verify the token is still valid (e.g., GitHub `/user`, Slack `/auth.test`). Flag expired or revoked tokens and prompt for re-authentication.
- **Execution history pruning** — If `execution.db` has grown beyond a configurable size or age threshold, offer to prune old runs while preserving the most recent N runs per workflow.
- **Template staleness** — Check if any step templates reference APIs or patterns that Claude recognizes as outdated. Offer to regenerate.
- **Disk usage report** — Report total size of all liteflow databases and the templates directory.
- **Routine health** — Verify that all configured Routines are still active and their triggers are functioning. Report any Routines that have silently stopped firing.
- **Status summary** — Claude compiles all findings into a brief health report. If everything is healthy, the report is a single line ("liteflow: all systems nominal, 5 workflows, 142 runs, 3 credentials valid"). If issues are found, Claude provides actionable recommendations.

Following OpenClaw's "silent success" model, the health check only sends notifications (e.g., Slack message, console output) when something is wrong or was auto-repaired. Healthy runs produce no noise.

This template embodies liteflow's design philosophy: the workflow engine is itself managed by a workflow. The infrastructure is self-describing, self-monitoring, and — where safe — self-healing.

### Template Structure

A template is a directory containing the workflow graph definition, step scripts, and a manifest:

```
templates/morning-briefing/
├── manifest.json          # Name, description, required credentials, variables
├── workflow.json           # Graph definition (nodes + edges)
├── steps/
│   ├── check_calendar.py
│   ├── check_github.py
│   ├── check_prs.py
│   └── summarize.py        # Claude step prompt template
└── README.md               # Human-readable description and customization guide
```

### Emergent Template Library

Beyond pre-built templates, liteflow accumulates templates through use. The first time Claude generates a "post to Slack" step, that script is saved as a reusable template. Over time, the user builds a personal library of proven step scripts. The `/flow save-step` and `/flow share` commands formalize this: save individual steps or entire workflows as portable template bundles.

This creates a potential community distribution vector: users share template bundles, effectively building a crowd-sourced connector library. The difference from n8n's static nodes is that these templates are full Python scripts — inspectable, modifiable, and customizable without leaving the plugin.

---

## Cross-Plugin Composition

### The SQLite Advantage

Because every Claude Code plugin that uses SQLite stores data in inspectable database files on the local filesystem, liteflow workflows can query and interact with other plugins' data. This is composition that would be impossible if plugins used different storage backends or ran in separate containers.

### Example Compositions

**liteflow + Knowledge Graph Plugin**
A workflow step queries the knowledge graph to find all concepts related to the current project, then uses that context to enrich a Claude reasoning step.

**liteflow + Decision Journal Plugin**
A workflow records the outcome of an automated decision in the decision journal, with the full execution context as supporting evidence. Later workflows can query past decisions to inform new ones.

**liteflow + Codebase Archaeology Plugin**
A workflow triggers re-indexing of a codebase after detecting changes, then queries the index to identify which modules were affected and who should review them.

### The `query` Step Type as Glue

The `query` step type accepts any SQLite database path, enabling cross-plugin joins:

```json
{
  "id": "find-related-decisions",
  "type": "query",
  "database": "~/.claude-plugins/decision-journal/decisions.db",
  "sql": "SELECT * FROM decisions WHERE topic LIKE ? AND created_at > ?",
  "params": ["%{project_name}%", "{thirty_days_ago}"]
}
```

---

## Plugin File Structure

```
liteflow/
├── plugin.toml                 # Plugin metadata, slash command declarations
├── setup.sh                    # Dependency installation, database initialization
│
├── lib/
│   ├── __init__.py
│   ├── engine.py               # The runner loop (~150-200 lines)
│   ├── steps.py                # Step type dispatchers
│   ├── graph.py                # simple-graph-sqlite wrapper
│   ├── state.py                # sqlite-utils run/step tracking
│   ├── queue.py                # litequeue wrapper
│   ├── helpers.py              # StepContext, SecureStore, HTTPStep, RunLogger
│   ├── deps.py                 # Lazy dependency installer
│   ├── creds.py                # Credential management
│   └── routines.py             # Routine creation helpers (wraps /schedule CLI)
│
├── commands/
│   ├── flow-new.md             # Slash command: create workflow
│   ├── flow-build.md           # Slash command: conversational builder
│   ├── flow-run.md             # Slash command: execute workflow
│   ├── flow-list.md            # Slash command: list workflows
│   ├── flow-show.md            # Slash command: display workflow structure
│   ├── flow-history.md         # Slash command: execution history
│   ├── flow-inspect.md         # Slash command: inspect a run
│   ├── flow-auth.md            # Slash command: credential management
│   ├── flow-schedule.md        # Slash command: create Routine with schedule trigger
│   ├── flow-on-github.md       # Slash command: create Routine with GitHub trigger
│   ├── flow-on-api.md          # Slash command: create Routine with API trigger
│   ├── flow-templates.md       # Slash command: template management
│   ├── flow-health.md          # Slash command: run self-health-check
│   ├── flow-visualize.md       # Slash command: Mermaid diagram generation
│   ├── flow-setup.md           # Slash command: installation and setup
│   └── flow-status.md          # Slash command: system status
│
├── agents/
│   ├── workflow-builder.md     # Subagent: conversational workflow construction
│   ├── workflow-debugger.md    # Subagent: failure analysis and repair
│   └── workflow-optimizer.md   # Subagent: performance analysis and suggestions
│
├── hooks/
│   ├── session-start.sh        # Optional: trigger workflows on session start
│   └── post-tool-use.sh        # Optional: trigger workflows after tool use
│
├── templates/
│   ├── morning-briefing/
│   ├── pr-review/
│   ├── dependency-audit/
│   ├── release-prep/
│   ├── research-digest/
│   ├── incident-response/
│   └── liteflow-health/        # Self-health-check meta-workflow
│
├── SKILL.md                    # Teaches Claude how to build and manage workflows
└── README.md                   # User-facing documentation
```

### Estimated Code Volume

| Component | Approximate Lines |
|-----------|------------------|
| `engine.py` (runner loop) | 150-200 |
| `steps.py` (step dispatchers) | 150-200 |
| `graph.py` (graph wrapper) | 80-120 |
| `state.py` (run tracking) | 100-150 |
| `queue.py` (queue wrapper) | 50-80 |
| `helpers.py` (utilities) | 200-250 |
| `deps.py` (lazy installer) | 30-50 |
| `creds.py` (credentials) | 80-120 |
| `routines.py` (Routine helpers) | 60-100 |
| **Total Python** | **~900-1270** |

The entire runtime is under 1,300 lines of Python. The complexity lives in the SKILL.md (teaching Claude how to use the system) and the slash command definitions (providing user entry points), not in the runtime code.

---

## Design Principles

### 1. Zero Infrastructure

The plugin works on any machine with Python 3.7+ and requires no external services, no servers, no containers. SQLite provides every data primitive. The standard library provides HTTP, JSON, subprocess execution, and filesystem operations. Cloud execution is delegated to Routines running on Anthropic's infrastructure.

### 2. Inspect Everything

Every piece of state is in a SQLite database that can be opened with any SQLite client. Workflow definitions are JSON in a graph database. Execution history is queryable with SQL. Step scripts are plain Python files. There is no opaque binary state, no proprietary format, no "check the web UI."

### 3. Claude as Integral, Not Bolted-On

Claude isn't an add-on integration — it's the builder, the debugger, the optimizer, and a step type. The system is designed around the assumption that an LLM is present and capable, which enables design choices (conversational construction, generated connectors, reasoning steps) that are impossible in traditional workflow engines.

### 4. Compose, Don't Compete

liteflow does not build trigger infrastructure — it composes with Routines. It does not build a connector catalog — it composes with Claude's API knowledge. It does not build a visual editor — it composes with Claude's conversational interface. Each component does one thing well.

### 5. Emergent Over Pre-Built

The connector library isn't shipped — it emerges through use. Claude generates step scripts, which become templates, which become a personal library, which can be shared as a community catalog. The system gets more capable the more you use it.

### 6. Graceful Degradation

Every integration works at three tiers: zero-dependency (stdlib HTTP), lightweight helpers (ships with plugin), and full SDK (pip installed on demand). The user's first workflow runs immediately. Richer capabilities unlock as SDKs are installed. Nothing requires upfront setup.

### 7. Self-Monitoring

Following OpenClaw's lead, liteflow includes a self-health-check workflow as a first-class template. The system monitors its own integrity, prunes its own history, validates its own credentials, and reports its own status. The workflow engine is managed by a workflow.

---

## Comparison: liteflow vs. n8n vs. Zapier vs. OpenClaw

| Dimension | liteflow | n8n | Zapier | OpenClaw |
|-----------|----------|-----|--------|----------|
| **Infrastructure** | None (Python + SQLite + Routines) | Node.js server + database | Cloud SaaS | Dedicated machine (Mac Mini) |
| **UI** | Claude conversation | Web visual builder | Web visual builder | Chat apps (WhatsApp, Telegram, etc.) |
| **Connector library** | Claude-generated + emergent | 400+ pre-built nodes | 8000+ connectors | Skills as Python/MD scripts |
| **LLM integration** | Native step type | Plugin/HTTP node | AI action node | Core architecture (LLM-native) |
| **Trigger types** | Routines (schedule/API/GitHub), hooks, manual | Webhooks, cron, polling | Webhooks, polling, schedule | Cron, webhooks, chat messages |
| **Multi-step workflows** | DAG with branching, fan-out/in | Visual DAG | Linear + branching | Agent pipeline (less structured) |
| **Execution history** | SQLite (queryable with SQL) | Database-backed | Cloud-managed | Logs + memory files |
| **Persistence** | SQLite files on disk | PostgreSQL/SQLite | Cloud | File-based memory |
| **Cost** | Free (plugin) + Routine usage | Free (self-hosted) / Paid | Paid subscription | Free (self-hosted) + API costs |
| **Setup time** | < 1 minute | 15-30 minutes | 5 minutes | 30-60 minutes |
| **Cloud execution** | Via Routines (Anthropic) | Self-hosted or cloud | Native | Self-hosted only |
| **Self-healing** | Health-check template | Manual monitoring | Managed | Autonomous health checks |
| **Target user** | Developers in Claude Code | Technical / DevOps | Non-technical | Power users / developers |
| **Offline operation** | Full (except HTTP steps) | Requires server | Requires internet | Full (local machine) |

### Where liteflow Wins

- Zero infrastructure overhead with cloud execution via Routines
- Claude as a native reasoning step within workflows
- Conversational workflow construction
- Cross-plugin data composition via SQLite
- Full Python expressiveness in every step
- Structured execution history queryable with SQL
- Portable SQLite-file-based state

### Where Others Win

- **n8n/Zapier**: Visual graph editing UI, mature pre-built connectors, OAuth flow handling, production monitoring dashboards, team collaboration
- **OpenClaw**: Always-on 24/7 agent, multi-channel messaging, multi-agent orchestration, system-level access, deeper autonomy

### liteflow's Niche

liteflow targets a specific and underserved niche: **developers who live in Claude Code and want structured, repeatable, inspectable workflow automation without adding infrastructure**. The developer who currently writes one-off Python scripts and bash aliases to glue their tools together — and who now has Routines for triggering but needs a structured execution layer between "a prompt fires" and "the work gets done."

The relationship to Routines is symbiotic, not competitive. A Routine is a trigger with a prompt. A liteflow workflow is a multi-step execution plan with branching, state, and history. The Routine fires the prompt. The prompt runs the workflow. The workflow does the work.

---

## Future Directions

### Community Template Registry

A GitHub repository or lightweight registry where users publish workflow template bundles. Install with `/flow import github:username/template-name`.

### Visual Graph Output

Generate interactive HTML workflow visualizations (Mermaid, D3, or SVG) that show execution status, timing, and data flow. Rendered as Claude Code artifacts.

### Workflow Versioning

Track workflow definition changes over time using SQLite's built-in capabilities. Compare versions, roll back to previous definitions, see what changed between runs.

### Multi-Workflow Orchestration

A meta-workflow layer that manages dependencies between workflows — "run the data sync workflow, then the report workflow, but only if the sync produced new data."

### MCP Server Mode

Expose liteflow's workflow execution capabilities as an MCP server, allowing other tools and agents to trigger and monitor workflows programmatically.

### Plugin Interop Protocol

A standardized way for Claude Code plugins to declare their SQLite schemas and expose queryable surfaces, enabling richer cross-plugin composition beyond ad-hoc SQL queries.

### Routine Composition Patterns

As Routines mature beyond research preview, explore deeper integration patterns: Routines that pass structured payloads to liteflow workflows, Routines that receive workflow completion callbacks, and Routines that chain multiple liteflow workflows in response to a single trigger.

### Expanded Trigger Surface

As Anthropic expands Routine triggers beyond GitHub (noted as planned in the Routines announcement), liteflow's trigger commands should track that expansion — `/flow on-linear`, `/flow on-sentry`, `/flow on-slack`, etc. — each creating a Routine with the appropriate event subscription.
