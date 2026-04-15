---
name: flow-new
description: Create a new workflow from natural language description
argument-hint: "<name> [description]"
allowed-tools: ["Bash", "Write", "Read", "Glob"]
---

Create a new workflow from the user's natural language description.

If only a name is given with no description, ask the user what the workflow should do before proceeding.

When both name and description are provided:

1. **Parse the description** to identify:
   - Individual steps and their types (script, shell, claude, query, http, transform, gate, fan-out, fan-in)
   - Data flow and connections between steps
   - Any conditional branches or parallel paths

2. **Design the workflow graph** — determine the steps and edges (connections) that form the DAG.

3. **Generate step scripts** for each step, following the step contract:
   - Each step is a standalone Python file
   - Reads JSON from stdin
   - Has a `run(context)` function that returns a dict
   - Outputs JSON to stdout

4. **Save step scripts** to `~/.liteflow/steps/<workflow-name>/`

5. **Register the workflow** using `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py` subcommands to add steps and edges to the graph database.

6. **Show the created workflow structure** — display each step with its type and the edges connecting them. Include a Mermaid diagram if the workflow has 3 or more steps.
