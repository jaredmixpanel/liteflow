---
name: flow-on-api
description: Create an API-triggered Routine for a workflow
argument-hint: "<workflow-name>"
allowed-tools: ["Bash"]
---

Create a Claude Code Routine with an API trigger endpoint that runs the specified workflow.

If no workflow name is provided, ask the user which workflow to expose via API.

The Routine should:
1. Accept an API trigger (HTTP POST)
2. Run `/liteflow:flow-run <workflow-name>` with the POST body passed as context via `--context`
3. Return execution results

Create the Routine using Claude Code's Routines feature with an API trigger configuration.

After creation, return to the user:
- The API endpoint URL for triggering the workflow
- The bearer token for authentication
- An example `curl` command showing how to trigger the workflow:
  ```
  curl -X POST <endpoint-url> \
    -H "Authorization: Bearer <token>" \
    -H "Content-Type: application/json" \
    -d '{"key": "value"}'
  ```

Inform the user that Routines require Claude Code's Routines feature to be enabled and available.
