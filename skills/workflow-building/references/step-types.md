# Step Types Reference

This document covers all 9 liteflow step types with their configuration, behavior, and examples.

---

## script

Executes a Python file that follows the step contract.

**When to use**: Custom logic, data processing, complex API integrations, anything that needs full Python expressiveness.

**Required config**:
- `file`: Path to the Python script (relative to `~/.liteflow/steps/<workflow>/` or absolute)

**Optional config**:
- `timeout`: Maximum execution time in seconds (default: 300)
- `continue_on_error`: Boolean, continue workflow on failure (default: false)

**Example definition**:
```json
{
  "id": "fetch_issues",
  "type": "script",
  "config": {
    "file": "fetch_issues.py",
    "timeout": 60
  }
}
```

**Example script** (`fetch_issues.py`):
```python
import json, sys
from liteflow.helpers import StepContext, HTTPStep, SecureStore

def run(context: dict) -> dict:
    store = SecureStore()
    token = store.get("github")
    http = HTTPStep()
    issues = http.get(
        f"https://api.github.com/repos/{context['repo']}/issues",
        headers={"Authorization": f"token {token}"}
    )
    return {"issues": issues, "count": len(issues)}

if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    json.dump(run(ctx), sys.stdout)
```

**Output**: The dict returned by `run()` is merged into context under the step ID.

---

## shell

Executes a shell command. Context values are injected as environment variables.

**When to use**: System commands, file operations, CLI tools, quick one-liners that do not need Python.

**Required config**:
- `command`: Shell command string (supports template substitution)

**Optional config**:
- `timeout`: Maximum execution time in seconds (default: 120)
- `shell`: Shell to use (default: `/bin/sh`)
- `continue_on_error`: Boolean (default: false)

**Example definition**:
```json
{
  "id": "count_files",
  "type": "shell",
  "config": {
    "command": "find {target_dir} -name '*.py' | wc -l"
  }
}
```

**Output**: Captured as `{"stdout": "...", "stderr": "...", "exit_code": 0}`. Nonzero exit codes are treated as failures unless `continue_on_error` is true.

---

## claude

Sends a templated prompt to Claude and captures the response.

**When to use**: Judgment calls, text generation, classification, summarization — tasks requiring reasoning, not computation.

**Required config**:
- `prompt`: Prompt string with `{variable}` template placeholders

**Optional config**:
- `model`: Model to use (default: `sonnet`). Values: `haiku`, `sonnet`, `opus`
- `system`: System prompt string
- `max_tokens`: Maximum response tokens (default: 4096)
- `temperature`: Sampling temperature (default: 0.0)
- `response_format`: `text` or `json` (default: `text`). When `json`, the response is parsed as JSON.

**Example definition**:
```json
{
  "id": "classify_issues",
  "type": "claude",
  "config": {
    "prompt": "Classify each issue as bug, feature, or chore:\n\n{fetch_issues.issues}",
    "model": "haiku",
    "response_format": "json",
    "system": "Return a JSON array of objects with 'id' and 'category' fields."
  }
}
```

**Output**: `{"response": "..."}` for text format, or the parsed JSON object directly for json format.

---

## query

Executes SQL against any SQLite database.

**When to use**: Reading or writing structured data in liteflow databases or any local SQLite file.

**Required config**:
- `sql`: SQL statement (supports template substitution)

**Optional config**:
- `database`: Path to SQLite database (default: `~/.liteflow/execution.db`)
- `params`: List of bind parameters
- `single_row`: Boolean, return only the first row (default: false)

**Example definition**:
```json
{
  "id": "get_recent_runs",
  "type": "query",
  "config": {
    "sql": "SELECT * FROM runs WHERE workflow = '{workflow_name}' ORDER BY started_at DESC LIMIT 10",
    "database": "~/.liteflow/execution.db"
  }
}
```

**Output**: `{"rows": [...], "row_count": N, "columns": [...]}`. Each row is a dict keyed by column name.

---

## http

Makes an HTTP request using urllib (zero external dependencies).

**When to use**: Simple REST API calls, webhooks, health checks — when you do not need complex auth flows or pagination.

**Required config**:
- `url`: Request URL (supports template substitution)

**Optional config**:
- `method`: HTTP method (default: `GET`)
- `headers`: Dict of headers (supports template substitution in values)
- `body`: Request body string or dict (dict is JSON-encoded automatically)
- `timeout`: Request timeout in seconds (default: 30)
- `expected_status`: Expected HTTP status code (default: 200). Other codes are treated as errors.

**Example definition**:
```json
{
  "id": "notify_slack",
  "type": "http",
  "config": {
    "url": "https://hooks.slack.com/services/{slack_webhook_path}",
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "body": {"text": "Workflow completed: {workflow_name}"}
  }
}
```

**Output**: `{"status": 200, "body": "...", "headers": {...}}`. The body is parsed as JSON if the response Content-Type is `application/json`.

---

## transform

Evaluates a Python expression to reshape data. No script file needed.

**When to use**: Reformatting, filtering, mapping, or combining data between steps. Use instead of writing a full script for simple data transformations.

**Required config**:
- `expression`: Python expression evaluated with `context` in scope. Must return a dict.

**Optional config**:
- `imports`: List of modules to import before evaluating (default: `[]`)

**Example definition**:
```json
{
  "id": "extract_titles",
  "type": "transform",
  "config": {
    "expression": "{\"titles\": [i['title'] for i in context['fetch_issues']['issues']], \"count\": context['fetch_issues']['count']}"
  }
}
```

**Output**: The dict returned by the expression is merged into context under the step ID.

---

## gate

Evaluates a condition and produces a boolean result for routing.

**When to use**: Conditional branching in the workflow. Use gate steps instead of embedding conditionals in script steps — it keeps decision logic visible in the DAG.

**Required config**:
- `condition`: Python expression evaluated against context. Must be truthy/falsy.

**Optional config**:
- `description`: Human-readable description of what the gate decides

**Example definition**:
```json
{
  "id": "check_threshold",
  "type": "gate",
  "config": {
    "condition": "context['fetch_issues']['count'] > 10",
    "description": "Route to bulk processing if more than 10 issues"
  }
}
```

**Edges from gate steps**: Use `when_true` and `when_false` on outgoing edges:
```json
[
  {"from": "check_threshold", "to": "bulk_process", "when_true": true},
  {"from": "check_threshold", "to": "single_process", "when_false": true}
]
```

**Output**: `{"_gate_result": true, "condition": "...", "description": "..."}` or `{"_gate_result": false, ...}`.

---

## fan-out

Splits an array in the context into individual items for parallel processing.

**When to use**: Process each element of a collection independently — API calls per item, per-record transformation, batch operations.

**Required config**:
- `source`: Dot-path to the array in context (e.g., `fetch_issues.issues`)
- `item_key`: Key name for each item in the sub-context (e.g., `issue`)

**Optional config**:
- `max_parallel`: Maximum concurrent executions (default: 5)
- `continue_on_error`: Continue processing remaining items if one fails (default: false)

**Example definition**:
```json
{
  "id": "split_issues",
  "type": "fan-out",
  "config": {
    "source": "fetch_issues.issues",
    "item_key": "issue",
    "max_parallel": 3
  }
}
```

**Behavior**: For each item in the source array, the engine runs the downstream steps (between fan-out and its paired fan-in) with the item injected into context under `item_key`. Each parallel branch receives `context["issue"]` containing one issue.

**Output**: `{"_fan_out": true, "item_count": N, "source": "fetch_issues.issues"}`.

---

## fan-in

Collects results from parallel fan-out branches.

**When to use**: Always paired with a fan-out step. Aggregates parallel results back into a single array.

**Required config**:
- `fan_out_step`: ID of the paired fan-out step
- `collect_key`: Key under which to collect results (e.g., `results`)

**Optional config**:
- `merge_strategy`: How to merge results. `list` (default) collects into an array. `merge` merges all dicts into one.

**Example definition**:
```json
{
  "id": "collect_results",
  "type": "fan-in",
  "config": {
    "fan_out_step": "split_issues",
    "collect_key": "processed_issues",
    "merge_strategy": "list"
  }
}
```

**Output**: `{"processed_issues": [...], "item_count": N, "failed_count": 0}`. The `processed_issues` array contains one entry per fan-out branch, each being the accumulated output from that branch's steps.
