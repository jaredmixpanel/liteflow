# Extending liteflow

This guide covers how to add new step types, commands, agents, skills, hooks, and templates to liteflow. Each extension point is auto-discovered -- no central registration is required unless noted otherwise.

## Plugin Structure Overview

```
liteflow/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest (name, version, description)
├── commands/                 # Auto-discovered commands
│   └── flow-*.md
├── agents/                   # Auto-discovered agents
│   └── *.md
├── skills/                   # Auto-discovered skills
│   └── */SKILL.md
├── hooks/
│   └── hooks.json            # Hook definitions
├── templates/                # Workflow templates
│   └── */manifest.json + workflow.json + steps/
├── scripts/                  # Utility scripts
│   └── cron-runner.sh
└── lib/                      # Python runtime
    └── *.py
```

All paths in commands and scripts use `${CLAUDE_PLUGIN_ROOT}` -- never hardcode paths.

## Adding a New Command

Create `commands/flow-<name>.md` with YAML frontmatter:

```markdown
---
name: flow-mycommand
description: What this command does
argument-hint: <required-arg> [optional-arg]
allowed-tools:
  - Bash
  - Read
---

Instructions for Claude to execute this command.

The user wants to: `$ARGUMENTS`

Run: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py <subcommand> $ARGUMENTS`
```

Key conventions:

- Name must start with `flow-` (convention, not enforced).
- `argument-hint` shows usage help when listing commands.
- `allowed-tools` lists which tools the command may use. Common tools include `Bash`, `Read`, `Write`, `Grep`, and `Glob`.
- Use `$ARGUMENTS` to reference user input passed to the command.
- Use `${CLAUDE_PLUGIN_ROOT}` for all file paths -- this resolves to the plugin installation directory at runtime.
- Commands are auto-discovered by Claude Code from the `commands/` directory. No registration step is needed.

The body of the file is a system prompt that tells Claude how to execute the command. It can include multi-step instructions, context about expected behavior, and references to other commands or CLI subcommands.

See the existing commands in `commands/` for examples. `flow-new.md`, `flow-run.md`, and `flow-show.md` are good starting points.

## Adding a New Step Type

Step types are the execution primitives of liteflow workflows. The nine built-in types are: `script`, `shell`, `claude`, `query`, `http`, `transform`, `gate`, `fan-out`, and `fan-in`.

### 1. Write the executor function

Add an executor function to `lib/steps.py`:

```python
def execute_mytype(
    config: Dict[str, Any],
    context: Dict[str, Any],
    run_id: str,
    liteflow_home: str,
) -> Dict[str, Any]:
    """Execute a mytype step.

    Config fields:
        my_field: Description of the field.
    """
    my_field = config["my_field"]
    # ... implementation ...
    return {"result": "output"}
```

### 2. Register in the executors dict

Add the new type to the `executors` dict in `execute_step()` (around line 69-79 of `lib/steps.py`):

```python
executors = {
    "script": execute_script,
    "shell": execute_shell,
    "claude": execute_claude,
    "query": execute_query,
    "http": execute_http,
    "transform": execute_transform,
    "gate": execute_gate,
    "fan-out": execute_fan_out,
    "fan-in": execute_fan_in,
    "mytype": execute_mytype,  # Add here
}
```

### Guidelines

- **Function signature**: Must be `(config, context, run_id, liteflow_home) -> Dict[str, Any]`. All four parameters are always passed by the engine.
- **Return value**: Return a dict. The engine merges it into the workflow context under the step's ID (`context[step_id] = return_value`).
- **Error handling**: Raise exceptions to signal failure. The engine catches them and applies the step's `on_error` policy (fail, retry, or skip).
- **Template substitution**: Use `_template(text, context)` to resolve `{variable}` placeholders in config values before using them. This supports dot-path access like `{prior_step.nested.key}`.
- **Context access**: Use `StepContext(context)` for convenient dot-path lookups into the context dict.
- **HTTP with auth**: For steps that make HTTP requests, use `HTTPStep` with `SecureStore` for credential injection rather than handling auth manually.
- **Imports**: Import helpers from `lib/helpers.py`: `from .helpers import HTTPStep, RunLogger, StepContext`.

## Adding a New Agent

Agents are autonomous specialists that Claude Code delegates to for complex tasks. Create `agents/<name>.md` with YAML frontmatter:

```markdown
---
description: |
  Describe what this agent does and when to use it.

  <example>
  Context: User describes a situation.
  user: "analyze my workflow performance"
  assistant: "I'll use the workflow-analyzer agent to investigate this."
  </example>

  <example>
  Context: User asks a related question.
  user: "why is my deploy workflow slow?"
  assistant: "I'll use the workflow-analyzer agent to diagnose this."
  </example>
tools:
  - Read
  - Bash
  - Grep
  - Glob
model: sonnet
---

System prompt for the agent goes here.

Explain the agent's role, capabilities, process, and output format.
```

Key conventions:

- **`<example>` blocks** in the description define trigger patterns. Include 2-3 examples showing the kinds of user requests that should activate this agent.
- **`tools`** lists the tools available to the agent during execution.
- **`model`** specifies the Claude model: `sonnet` (standard tasks), `opus` (complex analysis), or `haiku` (quick lookups).
- **The body** (below the frontmatter) is the agent's system prompt. It should describe the agent's role, its step-by-step process, and the format of its output.
- Agents are auto-discovered from the `agents/` directory.

See the existing agents for examples: `workflow-builder.md` (construction), `workflow-debugger.md` (diagnosis), and `workflow-optimizer.md` (performance).

## Adding a New Skill

Skills provide educational content and integration guidance that Claude loads into context when relevant to the user's task. Create a directory `skills/<name>/` with a `SKILL.md` file:

```markdown
---
name: my-skill
description: "Use this skill when the user asks about <trigger conditions>."
---

# Skill Title

Content that Claude loads when the skill is activated.

## Section One

Detailed guidance, code examples, and best practices.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/my-skill/references/detailed-spec.md`
```

### Optional reference files

Place supplementary material at `skills/<name>/references/<file>.md`. Reference these from the main `SKILL.md` using `${CLAUDE_PLUGIN_ROOT}` paths. Reference files allow progressive disclosure -- the main skill file provides an overview, and references contain the full details.

### Guidelines

- The `description` field in the frontmatter determines when Claude activates the skill. Write it as a trigger condition listing the relevant topics and keywords.
- Skills are read-only context -- they provide knowledge, not executable commands.
- Skills are auto-discovered from the `skills/` directory.

See `skills/workflow-building/SKILL.md` and `skills/workflow-debugging/` for examples.

## Adding a New Hook

Hooks run automatically in response to Claude Code lifecycle events. Edit `hooks/hooks.json` to add a new hook:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/my-hook.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

### Supported events

| Event | When it fires |
|-------|---------------|
| `SessionStart` | When a Claude Code session begins |
| `PreToolUse` | Before a tool is used |
| `PostToolUse` | After a tool completes |
| `Stop` | When the assistant stops generating |

### Hook structure

Each event maps to an array of hook groups. Each group has:

- **`matcher`** -- A string to match against (empty string matches everything). For `PreToolUse`/`PostToolUse`, this matches the tool name.
- **`hooks`** -- An array of hook definitions, each with:
  - `type` -- Currently `"command"` (runs a shell command).
  - `command` -- The command to execute. Use `${CLAUDE_PLUGIN_ROOT}` for paths.
  - `timeout` -- Maximum execution time in seconds.

### Guidelines

- Keep hooks fast. They run synchronously and block the session if slow.
- Use `2>/dev/null || true` for hooks that should not block on failure (as the existing `SessionStart` hook does).
- Hook scripts receive event context via environment variables.

## Adding a New Template

Templates are pre-built workflow packages that users can instantiate. Create a directory `templates/<name>/` with three components:

### Required files

**`manifest.json`** -- Metadata, required credentials, and user-configurable variables:

```json
{
  "name": "my-template",
  "description": "What this template does",
  "version": "1.0.0",
  "required_credentials": ["github", "slack"],
  "variables": {
    "repo_url": "GitHub repository URL",
    "channel": "Slack channel for notifications"
  }
}
```

**`workflow.json`** -- The workflow graph definition with nodes (steps) and edges (transitions):

```json
{
  "nodes": [
    {
      "id": "fetch_data",
      "type": "http",
      "config": { "url": "{repo_url}/api/data", "method": "GET" }
    },
    {
      "id": "process",
      "type": "script",
      "config": { "script": "process.py" }
    }
  ],
  "edges": [
    { "from": "fetch_data", "to": "process" }
  ]
}
```

**`steps/`** -- Directory containing step scripts referenced by the workflow. Each script follows the standard step contract (`run(context) -> dict`, JSON stdin/stdout).

### Guidelines

- `required_credentials` lists services the user must authenticate with before running. The `flow-auth` command handles credential setup.
- `variables` defines user-provided values that are substituted into the workflow via `{variable}` template syntax.
- Templates are auto-discovered by the `flow-templates` command from the `templates/` directory.
- See `templates/pr-review/` and `templates/morning-briefing/` for complete examples.

See the [creating-templates.md](creating-templates.md) guide for full details on template design and best practices.

## Convention Reference

| Convention | Details |
|-----------|---------|
| `${CLAUDE_PLUGIN_ROOT}` | Always use this for paths in commands and scripts |
| Step contract | `run(context: dict) -> dict`, JSON stdin/stdout |
| Template substitution | `{variable}` with dot-path support (e.g., `{step_id.nested.key}`) |
| Step scripts location | `~/.liteflow/steps/<workflow-name>/` |
| Database location | `~/.liteflow/` (workflows.db, execution.db, queue.db, credentials.db, config.db) |
| Command naming | Commands use `flow-<name>` prefix |
| Step script naming | Snake_case filenames matching the step ID (e.g., `fetch_data.py`) |
| Error handling | Use `on_error` in step config: `fail` (default), `retry`, or `skip` |
| Credentials | Never plaintext. Use `SecureStore` with Fernet encryption via `flow-auth` |

## Cross-References

- [Architecture](../concepts/architecture.md) -- System architecture and module relationships
- [Step Types Reference](../reference/step-types/index.md) -- Complete reference for all built-in step types
- [Module Reference](../reference/modules/index.md) -- Python API documentation
- [Commands Reference](../reference/commands.md) -- All available commands
- [Creating Templates](creating-templates.md) -- Template creation guide
- [Documentation Home](../index.md) -- Docs home
