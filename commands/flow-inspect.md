---
name: flow-inspect
description: Inspect a specific workflow run in detail
argument-hint: "<run-id | 'last'>"
allowed-tools: ["Bash", "Read"]
---

If the argument is "last" or no argument is provided, retrieve the most recent run.

Run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py inspect <run-id>` to get detailed execution information.

Display the following:

1. **Run metadata** — Workflow name, run ID, overall status, start time, end time, total duration.

2. **Step-by-step execution** — For each step in execution order, show:
   - Step name and type
   - Status (completed, failed, skipped)
   - Duration
   - Input context (summarized if large)
   - Output data (summarized if large)

3. **Failure analysis** — For any failed steps:
   - The full error message
   - Analysis of what likely went wrong
   - Suggestions for fixing the issue (e.g., missing credentials, invalid input, script errors)

4. **Recommendations** — Based on the run results, suggest next actions:
   - Re-run with fixes
   - Edit the workflow (`/liteflow:flow-edit`)
   - Check credentials (`/liteflow:flow-auth test`)
