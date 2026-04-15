# liteflow

Workflow automation as a Claude Code plugin. An n8n-lite that requires zero infrastructure.

## What is liteflow?

liteflow turns Claude into a conversational workflow automation platform. The entire system runs on Python's standard library SQLite and a handful of pip-installable libraries. There is no server, no Docker, no web UI, no Node.js, no Redis. Install the plugin and you have a running workflow automation engine immediately.

Claude serves simultaneously as the **builder**, the **orchestrator**, the **debugger**, and — uniquely — a **first-class step type** within workflows.

## Quick Start

```
# 1. Install the plugin (option A: direct path)
claude --plugin-dir /path/to/liteflow

# 1. Install the plugin (option B: dev marketplace)
/plugin marketplace add /path/to/liteflow
/plugin install liteflow@liteflow-dev

# 2. Initialize
/liteflow:flow-setup

# 3. Build your first workflow
/liteflow:flow-build

# 4. Or create from a template
/liteflow:flow-templates morning-briefing
```

## Architecture

liteflow is built on four SQLite libraries composed together:

| Library | Role |
|---------|------|
| `simple-graph-sqlite` | Workflow definitions as directed acyclic graphs |
| `litequeue` | Execution queue with visibility timeouts and dead-letter handling |
| `sqlite-utils` | Run history and step results as structured records |
| `sqlitedict` | Credential storage and configuration |

### Database Files

```
~/.liteflow/
├── workflows.db        # Workflow graph definitions
├── execution.db        # Run history, step results
├── queue.db            # Active execution queue
├── credentials.db      # API tokens (encrypted)
├── config.db           # Plugin configuration
└── steps/              # Step scripts organized by workflow
```

## Step Types

| Type | Purpose | Example |
|------|---------|---------|
| `script` | Run a Python script (step contract) | API calls, data processing |
| `shell` | Run a shell command or script file | `gh`, `git`, `curl`, `.sh` scripts |
| `claude` | LLM reasoning step (supports all CLI flags) | Classification, summarization |
| `query` | SQL against any SQLite DB | Cross-plugin data queries |
| `http` | HTTP request (zero deps) | Webhooks, REST APIs |
| `transform` | Pure data transformation | Reshape, filter, extract |
| `gate` | Conditional branch point | If/else routing |
| `fan-out` | Split array into parallel executions | Process each item independently |
| `fan-in` | Collect parallel results | Merge fan-out outputs into one array |

## The Step Contract

Every step script follows a minimal contract — JSON in, JSON out:

```python
import json, sys

def run(context: dict) -> dict:
    # Your logic here
    return {"result": "value"}

if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
```

## Commands

### Core
| Command | Description |
|---------|-------------|
| `/liteflow:flow-new` | Create a workflow from description |
| `/liteflow:flow-build` | Conversational workflow builder |
| `/liteflow:flow-list` | List all workflows |
| `/liteflow:flow-show` | Display workflow structure + Mermaid diagram |
| `/liteflow:flow-run` | Execute a workflow |
| `/liteflow:flow-history` | Show execution history |
| `/liteflow:flow-inspect` | Inspect a specific run |
| `/liteflow:flow-edit` | Modify workflow steps and connections |
| `/liteflow:flow-visualize` | Generate Mermaid diagram |

### Credentials
| Command | Description |
|---------|-------------|
| `/liteflow:flow-auth` | Add, list, test, or remove service credentials |

### Triggers
| Command | Description |
|---------|-------------|
| `/liteflow:flow-schedule` | Create a scheduled Routine |
| `/liteflow:flow-on-github` | Create a GitHub event Routine |
| `/liteflow:flow-on-api` | Create an API-triggered Routine |

### Templates
| Command | Description |
|---------|-------------|
| `/liteflow:flow-templates` | List and create from templates |

### Administration
| Command | Description |
|---------|-------------|
| `/liteflow:flow-setup` | Install dependencies, initialize databases |
| `/liteflow:flow-status` | System status dashboard |

## Templates

liteflow ships with workflow templates for common patterns:

- **Morning Briefing** — GitHub activity, pending PRs, open issues summarized by Claude
- **PR Review** — Fetch diff, analyze changes, check tests, generate review
- **Health Check** — Database integrity, stale runs, credential validation, disk usage

## Trigger Integration

liteflow composes with Claude Code's full automation stack:

| Method | Persistence | Runs on | Best for |
|--------|------------|---------|----------|
| **Manual** (`/liteflow:flow-run`) | None | Local | One-off execution |
| **`/loop`** | Session-scoped | Local | Polling, development iteration |
| **In-session cron** (`CronCreate`) | Session-scoped | Local | Recurring checks during a session |
| **Desktop scheduled tasks** | Persistent | Local | Daily/weekly automations with local file access |
| **Routines** | Persistent | Cloud | Schedule, GitHub events, or API triggers |
| **Hooks** | Persistent | Local | Session lifecycle (SessionStart, PostToolUse, Stop) |
| **One-shot reminders** | Session-scoped | Local | "Run this workflow in 30 minutes" |
| **Chained workflows** | Per-run | Local | Workflows triggering other workflows |

Use `/liteflow:flow-schedule` to set up any scheduled trigger. A `loop.md` template is included at `templates/loop.md` — copy it to `.claude/loop.md` to make bare `/loop` run liteflow health checks automatically.

## Dependencies

### Zero-Install Core
The plugin runs on Python's standard library. SQLite libraries are installed automatically on first use:
- `sqlite-utils`
- `simple-graph-sqlite`
- `litequeue`
- `sqlitedict`

### Optional SDKs
Service SDKs install on demand when workflows need them:
- `PyGithub`, `slack_sdk`, `notion-client`, `boto3`, etc.

## License

MIT
