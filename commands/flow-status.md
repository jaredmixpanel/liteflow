---
name: flow-status
description: Show liteflow system status
allowed-tools: ["Bash", "Read"]
---

Run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py status` to retrieve the current system status.

Display the results formatted as a status dashboard with the following sections:
- **Installed Dependencies**: list of Python packages and their versions
- **Database Sizes**: file sizes of each database under `~/.liteflow/`
- **Queue Depth**: number of pending items in the execution queue
- **Recent Runs**: last 5 workflow executions with status
- **Configured Credentials**: list of services with credentials configured (names only, never values)

If liteflow is not set up yet, suggest running `/liteflow:flow-setup` first.
