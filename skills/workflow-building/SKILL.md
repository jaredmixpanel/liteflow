---
name: workflow-building
description: "Use this skill when the user asks about building workflows, creating step scripts, defining workflow steps, connecting steps in a DAG, configuring step types (script, shell, claude, query, http, transform, gate, fan-out, fan-in), writing the step contract, or designing workflow automation with liteflow."
---

# Building Liteflow Workflows

## Workflow Structure

A liteflow workflow is a directed acyclic graph (DAG) stored in SQLite via simple-graph-sqlite. Each workflow consists of:

- **Workflow record**: A unique ID, human-readable name, and JSON metadata (description, version, author, created timestamp).
- **Steps (nodes)**: Each step is a node in the graph with JSON properties: `id` (unique within workflow), `type` (one of the 9 step types), and `config` (type-specific configuration).
- **Transitions (edges)**: Directed edges connecting steps. Each edge can carry an optional `condition` property for conditional branching.

Workflows live in `~/.liteflow/workflows.db`. Step scripts live in `~/.liteflow/steps/<workflow-name>/`.

## The Step Contract

Every step script follows one contract: JSON in via stdin, JSON out via stdout, exceptions signal failure. No framework imports required.

```python
import json, sys

def run(context: dict) -> dict:
    # Receives accumulated context from all prior steps
    # Returns output dict — merged into run context under this step's ID
    # Raise any exception to signal failure
    return {"result": "value"}

if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
```

This contract is minimal by design. Steps are standalone executables. Test any step independently:

```bash
echo '{"key": "value"}' | python my_step.py
```

Refer to `${CLAUDE_PLUGIN_ROOT}/skills/workflow-building/references/step-contract.md` for the full contract specification, advanced patterns, and helper utilities.

## Step Types Overview

Liteflow provides 9 step types. Choose the lightest type that fits the operation:

| Type | Purpose | When to Use |
|------|---------|-------------|
| `script` | Python file following step contract | Custom logic, data processing, API integrations |
| `shell` | Shell command execution | System commands, file operations, CLI tools |
| `claude` | LLM reasoning with templated prompt | Judgment calls, text generation, classification |
| `query` | SQL against any SQLite database | Reading/writing structured data |
| `http` | HTTP request via urllib (zero deps) | REST API calls, webhooks |
| `transform` | Pure data transformation | Reshaping data between steps |
| `gate` | Conditional branch point | If/else routing in the DAG |
| `fan-out` | Split array into parallel items | Process each item in a collection |
| `fan-in` | Collect parallel results | Aggregate fan-out results |

Refer to `${CLAUDE_PLUGIN_ROOT}/skills/workflow-building/references/step-types.md` for complete configuration details, required fields, and examples for each type.

## Building a Workflow

Follow this process to design and implement a workflow:

### 1. Define Inputs and Outputs

Identify what the workflow receives as initial context and what it should produce as final output. Write these down before designing steps. The initial context is passed as JSON to the first step(s).

### 2. Decompose into Steps

Break the task into discrete operations with clear boundaries. Each step should do exactly one thing. Prefer more small steps over fewer large steps — small steps are easier to test, debug, and reuse.

### 3. Choose Step Types

For each operation, select the lightest step type that handles it:
- Pure data reshaping? Use `transform`.
- Run a shell command? Use `shell`.
- Call an API? Use `http` for simple requests, `script` for complex auth or pagination.
- Need LLM reasoning? Use `claude`.
- Conditional logic? Use `gate`.
- Process a list? Use `fan-out` / `fan-in`.

### 4. Define Data Flow

Determine what each step produces and what downstream steps consume. Each step's output is namespaced by its step ID in the accumulated context. A step reading from a prior step accesses `context['<step_id>']['<key>']`.

### 5. Add Edges and Conditions

Connect steps with directed edges. For linear flows, edges have no conditions. For branching, use a `gate` step and add `when_true` / `when_false` properties to outgoing edges.

### 6. Write Step Scripts

Generate step scripts following the contract. Save them to `~/.liteflow/steps/<workflow-name>/`. Each script file name should match the step ID (e.g., `fetch_data.py` for step `fetch_data`).

### 7. Register the Graph

Use the CLI to register the workflow:

```bash
python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py create <workflow-name> --steps '<steps-json>' --edges '<edges-json>'
```

## Edge Conditions

Edges connect steps and control execution flow:

- **Unconditional edges**: Always followed when the source step succeeds. Used for linear sequences.
- **Conditional edges from gate steps**: Gate steps evaluate a condition and produce `{"_gate_result": true}` or `{"_gate_result": false}`. Outgoing edges carry `"when_true": true` or `"when_false": true` to route accordingly.
- **Conditional edges with expressions**: Any edge can carry a `"condition"` property — a Python expression evaluated against the current context. The edge is followed only if the expression evaluates to truthy.

Example gate pattern:

```json
{
  "edges": [
    {"from": "validate", "to": "check_threshold", "condition": null},
    {"from": "check_threshold", "to": "process_large", "when_true": true},
    {"from": "check_threshold", "to": "process_small", "when_false": true}
  ]
}
```

## Context Accumulation

The engine maintains a run context dictionary that accumulates outputs from every completed step:

1. The workflow starts with the initial context provided at run time.
2. After each step completes, its output dict is merged into the context under the step's ID: `context[step_id] = step_output`.
3. Subsequent steps receive the full accumulated context as input.

Access prior step outputs using the step ID as a key:

```python
def run(context: dict) -> dict:
    issues = context['fetch_issues']['issues']
    count = context['fetch_issues']['count']
    return {"processed": len(issues)}
```

## Template Substitution

Step configurations support `{variable}` placeholders that are filled from context at runtime. Use dot-path syntax for nested access:

- `{workflow_name}` — top-level context key
- `{fetch_issues.count}` — nested access into a step's output
- `{fetch_issues.issues[0].title}` — array index access

Templates work in: claude step prompts, shell commands, HTTP URLs and bodies, query SQL strings, and transform expressions.

Example claude step config:

```json
{
  "type": "claude",
  "config": {
    "prompt": "Summarize these {fetch_issues.count} issues:\n{fetch_issues.issues}",
    "model": "sonnet"
  }
}
```

## Best Practices

1. **Keep steps small and focused.** One operation per step. If a step does two things, split it.

2. **Use transform steps to reshape data.** When one step's output format does not match what the next step expects, insert a transform step rather than coupling the steps.

3. **Use gate steps for branching.** Do not embed complex conditionals in script steps. Use a gate step to make the decision and let the DAG handle routing.

4. **Test steps independently.** Every step script can be tested by piping JSON on the command line:
   ```bash
   echo '{"input_key": "test_value"}' | python ~/.liteflow/steps/my-workflow/my_step.py
   ```

5. **Use the claude step type for judgment, not computation.** LLM steps are for classification, summarization, and reasoning. Use script or transform steps for deterministic data processing.

6. **Never hardcode credentials.** Store API tokens and secrets via SecureStore (`python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py auth set --service <name>`). Access them in scripts via `from liteflow.helpers import SecureStore`.

7. **Use --dry-run first.** Validate the workflow graph and credentials before live execution:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py run <workflow-name> --dry-run
   ```

8. **Name steps descriptively.** Step IDs become context keys. Use names like `fetch_issues`, `filter_critical`, `send_notification` — not `step1`, `step2`, `step3`.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/workflow-building/references/step-contract.md` — Full step contract specification with advanced patterns
- `${CLAUDE_PLUGIN_ROOT}/skills/workflow-building/references/step-types.md` — Complete step type reference with configuration details
