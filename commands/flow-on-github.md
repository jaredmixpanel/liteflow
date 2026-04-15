---
name: flow-on-github
description: Create a GitHub event-triggered Routine for a workflow
argument-hint: "<event-type> <workflow-name>"
allowed-tools: ["Bash"]
---

Create a Claude Code Routine triggered by GitHub events that runs the specified workflow.

If no event type or workflow name is provided, ask the user for both.

Supported event types:
- `pr-opened` — triggers when a pull request is opened
- `pr-merged` — triggers when a pull request is merged
- `push` — triggers on push to a branch (ask which branch, default: main)
- `issue-created` — triggers when a new issue is created
- `release-published` — triggers when a release is published

The Routine should:
1. Be triggered by the specified GitHub event
2. Run `/liteflow:flow-run <workflow-name>` with the event payload passed as context via `--context`
3. Include the event payload so workflow steps can access event data (PR number, branch, issue body, etc.)

Create the Routine using Claude Code's Routines feature.

Inform the user that:
- Routines require Claude Code's Routines feature to be enabled
- The GitHub integration must be configured for event triggers to work
- They can verify the trigger is active by checking their Routines configuration
