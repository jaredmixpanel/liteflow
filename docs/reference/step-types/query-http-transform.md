# Query, HTTP, and Transform Steps

The three "data" step types for reading databases, calling APIs, and reshaping data between steps. All three are lightweight -- they require no external dependencies and no separate script files.

---

## Query Step

Runs SQL against a SQLite database. Useful for reading or writing liteflow's own databases (workflows, execution history, config) or any other SQLite file.

### Config Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | yes | -- | Must be `"query"` |
| `database` | string | yes | -- | Path to SQLite DB (supports `{variable}` templating, relative to `~/.liteflow/` or absolute) |
| `sql` | string | yes | -- | SQL query (supports `{variable}` templating) |
| `params` | list | no | `[]` | Parameterized query values (passed to `cursor.execute()` as positional args) |

### Output

The output shape depends on the SQL statement type:

- **SELECT queries**: `{"rows": [{"col1": val, ...}, ...], "count": N}`
- **INSERT / UPDATE / DELETE**: `{"rowcount": N}`

SELECT results use `sqlite3.Row` as the row factory, so each row is returned as a dict keyed by column name.

### Database Path Resolution

The `database` value is resolved in this order:

1. `Path(database).expanduser()` -- tilde expansion is applied first.
2. If the result is not an absolute path, it is joined with the liteflow home directory (`~/.liteflow/`).

This means you can use:
- `"execution.db"` -- resolves to `~/.liteflow/execution.db`
- `"~/other/data.db"` -- resolves to the absolute path after tilde expansion
- `"/absolute/path/to/db.sqlite"` -- used as-is

### Template Substitution

Both `database` and `sql` are template-substituted before execution. The `params` list is passed through unchanged -- use `params` with `?` placeholders in the SQL for safe parameterized queries rather than templating user-supplied values directly into SQL strings.

### Example

```json
{
  "id": "check-stale-runs",
  "type": "query",
  "database": "execution.db",
  "sql": "SELECT id, workflow_id, started_at FROM runs WHERE status = 'running' AND started_at < datetime('now', '-1 hour')"
}
```

Output:

```json
{
  "rows": [
    {
      "id": "run-abc123",
      "workflow_id": "daily-cleanup",
      "started_at": "2025-01-15T08:30:00"
    }
  ],
  "count": 1
}
```

### Example: Parameterized Query

```json
{
  "id": "find-user-runs",
  "type": "query",
  "database": "execution.db",
  "sql": "SELECT * FROM runs WHERE workflow_id = ? AND status = ?",
  "params": ["daily-report", "completed"]
}
```

### Example: Write Operation

```json
{
  "id": "mark-complete",
  "type": "query",
  "database": "execution.db",
  "sql": "UPDATE runs SET status = 'cancelled' WHERE id = '{stale-run-id}'"
}
```

Output: `{"rowcount": 1}`

---

## HTTP Step

Makes HTTP requests using Python's `urllib` (zero external dependencies). Supports service name resolution and automatic credential injection for common APIs.

### Config Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | yes | -- | Must be `"http"` |
| `url` | string | yes | -- | Full URL or service name (e.g., `"github"`, `"slack"`) |
| `method` | string | no | `"GET"` | HTTP method: `GET`, `POST`, `PUT`, `DELETE` |
| `endpoint` | string | no | `""` | API endpoint path appended to the resolved base URL |
| `headers` | dict | no | `{}` | Request headers |
| `body` | dict/string | no | `null` | Request body (JSON-encoded, supports templating) |

### URL Resolution

When `url` does not start with `http://` or `https://`, it is treated as a service name and resolved in this order:

1. **SecureStore lookup** -- check the credentials database for a stored `base_url` for that service.
2. **Built-in SERVICE_URLS** -- fall back to the hardcoded service URL map:

| Service | Base URL |
|---------|----------|
| `github` | `https://api.github.com` |
| `slack` | `https://slack.com/api` |
| `jira` | `https://your-domain.atlassian.net/rest/api/3` |
| `notion` | `https://api.notion.com/v1` |
| `linear` | `https://api.linear.app/graphql` |
| `sendgrid` | `https://api.sendgrid.com/v3` |
| `openai` | `https://api.openai.com/v1` |
| `anthropic` | `https://api.anthropic.com/v1` |

3. The `endpoint` path is appended after a `/` separator.

If the service name cannot be resolved through either method, a `ValueError` is raised.

### Auto-Auth Injection

When using a service name (not a full URL) and credentials are stored in the SecureStore, `HTTPStep._inject_auth()` automatically adds authorization headers. Auth injection is **skipped** if:

- The `url` starts with `http://` or `https://` (treated as a raw URL, not a service name).
- An `Authorization` or `authorization` header is already present in the config.
- No token is found in the SecureStore for the service.

Service-specific header formats:

| Service | Headers Added |
|---------|---------------|
| `github` | `Authorization: token {token}`, `Accept: application/vnd.github.v3+json` |
| `anthropic` | `x-api-key: {token}`, `anthropic-version: 2023-06-01` |
| `slack` | `Authorization: Bearer {token}` |
| *(all others)* | `Authorization: Bearer {token}` |

### Body Templating

The `body` field supports template substitution with two paths depending on its type:

- **String body**: template-substituted, then parsed as JSON. If JSON parsing fails, the string is sent as-is.
- **Dict body**: serialized to JSON, template-substituted on the JSON string, then parsed back to a dict.

This means `{variable}` placeholders in body values are resolved from the workflow context before the request is made.

### Response Handling

- Successful responses are parsed as JSON and returned as a dict.
- Empty response bodies return `{"status": <code>, "ok": true}`.
- Non-JSON responses return `{"status": <code>, "body": "<raw text>"}`.
- HTTP errors raise `urllib.error.HTTPError` with the response body included in the error message.

### Timeout

All HTTP requests have a **30-second timeout**, hardcoded in `HTTPStep._request()`.

### Examples

**Simple GET request with service name:**

```json
{
  "id": "fetch-user",
  "type": "http",
  "url": "github",
  "endpoint": "/user",
  "method": "GET"
}
```

**POST with templated body:**

```json
{
  "id": "post-message",
  "type": "http",
  "url": "slack",
  "endpoint": "/chat.postMessage",
  "method": "POST",
  "body": {
    "channel": "{slack_channel}",
    "text": "Build complete: {build-step.status}"
  }
}
```

**Full URL with custom headers (no auto-auth):**

```json
{
  "id": "call-webhook",
  "type": "http",
  "url": "https://hooks.example.com/notify",
  "method": "POST",
  "headers": {
    "X-Webhook-Secret": "abc123"
  },
  "body": {
    "event": "workflow_complete",
    "run_id": "{_run_id}"
  }
}
```

**PUT request:**

```json
{
  "id": "update-issue",
  "type": "http",
  "url": "github",
  "endpoint": "/repos/{repo_owner}/{repo_name}/issues/{issue_number}",
  "method": "PUT",
  "body": {
    "state": "closed",
    "labels": ["automated"]
  }
}
```

---

## Transform Step

Evaluates a Python expression with the full context available. Designed for reshaping data between steps without writing a separate script file.

### Config Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | yes | -- | Must be `"transform"` |
| `expression` | string | yes | -- | Python expression to evaluate |

### Eval Environment

Transform expressions run in a restricted `eval()` with a limited set of builtins and no access to file I/O, imports, or arbitrary attribute access.

**Safe builtins available:**

| Category | Names |
|----------|-------|
| Type constructors | `str`, `int`, `float`, `bool`, `list`, `dict`, `tuple` |
| Ordering | `sorted`, `reversed` |
| Aggregation | `len`, `min`, `max`, `sum`, `abs`, `round` |
| Boolean | `any`, `all` |
| Iteration | `zip`, `enumerate`, `range` |
| Constants | `True`, `False`, `None` |

**Modules:**

| Name | Description |
|------|-------------|
| `json` | The `json` standard library module (for `json.dumps()`, `json.loads()`, etc.) |

**Local variables:**

| Name | Description |
|------|-------------|
| `context` | The full context dict |
| `ctx` | A `StepContext` wrapper with dot-path access via `ctx.get("key.nested")` |
| *(top-level keys)* | All top-level context keys are injected as local variables (e.g., if context has `"user": "jared"`, then `user` is available directly) |

### Output

- If the expression evaluates to a **dict**, it is returned as the step output directly.
- If it evaluates to **anything else**, it is wrapped as `{"result": <value>}`.

### Template Substitution Does Not Apply

Transform expressions are **not** template-substituted. The `{variable}` syntax is not used here. Instead, access context values directly via:

- `context['key']` -- standard dict access
- `ctx.get('key.nested.path')` -- dot-path access with default
- Top-level variable names -- e.g., `user` instead of `context['user']`

This distinction is important: template substitution produces strings, while eval expressions work with native Python types (lists, dicts, numbers, booleans).

### Examples

**Extract a list of values:**

```json
{
  "id": "extract-titles",
  "type": "transform",
  "expression": "[r['title'] for r in context['fetch-prs']['prs']]"
}
```

Output: `{"result": ["Fix bug", "Add feature", ...]}`

**Return a dict (no wrapping):**

```json
{
  "id": "summarize-data",
  "type": "transform",
  "expression": "{'total': len(context['fetch-data']['rows']), 'filtered': [r for r in context['fetch-data']['rows'] if r['status'] == 'open']}"
}
```

Output: `{"total": 10, "filtered": [...]}`

**Use the StepContext helper:**

```json
{
  "id": "safe-count",
  "type": "transform",
  "expression": "{'count': ctx.get('fetch-data.count', default=0), 'has_data': ctx.get('fetch-data.count', default=0) > 0}"
}
```

Output: `{"count": 5, "has_data": true}`

**Use the json module:**

```json
{
  "id": "serialize-report",
  "type": "transform",
  "expression": "{'payload': json.dumps({'summary': ctx.get('report.response'), 'count': ctx.get('fetch-data.count')})}"
}
```

Output: `{"payload": "{\"summary\": \"...\", \"count\": 5}"}`

**Use top-level context variables directly:**

```json
{
  "id": "format-greeting",
  "type": "transform",
  "expression": "{'message': f'Hello {user}, you have {len(context[\"fetch-data\"][\"rows\"])} items'}"
}
```

If context contains `{"user": "jared", "fetch-data": {"rows": [...]}}`, the variable `user` is available directly because it is a top-level context key.

---

## When to Use Each

| Scenario | Step Type | Why |
|----------|-----------|-----|
| Read/write liteflow's own databases | query | Direct access to workflow, execution, or config data |
| Read/write any SQLite database | query | Generic SQL capability |
| Call an external REST API | http | Auto-auth, service name resolution |
| Post to Slack/GitHub/etc. | http | Built-in service support with credential injection |
| Reshape data between steps | transform | Lightweight, no separate file needed |
| Filter, sort, or aggregate data | transform | Python expression power with safe builtins |
| Complex data processing | script | When a transform expression becomes unwieldy |

### Decision Guide

Use **query** when your data lives in SQLite. Use **http** when your data lives behind a REST API. Use **transform** when you need to reshape data that is already in the context.

If a transform expression grows beyond a single line or needs imports beyond `json`, consider moving the logic to a **script** step instead. Transform is designed for concise reshaping, not general-purpose computation.

---

## See Also

- [Step Types Overview](index.md) -- all step types at a glance
- [Script, Shell, and Claude Steps](script-shell-claude.md) -- execution step types
- [Gate, Fan-Out, and Fan-In Steps](gate-fanout-fanin.md) -- flow control step types
- [Credentials Setup](../../getting-started/credentials.md) -- storing API tokens for HTTP auto-auth
- [Context and Data Flow](../../concepts/context-and-data-flow.md) -- template substitution rules and eval scope details
- [Documentation Home](../../index.md)
