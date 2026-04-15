# Step Contract Reference

## Contract Specification

Every liteflow step is a standalone Python file that implements one function:

```python
def run(context: dict) -> dict
```

### Input

The `context` parameter is a JSON-deserialized dictionary containing:

- **Initial run context**: Key-value pairs passed when the workflow was started.
- **Accumulated step outputs**: Each completed step's output is stored under its step ID. For example, if step `fetch_data` returned `{"items": [...]}`, subsequent steps see `context["fetch_data"]["items"]`.

The context is delivered via stdin as a JSON string. The `__main__` guard handles deserialization:

```python
if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
```

### Output

The `run` function returns a dictionary. This dictionary is merged into the run context under the step's ID. Return only the data downstream steps need — keep output lean.

```python
def run(context: dict) -> dict:
    # Good: return specific, named outputs
    return {
        "count": 42,
        "items": [{"id": 1, "title": "First"}],
        "status": "complete"
    }
```

Output is captured from stdout. Do not print debug output to stdout — use stderr or the RunLogger helper instead.

### Error Handling

Raise an exception to signal step failure. The engine captures the exception message and traceback, marks the step as failed, and halts the workflow (unless the step is configured with `continue_on_error: true`).

```python
def run(context: dict) -> dict:
    if "required_key" not in context:
        raise ValueError("Missing required_key in context — ensure fetch_data step ran first")
    
    try:
        result = call_external_api(context["api_url"])
    except ConnectionError as e:
        raise RuntimeError(f"API unreachable at {context['api_url']}: {e}")
    
    return {"api_result": result}
```

Write descriptive error messages. Include what was expected, what was received, and which prior step should have produced the missing data.

## Annotated Full Example

```python
"""
Step: filter_critical_issues
Filters issues to only those with severity >= critical.

Expects context from: fetch_issues (must produce 'issues' list)
Produces: filtered list and count for downstream steps
"""
import json
import sys

def run(context: dict) -> dict:
    # 1. Extract input from prior step
    issues = context.get("fetch_issues", {}).get("issues", [])
    if not issues:
        raise ValueError(
            "No issues found in context['fetch_issues']['issues']. "
            "Ensure the fetch_issues step completed successfully."
        )
    
    # 2. Perform the step's single operation
    critical = [i for i in issues if i.get("severity", "low") in ("critical", "high")]
    
    # 3. Return structured output
    return {
        "issues": critical,
        "count": len(critical),
        "original_count": len(issues),
        "filter_applied": "severity >= critical"
    }

if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
```

## Testing Steps

Test any step script by piping JSON on the command line:

```bash
# Basic test
echo '{"fetch_issues": {"issues": [{"id": 1, "severity": "critical"}]}}' | python filter_critical.py

# Test with empty input
echo '{}' | python filter_critical.py  # Should raise ValueError

# Test with file input
python filter_critical.py < test_context.json

# Pipe steps together for integration testing
echo '{"repo": "my-org/my-repo"}' | python fetch_issues.py | python filter_critical.py
```

## Advanced Patterns

### Using StepContext Helper

The `StepContext` helper provides convenience methods for common operations:

```python
from liteflow.helpers import StepContext

def run(context: dict) -> dict:
    ctx = StepContext(context)
    
    # Safe nested access with defaults
    issues = ctx.get("fetch_issues.issues", default=[])
    threshold = ctx.get("config.threshold", default=10)
    
    # Access credentials
    api_key = ctx.credential("github")
    
    return {"processed": len(issues)}
```

### Using HTTPStep for API Calls

The `HTTPStep` helper handles HTTP requests with retry, timeout, and error handling — all zero-dependency via urllib:

```python
from liteflow.helpers import HTTPStep

def run(context: dict) -> dict:
    http = HTTPStep()
    
    # GET request
    response = http.get(
        "https://api.github.com/repos/{owner}/{repo}/issues",
        headers={"Authorization": f"token {context['github_token']}"},
        params={"state": "open", "per_page": 100}
    )
    
    # POST request
    result = http.post(
        "https://api.example.com/webhook",
        json_body={"event": "workflow_complete", "data": context["summary"]}
    )
    
    return {"issues": response, "webhook_status": result["status"]}
```

### Using RunLogger for Structured Logging

Log to stderr (not stdout) for debug output. RunLogger writes structured JSON logs:

```python
from liteflow.helpers import RunLogger

def run(context: dict) -> dict:
    log = RunLogger("my_step")
    
    log.info("Starting processing", item_count=len(context.get("items", [])))
    log.debug("Full context keys", keys=list(context.keys()))
    
    try:
        result = process(context["items"])
        log.info("Processing complete", result_count=len(result))
    except Exception as e:
        log.error("Processing failed", error=str(e))
        raise
    
    return {"result": result}
```

### Using SecureStore for Credentials

Never hardcode API tokens or secrets. Use SecureStore to retrieve credentials stored via the CLI:

```python
from liteflow.helpers import SecureStore

def run(context: dict) -> dict:
    store = SecureStore()
    token = store.get("github")  # Retrieves token for "github" service
    
    if not token:
        raise RuntimeError(
            "No GitHub credential found. "
            "Run: python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py auth set --service github"
        )
    
    # Use token in API calls
    return {"authenticated": True}
```

### Multiple Return Values and Nested Structures

Return as much structured data as downstream steps need, but no more:

```python
def run(context: dict) -> dict:
    return {
        "summary": {
            "total": 100,
            "passed": 95,
            "failed": 5,
            "pass_rate": 0.95
        },
        "failures": [
            {"test": "test_login", "error": "timeout"},
            {"test": "test_upload", "error": "permission denied"}
        ],
        "metadata": {
            "run_duration_seconds": 45,
            "timestamp": "2025-01-15T10:30:00Z"
        }
    }
```

Downstream steps access nested values: `context["test_runner"]["summary"]["pass_rate"]`.

### Idempotency Considerations

Design steps to be safely re-runnable:

- **Read operations** are naturally idempotent — no special handling needed.
- **Write operations** should check for existing state before writing. Use upsert patterns or check-then-act with appropriate guards.
- **API calls with side effects** (sending emails, creating records) should include deduplication keys or check for prior completion.
- Store a `_completed_at` timestamp in output so re-runs can detect prior completion:

```python
import datetime

def run(context: dict) -> dict:
    # Check if this step already ran (re-run scenario)
    prior = context.get("send_notification", {})
    if prior.get("_completed_at"):
        return prior  # Return cached result
    
    send_email(context["recipient"], context["message"])
    
    return {
        "sent": True,
        "_completed_at": datetime.datetime.utcnow().isoformat()
    }
```
