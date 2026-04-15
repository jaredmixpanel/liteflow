---
name: flow-list
description: List all workflows with last run status
allowed-tools: ["Bash"]
---

Run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py list` to retrieve all registered workflows.

Format the output as a table with these columns:
- **Name** — workflow name
- **Steps** — number of steps in the workflow
- **Last Run** — timestamp of the most recent execution (or "Never" if not yet run)
- **Status** — status of the last run (success, failed, running, or "—")
- **Created** — when the workflow was created

If no workflows exist, inform the user and suggest creating one with `/liteflow:flow-new` or `/liteflow:flow-build`.
