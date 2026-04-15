---
name: flow-run
description: Execute a workflow
argument-hint: "<workflow-name> [--dry-run] [--context '{...}']"
allowed-tools: ["Bash", "Read"]
---

Execute the specified workflow.

If no workflow name is provided, run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py list` to show available workflows and ask the user to choose one.

Run the workflow using:
```
python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py run <workflow-name> [--dry-run] [--context '...']
```

Pass through any flags the user provided:
- `--dry-run` — Show what would execute without performing side effects
- `--context '{...}'` — Provide initial context as a JSON object

Stream progress output to the user, showing each step as it executes with its status (running, completed, failed, skipped).

On completion, display a summary of results including:
- Total execution time
- Number of steps completed
- Final output data

On failure, show the error details and suggest running `/liteflow:flow-inspect last` for a detailed breakdown of what went wrong.
