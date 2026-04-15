# Architecture Overview

liteflow is a Claude Code plugin providing DAG-based workflow automation built on Python + SQLite. Zero infrastructure -- no server, Docker, web UI, Node.js, or Redis. This page explains the two-layer architecture and how all components fit together.

---

## Two-Layer Design

liteflow is split into two distinct layers: a **plugin layer** that Claude Code auto-discovers, and a **Python runtime** that does the actual work.

### Plugin Layer

The plugin layer lives in the repository root and consists entirely of Markdown files with YAML frontmatter. Claude Code auto-discovers these at load time.

| Component | Directory | Count | Purpose |
|-----------|-----------|-------|---------|
| Commands | `commands/` | 16 | Slash commands users invoke directly |
| Agents | `agents/` | 3 | Autonomous sub-agents for specialized tasks |
| Skills | `skills/` | 2 | Knowledge bundles with reference documents |
| Hooks | `hooks/` | 1 | Event-driven automation |

**Commands** (16 total):

- `flow-setup` -- Install dependencies and initialize databases
- `flow-new` -- Create a new workflow from scratch
- `flow-build` -- Build a workflow from a template
- `flow-list` -- List all workflows
- `flow-show` -- Show workflow details and structure
- `flow-run` -- Execute a workflow
- `flow-history` -- View execution history
- `flow-inspect` -- Inspect a specific run
- `flow-status` -- Check system health
- `flow-edit` -- Modify an existing workflow
- `flow-visualize` -- Render a workflow as a diagram
- `flow-auth` -- Manage credentials and API tokens
- `flow-schedule` -- Schedule recurring workflow execution
- `flow-on-github` -- GitHub event-triggered workflows
- `flow-on-api` -- API webhook-triggered workflows
- `flow-templates` -- Browse and apply workflow templates

**Agents** (3 total):

- `workflow-builder` -- Helps design and create new workflows interactively
- `workflow-debugger` -- Diagnoses and fixes failing workflow runs
- `workflow-optimizer` -- Analyzes workflows for performance improvements

**Skills** (2 total):

- `workflow-building` -- Knowledge bundle with `references/step-contract.md` and `references/step-types.md`
- `workflow-debugging` -- Knowledge bundle with `references/error-patterns.md`

**Hook** (1 total):

- `SessionStart` -- Runs a silent health check via `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py status --quiet` on every session start (5-second timeout, failure ignored)

### Python Runtime

The Python runtime lives in `lib/` and contains ~2,950 lines of code across 10 files. This is where all execution logic resides.

| Module | Role |
|--------|------|
| `engine.py` | Core orchestrator. The `LiteflowEngine` class drives all workflow operations. |
| `steps.py` | 9 step type executors (script, shell, claude, query, http, transform, gate, fan-out, fan-in). Handles template variable substitution. |
| `graph.py` | Workflow DAG management. Wraps `simple-graph-sqlite` -- workflows are nodes, steps are nodes linked by "contains" edges, transitions are separate edges. |
| `state.py` | Execution tracking. Manages `runs` and `step_runs` tables. Wraps `sqlite-utils`. |
| `queue.py` | Execution queue with visibility timeouts. Wraps `litequeue`. |
| `creds.py` | Credential storage. `SecureStore` class wraps `sqlitedict` with Fernet encryption (falls back to base64 XOR). |
| `helpers.py` | Utilities: `StepContext` (context assembly), `HTTPStep` (HTTP request execution), `RunLogger` (structured logging). |
| `deps.py` | Lazy dependency installation. Silently installs packages on first import failure. |
| `cli.py` | CLI interface. Uses `argparse`, dispatches all operations to `LiteflowEngine` methods. |
| `__init__.py` | Public exports: `LiteflowEngine`, `StepContext`, `SecureStore`, `HTTPStep`, `RunLogger`. |

---

## Module Dependency Diagram

The following diagram shows how the Python runtime modules depend on each other:

```mermaid
graph TD
    cli["cli.py"] --> engine["engine.py"]

    engine --> graph["graph.py"]
    engine --> queue["queue.py"]
    engine --> state["state.py"]
    engine --> steps["steps.py"]
    engine --> helpers["helpers.py"]

    steps --> helpers
    steps --> creds["creds.py"]

    helpers --> creds

    graph --> deps["deps.py"]
    state --> deps
    queue --> deps
    creds --> deps

    classDef core fill:#4a90d9,stroke:#2c5f8a,color:#fff
    classDef data fill:#50b86c,stroke:#2d7a3e,color:#fff
    classDef util fill:#f5a623,stroke:#c47d0e,color:#fff
    classDef entry fill:#9b59b6,stroke:#6c3483,color:#fff

    class engine core
    class graph,state,queue,creds data
    class helpers,deps,steps util
    class cli entry
```

**Reading the diagram:**

- **Purple** (`cli.py`) -- Entry point. All operations flow through here.
- **Blue** (`engine.py`) -- Core orchestrator. Coordinates all other modules.
- **Green** (`graph.py`, `state.py`, `queue.py`, `creds.py`) -- Data layer. Each wraps a dedicated SQLite library.
- **Orange** (`steps.py`, `helpers.py`, `deps.py`) -- Execution and utility layer.

---

## SQLite Foundation

liteflow's entire persistence layer is built on 4 SQLite libraries managing 5 database files. No external database server is needed.

| Library | Database | Role |
|---------|----------|------|
| `simple-graph-sqlite` | `workflows.db` | Workflow DAG definitions (nodes + edges) |
| `sqlite-utils` | `execution.db` | Run history and step results (`runs` + `step_runs` tables) |
| `litequeue` | `queue.db` | Execution queue with visibility timeouts |
| `sqlitedict` | `credentials.db` | Encrypted API tokens (Fernet encryption with machine-derived key) |
| `sqlitedict` | `config.db` | Plugin configuration and settings |

All databases live at `~/.liteflow/`. Step scripts live at `~/.liteflow/steps/<workflow-name>/`.

This design makes liteflow's state fully **portable** (copy the directory), **inspectable** (open any `.db` with standard SQLite tools), and **backupable** (single directory to snapshot).

---

## Plugin-to-Runtime Flow

Here is how a command invocation travels from the user through the plugin layer and into the Python runtime:

```
User                    Claude Code               Plugin Layer              Python Runtime
 |                         |                         |                         |
 |  /liteflow:flow-run     |                         |                         |
 |  morning-briefing       |                         |                         |
 |------------------------>|                         |                         |
 |                         |  auto-discover           |                         |
 |                         |  commands/flow-run.md    |                         |
 |                         |------------------------>|                         |
 |                         |                         |  python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py
 |                         |                         |  run morning-briefing    |
 |                         |                         |------------------------>|
 |                         |                         |                         |  1. cli.py parses args
 |                         |                         |                         |  2. Creates LiteflowEngine
 |                         |                         |                         |  3. graph.py loads DAG
 |                         |                         |                         |  4. queue.py enqueues entry steps
 |                         |                         |                         |  5. steps.py executes each step
 |                         |                         |                         |  6. state.py records results
 |                         |                         |  JSON results to stdout  |
 |                         |                         |<------------------------|
 |                         |  parse JSON output       |                         |
 |                         |<------------------------|                         |
 |  display results        |                         |                         |
 |<------------------------|                         |                         |
```

**Step by step:**

1. User invokes `/liteflow:flow-run morning-briefing`
2. Claude Code discovers and executes `commands/flow-run.md`
3. The command runs `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py run morning-briefing`
4. `cli.py` parses the arguments and creates a `LiteflowEngine` instance
5. The engine orchestrates the run: `graph.py` (load definitions) -> `queue.py` (schedule steps) -> `steps.py` (execute) -> `state.py` (track results)
6. JSON results are returned to stdout, parsed by the command, and displayed to the user

---

## Zero-Infrastructure Philosophy

liteflow is designed to run with no infrastructure beyond Python itself:

- **4 pip packages** -- The entire system depends on `simple-graph-sqlite`, `sqlite-utils`, `litequeue`, and `sqlitedict`. All install automatically on first use via `deps.py`.
- **No daemon process** -- liteflow is invoked, runs to completion, then exits. There is no background server or long-running process.
- **All state in SQLite** -- Five `.db` files in a single directory (`~/.liteflow/`). Portable, inspectable with any SQLite client, and trivially backupable.
- **On-demand optional SDKs** -- Packages like `PyGithub`, `slack_sdk`, `requests`, and others install automatically the first time a workflow needs them. Core functionality never depends on them.
- **No build step** -- The plugin is pure Markdown (plugin layer) and pure Python (runtime). No transpilation, bundling, or compilation.

---

## See Also

- [Workflows and DAGs](workflows-and-dags.md) -- Deeper dive into the DAG model and how workflows are structured
- [Execution Engine](execution-engine.md) -- How the queue-driven run loop processes steps
- [Context and Data Flow](context-and-data-flow.md) -- How data moves between steps during execution
- [Module Reference](../reference/modules/index.md) -- Full API reference for all Python modules
- [Commands Reference](../reference/commands.md) -- Complete reference for all 16 commands
- [Documentation Home](../index.md) -- Back to the docs home page
