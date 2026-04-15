---
name: flow-edit
description: Edit a workflow — add, remove, or modify steps and connections
argument-hint: "<workflow-name> <action>"
allowed-tools: ["Bash", "Write", "Read", "Glob"]
---

Edit an existing workflow. If no action is specified, run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py show <workflow-name>` to display the current workflow structure, then ask the user what they would like to change.

Supported actions:

### `add-step <step-description>`
Add a new step to the workflow. Based on the description:
1. Determine the step type and configuration
2. Generate a step script following the step contract (JSON stdin, `run(context)` function, JSON stdout)
3. Save the script to `~/.liteflow/steps/<workflow-name>/`
4. Register the step in the graph and ask the user where to connect it (after which step, before which step)
5. Create the appropriate edges

### `remove-step <step-id>`
Remove a step from the workflow:
1. Identify incoming and outgoing edges
2. Reconnect edges around the removed step to maintain graph continuity
3. Remove the step from the graph and delete its script file

### `connect <step-a> <step-b> [--condition '...']`
Create a new edge between two steps. If a condition is provided, add it as an edge label/condition.

### `edit-step <step-id>`
Modify an existing step:
1. Read the current step configuration and script
2. Ask the user what to change
3. Update the script and/or configuration
4. Save changes

After any edit, display the updated workflow structure.
