# liteflow

Workflow automation as a Claude Code plugin. An n8n-lite that requires zero infrastructure.

## What is liteflow?

liteflow turns Claude into a conversational workflow automation platform. The entire system runs on Python's standard library SQLite and a handful of pip-installable libraries. There is no server, no Docker, no web UI, no Node.js, no Redis. Install the plugin and you have a running workflow automation engine immediately.

Claude serves simultaneously as the **builder**, the **orchestrator**, the **debugger**, and — uniquely — a **first-class step type** within workflows.

## Quick Start

```
# 1. Install the plugin
claude --plugin-dir /path/to/liteflow

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
| `shell` | Run a shell command | `gh`, `git`, `curl` |
| `claude` | LLM reasoning step | Classification, summarization |
| `query` | SQL against any SQLite DB | Cross-plugin data queries |
| `http` | HTTP request (zero deps) | Webhooks, REST APIs |
| `transform` | Pure data transformation | Reshape, filter, extract |
| `gate` | Conditional branch point | If/else routing |
| `fan-out`/`fan-in` | Parallel processing | Process each item in array |

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

liteflow composes with Claude Code's automation stack:

- **Routines** (primary) — Schedule, GitHub events, or API triggers on Anthropic's cloud
- **`/loop`** — In-session polling for development and monitoring
- **Hooks** — Session lifecycle triggers (SessionStart, PostToolUse, Stop)
- **Manual** — Direct invocation via `/liteflow:flow-run`
- **Chained** — Workflows triggering other workflows

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
