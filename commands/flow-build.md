---
name: flow-build
description: Interactively build a workflow through conversation
allowed-tools: ["Bash", "Write", "Read", "Glob", "Agent"]
---

Start a conversational workflow builder. Guide the user through designing and creating a workflow step by step.

Begin by asking these questions one at a time (do not dump all questions at once):

1. **What should this workflow accomplish?** — Get the overall goal and expected outcome.
2. **What services/APIs does it need to interact with?** — Identify external dependencies and credentials needed.
3. **Are there any conditional branches or parallel processing needs?** — Understand the graph shape.

Then iteratively construct the workflow:

1. **Design steps** — Propose a set of steps based on the user's answers. Show each step's name, type, and purpose. Ask for confirmation or adjustments.

2. **Generate scripts** — For each confirmed step, generate a Python script following the step contract (JSON stdin, `run(context)` function, JSON stdout). Save to `~/.liteflow/steps/<workflow-name>/`.

3. **Create the graph** — Register the workflow, steps, and edges using `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py`.

4. **Confirm each step** with the user before proceeding to the next.

After the workflow is fully built, display the complete structure and suggest next steps:
- Set up credentials if needed (`/liteflow:flow-auth`)
- Do a dry run (`/liteflow:flow-run <name> --dry-run`)
- Schedule it (`/liteflow:flow-schedule`)
