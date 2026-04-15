"""Placeholder for the liteflow scripts/ directory.

This directory holds shared utility scripts that plugin components can invoke.
Unlike the Python library in lib/ (which is the core engine), scripts here are
standalone executables meant to be called from hooks, commands, or step scripts
via ${CLAUDE_PLUGIN_ROOT}/scripts/<name>.

Intended uses:

  - Hook helper scripts: Validation or preprocessing logic that hooks invoke
    before or after tool use. For example, a PreToolUse hook might call a script
    here to lint a generated step script before it gets written to disk.

  - Template scaffolding: Scripts that generate boilerplate step scripts or
    workflow definitions from user input, called by the flow-new or flow-build
    commands when interactive generation isn't needed.

  - Credential rotation: A script that refreshes OAuth tokens or rotates API
    keys in the credential store, callable from the liteflow-health workflow
    template or a scheduled Routine.

  - Database maintenance: Scripts for vacuuming SQLite databases, exporting
    workflow definitions to JSON, or migrating schemas between versions.

  - CI/CD integration: Scripts that wrap the CLI for use in CI pipelines,
    e.g., running a workflow and asserting its exit status in a GitHub Action.

Convention:
  - Use kebab-case filenames with appropriate extensions (.py, .sh)
  - Make scripts executable (chmod +x) with proper shebangs
  - Reference via ${CLAUDE_PLUGIN_ROOT}/scripts/<name> for portability
  - Scripts should be self-contained — import from lib/ if needed but don't
    assume any working directory

This file is a no-op placeholder. Delete it once real scripts are added.
"""
