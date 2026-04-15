---
name: flow-visualize
description: Generate a Mermaid diagram of a workflow
argument-hint: "<workflow-name>"
allowed-tools: ["Bash", "Read"]
---

If no workflow name is provided, run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py list` to show available workflows and ask the user to choose one.

Load the workflow graph by running `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py show <workflow-name>` and generate a Mermaid flowchart diagram.

Use these node shapes by step type:
- **script** — rectangle `[Step Name]`
- **shell** — rectangle `[Step Name]`
- **claude** — stadium shape `([Step Name])`
- **query** — subroutine `[[Step Name]]`
- **http** — parallelogram `[/Step Name/]`
- **transform** — hexagon `{{Step Name}}`
- **gate** — diamond `{Step Name}`
- **fan-out** — double circle `(((Step Name)))`
- **fan-in** — double circle `(((Step Name)))`

Apply color coding by step type using `style` directives:
- script/shell: blue
- claude: purple
- query: green
- http: orange
- transform: teal
- gate: yellow
- fan-out/fan-in: pink

Label edges with condition text where applicable.

Output the complete Mermaid code block that can be rendered in any Mermaid-compatible viewer.
