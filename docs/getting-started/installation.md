# Installation and Setup

Get liteflow installed and verified in under 5 minutes. liteflow is a Claude Code plugin -- it runs inside Claude Code sessions, not as a standalone application.

---

## Prerequisites

Before you begin, make sure you have:

- **Python 3.7+** -- check with `python3 --version`
- **pip** -- comes bundled with Python; check with `python3 -m pip --version`
- **Claude Code CLI** -- the `claude` command must be available in your shell; see [Claude Code documentation](https://docs.anthropic.com/en/docs/claude-code) for installation

---

## Installation

There are two ways to load the liteflow plugin into Claude Code.

### Option A: Direct Path

Point Claude Code at the liteflow directory when starting a session:

```bash
claude --plugin-dir /path/to/liteflow
```

Replace `/path/to/liteflow` with the actual path to your local clone of the repository.

### Option B: Dev Marketplace (Development/Testing)

If you are developing or testing liteflow, you can register it through the plugin marketplace:

```
/plugin marketplace add /path/to/liteflow
/plugin install liteflow@liteflow-dev
```

This makes liteflow available across sessions without passing `--plugin-dir` each time.

---

## Initialize

Once the plugin is loaded, run the setup command inside your Claude Code session:

```
/liteflow:flow-setup
```

Under the hood, this runs `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py setup`, which does the following:

1. **Installs 4 core pip packages**:
   - `simple-graph-sqlite` -- graph storage for workflow DAGs
   - `litequeue` -- queue-driven step execution
   - `sqlite-utils` -- state and history tracking
   - `sqlitedict` -- encrypted credential storage

2. **Creates the `~/.liteflow/` directory** (and `~/.liteflow/steps/` for step scripts)

3. **Initializes 5 SQLite databases** for workflow definitions, execution history, queue management, credentials, and configuration

### Outside Claude Code

There is also a `setup.sh` script at the project root that performs the same initialization without requiring a Claude Code session:

```bash
./setup.sh
```

This is useful for CI environments or if you want to pre-initialize before your first session.

---

## Verify Installation

Run the status command to confirm everything is working:

```
/liteflow:flow-status
```

This displays a dashboard with:

| Section | What to Expect |
|---------|----------------|
| **Home directory path** | `~/.liteflow/` |
| **Database file sizes** | All 5 `.db` files should exist with non-zero sizes |
| **Queue depth** | 0 (no pending work) |
| **Recent runs** | Empty (no workflows executed yet) |
| **Workflow count** | 0 (no workflows created yet) |
| **Installed dependency status** | All 4 packages showing their versions |

If everything shows up correctly, liteflow is ready to use.

---

## What Was Created

After setup, your `~/.liteflow/` directory contains:

```
~/.liteflow/
├── workflows.db        # Workflow graph definitions (nodes + edges)
├── execution.db        # Run history and step execution records
├── queue.db            # Active execution queue
├── credentials.db      # API tokens (encrypted with machine-derived key)
├── config.db           # Plugin configuration and settings
└── steps/              # Step scripts organized by workflow name
```

Each database serves a distinct role:

| Database | Library | Purpose |
|----------|---------|---------|
| `workflows.db` | `simple-graph-sqlite` | Stores workflows as graph nodes, steps as linked nodes, transitions as edges |
| `execution.db` | `sqlite-utils` | Tracks `runs` and `step_runs` tables with full execution history |
| `queue.db` | `litequeue` | Manages the step execution queue with visibility timeouts |
| `credentials.db` | `sqlitedict` | Holds API tokens encrypted with Fernet (machine-derived key) |
| `config.db` | `sqlitedict` | Stores plugin settings and configuration |

All databases are standard SQLite files -- you can inspect them with any SQLite client if needed. For a deeper look at how these fit together, see [Architecture Overview](../concepts/architecture.md).

---

## SessionStart Hook

After installation, a `SessionStart` hook automatically runs each time you start a Claude Code session with the liteflow plugin loaded. The hook executes:

```bash
python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py status --quiet
```

This is a non-blocking health check with a 5-second timeout. It only surfaces output if something is unhealthy (missing databases, broken dependencies). Errors are suppressed with `|| true` so the hook never blocks session startup.

You do not need to configure this -- it is set up automatically as part of the plugin's `hooks/hooks.json`.

---

## Troubleshooting

### Python not found

Ensure `python3` is in your PATH:

```bash
python3 --version
```

If not found, install Python 3.7+ from [python.org](https://www.python.org/downloads/) or via your system package manager (`brew install python3`, `apt install python3`, etc.).

### pip install fails

If package installation fails with a permissions error, try installing with the `--user` flag:

```bash
python3 -m pip install --user simple-graph-sqlite litequeue sqlite-utils sqlitedict
```

On some systems (e.g., externally managed Python on Debian/Ubuntu), you may need:

```bash
python3 -m pip install --break-system-packages simple-graph-sqlite litequeue sqlite-utils sqlitedict
```

The `setup.sh` script tries all three approaches automatically.

### Database creation fails

Check that you have write permissions to `~/.liteflow/`:

```bash
mkdir -p ~/.liteflow && touch ~/.liteflow/test && rm ~/.liteflow/test
```

If the directory is on a read-only filesystem or restricted by permissions, set a custom path via the `LITEFLOW_HOME` environment variable:

```bash
export LITEFLOW_HOME=/path/to/writable/directory
```

### Plugin not loading

Verify the path you are passing to `--plugin-dir` is correct and contains the plugin manifest:

```bash
ls /path/to/liteflow/.claude-plugin/plugin.json
```

If this file does not exist, the directory is not a valid Claude Code plugin.

---

## Next Steps

With liteflow installed and verified, you are ready to start building workflows:

- **[Build Your First Workflow](first-workflow.md)** -- Create and run a workflow from scratch
- **[Set Up API Credentials](credentials.md)** -- Configure tokens for GitHub, Slack, and other services
- **[Explore Templates](templates.md)** -- Browse built-in workflow templates for common use cases

---

## See Also

- [Architecture Overview](../concepts/architecture.md) -- How the two-layer design and SQLite foundation work
- [Command Reference](../reference/commands.md) -- Details on `flow-setup`, `flow-status`, and all other commands
- [Documentation Home](../index.md) -- Back to the docs home page
