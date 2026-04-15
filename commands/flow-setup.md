---
name: flow-setup
description: Install dependencies and initialize liteflow databases
allowed-tools: ["Bash", "Read"]
---

Run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py setup` to install all required dependencies and initialize the liteflow databases.

Report what was installed and initialized. Display the list of Python packages installed and the database files created under `~/.liteflow/`.

If errors occur, diagnose the issue and suggest fixes. Common problems include:
- Missing Python 3 installation
- pip not available or outdated
- Permission issues writing to `~/.liteflow/`
- Missing system dependencies

After successful setup, confirm that all database files exist: workflows.db, execution.db, queue.db, credentials.db, config.db.
