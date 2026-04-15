---
name: flow-show
description: Display workflow structure and generate visualization
argument-hint: "<workflow-name>"
allowed-tools: ["Bash", "Read"]
---

If no workflow name is provided, run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py list` to show available workflows and ask the user to choose one.

Once a workflow name is known, run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py show <workflow-name>` to retrieve its structure.

Display the workflow as:

1. **Step details** — For each step, show:
   - Step ID
   - Step type (script, shell, claude, query, http, transform, gate, fan-out, fan-in)
   - Configuration summary (what the step does)

2. **Edge connections** — Show the flow between steps:
   - Source step -> Target step
   - Any condition labels on edges

3. **Mermaid diagram** — Generate a Mermaid flowchart of the workflow graph that can be rendered. Use appropriate shapes for different step types and label edges with conditions where applicable.
