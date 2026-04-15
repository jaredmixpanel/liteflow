---
name: flow-history
description: Show execution history for workflows
argument-hint: "[workflow-name] [--limit N]"
allowed-tools: ["Bash"]
---

Run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py history [--workflow <name>] [--limit N]` to retrieve execution history.

If a workflow name is provided, filter history to that workflow only. If `--limit` is specified, use that value; otherwise default to 20.

Display the results as a table with these columns:
- **Run ID** — unique identifier for the execution
- **Workflow** — workflow name
- **Status** — success, failed, or running
- **Started** — start timestamp
- **Duration** — how long the run took
- **Steps Completed** — number of steps that completed successfully out of total

If no history exists, inform the user and suggest running a workflow with `/liteflow:flow-run`.
