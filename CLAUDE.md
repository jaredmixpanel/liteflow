# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

liteflow is a Claude Code plugin that provides DAG-based workflow automation built entirely on Python + SQLite. It is a plugin (not a standalone app) — it has commands, agents, skills, and hooks that integrate with Claude Code, plus a Python runtime engine in `lib/`.

## Running & Testing

```bash
# Setup: install SQLite deps, initialize databases at ~/.liteflow/
python3 -m lib.cli setup

# Run a workflow
python3 -m lib.cli run <workflow-id> [--dry-run] [--context '{}']

# Other CLI commands
python3 -m lib.cli list|show|history|inspect|status|auth

# Test the plugin in Claude Code
claude --plugin-dir /path/to/liteflow
```

No test framework is configured yet. Test manually via CLI or by loading the plugin.

## Architecture

### Two Layers

1. **Plugin layer** (commands/, agents/, skills/, hooks/) — Markdown files that Claude Code auto-discovers. Commands invoke the Python runtime via `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py <subcommand>`.

2. **Python runtime** (lib/) — The actual engine. ~2,950 LOC across 10 files.

### How Workflows Execute

Workflows are DAGs stored in SQLite via `simple-graph-sqlite`. Execution is queue-driven via `litequeue`:

1. `engine.run_workflow()` finds entry steps (no inbound edges), enqueues them
2. `engine._run_loop()` dequeues a step, loads its config from the graph DB, builds context from prior step outputs, dispatches to the right executor in `steps.py`
3. On success: outbound edges are evaluated, eligible successor steps are enqueued
4. On failure: error policy applies (fail/retry/skip)
5. Loop until queue is empty

Context accumulates across steps — each step's output merges under its step_id key. Downstream steps see all prior outputs.

### Key Module Relationships

- `engine.py` orchestrates everything — calls `graph.py` for definitions, `queue.py` for scheduling, `state.py` for tracking, `steps.py` for execution
- `steps.py` dispatches to 9 executors (script, shell, claude, query, http, transform, gate, fan-out, fan-in) and handles template variable substitution
- `graph.py` wraps `simple_graph_sqlite` — workflows are nodes, steps are nodes linked by "contains" edges, transitions are separate edges
- `state.py` wraps `sqlite-utils` — `runs` and `step_runs` tables track execution history
- `creds.py` wraps `sqlitedict` with Fernet encryption (falls back to base64 XOR)
- `deps.py` lazy-installs packages on first import failure

### Database Files (all at ~/.liteflow/)

`workflows.db` (graph defs), `execution.db` (run history), `queue.db` (execution queue), `credentials.db` (encrypted tokens), `config.db` (settings). Step scripts live at `~/.liteflow/steps/<workflow-name>/`.

## Key Conventions

- **Step contract**: Every step script has `run(context: dict) -> dict`, reads JSON from stdin, writes JSON to stdout. No framework dependency.
- **${CLAUDE_PLUGIN_ROOT}**: All commands reference the plugin root this way — never hardcode paths.
- **Template substitution**: `{variable}` in step configs gets replaced from context. Dot-path and hyphens supported: `{step-name.nested.key}`.
- **Transform/gate eval**: Both `execute_transform` and `execute_gate` use restricted `eval()` with `context` available as a local variable plus safe builtins.
- **Claude step type**: Invokes Claude via `subprocess.run(["claude", "-p", prompt])` — the prompt is template-substituted from context. Arbitrary CLI flags are passed via a `flags` dict in the step config.
- **Shell step file mode**: Shell steps support both inline `command` and `file` (path to a `.sh` script with optional `args`).
- **Scheduling**: `flow-schedule` uses `CronCreate` for in-session scheduling, Desktop scheduled tasks for persistent local, and Routines for cloud. A `loop.md` template is at `templates/loop.md`.
- **Fan-out/fan-in**: Fan-out returns `_fan_out_items`; the engine enqueues N copies of the next step with per-item context. The engine tracks completion and populates `_fan_in_results` with collected outputs before the fan-in step runs. Steps with multiple predecessors wait for all to complete before executing.
- **Lazy deps**: Core SQLite libraries install silently on first use. Optional SDKs (PyGithub, slack_sdk, etc.) install when a workflow first needs them.
- **Credentials**: Never stored in plaintext. `SecureStore` encrypts with machine-derived key. Auto-injected into HTTP requests via `HTTPStep._inject_auth()`.

## Adding Things

- **New command**: Create `commands/flow-<name>.md` with YAML frontmatter (name, description, allowed-tools). Auto-discovered.
- **New step type**: Add `execute_<type>()` to `steps.py`, register in the `executors` dict.
- **New template**: Create `templates/<name>/` with `manifest.json`, `workflow.json`, and `steps/`. Auto-discovered by `flow-templates` command.
- **New agent**: Create `agents/<name>.md` with YAML frontmatter including `<example>` blocks for triggering.
