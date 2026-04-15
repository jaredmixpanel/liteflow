---
name: flow-templates
description: List and use workflow templates
argument-hint: "[template-name]"
allowed-tools: ["Bash", "Read", "Write", "Glob"]
---

If no template name is provided, list available templates from `${CLAUDE_PLUGIN_ROOT}/templates/`. For each template, show:
- **Name** — template identifier
- **Description** — what the workflow does
- **Required Credentials** — services that need authentication configured

Read each template's `manifest.json` to extract this information.

If a template name is given, create a workflow from that template:

1. **Read the template** — Load `${CLAUDE_PLUGIN_ROOT}/templates/<template-name>/manifest.json` and `${CLAUDE_PLUGIN_ROOT}/templates/<template-name>/workflow.json` to understand the template structure.

2. **Gather configuration** — Ask the user for any required configuration values:
   - Credentials for required services (suggest using `/liteflow:flow-auth` to set these up)
   - Custom values specific to the template (e.g., repository names, channel IDs, email addresses)

3. **Copy step scripts** — Copy template step scripts from `${CLAUDE_PLUGIN_ROOT}/templates/<template-name>/steps/` to `~/.liteflow/steps/<workflow-name>/`, substituting any configuration placeholders.

4. **Register the workflow** — Use `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py` to register the workflow graph in the database with all steps and edges.

5. **Confirm and suggest next steps**:
   - Show the created workflow structure
   - If credentials are needed, suggest: `/liteflow:flow-auth <service>`
   - Suggest a test run: `/liteflow:flow-run <workflow-name> --dry-run`
   - Suggest scheduling if appropriate: `/liteflow:flow-schedule`
