# Script, Shell, and Claude Steps

Detailed reference for the three "execution" step types that run external processes. These steps invoke subprocesses -- a Python script, a shell command/file, or the Claude CLI -- and capture their output back into the workflow context.

All three share the same output convention: stdout is parsed as JSON if possible, with type-specific fallbacks when it is not valid JSON.

---

## Script Step

Runs a Python script file that follows the [step contract](index.md). The script receives context as JSON on stdin and writes JSON to stdout.

### Config Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | yes | -- | Must be `"script"` |
| `script` | string | yes | -- | Path to Python file (relative to `~/.liteflow/` or absolute) |
| `timeout` | int | no | 300 | Timeout in seconds |

### Execution

1. **Resolve path** -- if `script` is a relative path, it is resolved relative to the liteflow home directory (`~/.liteflow/`). Absolute paths and paths starting with `~` are expanded directly.
2. **Check existence** -- raises `FileNotFoundError` if the resolved path does not exist.
3. **Run subprocess** -- executes `python3 <script>` with the full context dict piped as JSON to stdin. The working directory is set to the script's parent directory.
4. **Check exit code** -- non-zero exit code raises `RuntimeError` with the script's stderr.
5. **Parse stdout** -- attempts to parse stdout as JSON. If parsing fails, returns `{"output": <raw_text>}`. If stdout is empty, returns `{}`.

### Example Config

```json
{
  "id": "fetch-prs",
  "type": "script",
  "script": "steps/morning-briefing/fetch_prs.py",
  "timeout": 60
}
```

### Example Script (steps/fetch_prs.py)

```python
import json, sys

def run(context):
    repo = context.get("repo", "owner/repo")
    # ... fetch PRs via API ...
    return {"prs": [...], "pr_count": 5}

if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    json.dump(run(ctx), sys.stdout)
```

The `run(context)` function is a convention for testability -- the `if __name__` block handles the actual stdin/stdout contract that the engine uses.

### Template Substitution

Template substitution is **not** applied to script step configs. The script receives the raw context dict via stdin and is responsible for extracting values itself.

---

## Shell Step

Runs a shell command (inline) or a shell script file. Context values are injected as environment variables.

### Config Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | yes | -- | Must be `"shell"` |
| `command` | string | conditional | -- | Inline shell command (mutually exclusive with `file`) |
| `file` | string | conditional | -- | Path to `.sh` script (mutually exclusive with `command`) |
| `args` | list | no | `[]` | Arguments for file mode (supports `{variable}` templating) |
| `timeout` | int | no | 120 | Timeout in seconds |

You must provide exactly one of `command` or `file`.

### Two Modes

#### Inline Mode

The `command` string is template-substituted, then run via `subprocess.run()` with `shell=True`. The working directory is the liteflow home directory (`~/.liteflow/`).

```json
{
  "id": "check-branch",
  "type": "shell",
  "command": "gh pr diff {pr_number} --repo {repo}"
}
```

#### File Mode

The script file is run via `bash <file> <args...>`. Each entry in the `args` list is template-substituted before being passed. The working directory is set to the script file's parent directory.

```json
{
  "id": "fetch-diff",
  "type": "shell",
  "file": "steps/pr-review/fetch_diff.sh",
  "args": ["{pr_url}"]
}
```

If `file` is a relative path, it is resolved relative to `~/.liteflow/`. Raises `FileNotFoundError` if the resolved path does not exist.

### Environment Variables Injected

Both modes inject environment variables into the subprocess:

| Variable | Value |
|----------|-------|
| `LITEFLOW_RUN_ID` | The current run ID |
| `LITEFLOW_CONTEXT` | Full context dict serialized as a JSON string |
| `LITEFLOW_{KEY}` | For each **scalar** top-level context value (str, int, float, bool), with the key uppercased |

Nested dicts and lists are not promoted to individual environment variables -- use `LITEFLOW_CONTEXT` with `jq` or similar to access them.

Example: given context `{"user": "jared", "count": 5, "fetch-data": {"rows": [...]}}`:

```bash
echo $LITEFLOW_RUN_ID       # abc123def456
echo $LITEFLOW_USER          # jared
echo $LITEFLOW_COUNT         # 5
echo $LITEFLOW_CONTEXT | jq '.["fetch-data"].rows[0].title'
```

### Error Handling

Non-zero exit code raises `RuntimeError` with the command's stderr.

### Output Parsing

1. Tries to parse stdout as JSON.
2. If JSON parsing fails, returns `{"stdout": <raw_text>, "exit_code": 0}`.

---

## Claude Step

Invokes the Claude CLI (`claude -p <prompt>`) with a template-substituted prompt. Use this step type when you need LLM judgment -- text analysis, generation, classification, or summarization.

### Config Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | yes | -- | Must be `"claude"` |
| `prompt` | string | yes | -- | Prompt template (supports `{variable}` substitution) |
| `timeout` | int | no | 120 | Subprocess timeout in seconds |
| `parse_json` | bool | no | `false` | Use `--output-format json` and parse structured output |
| `flags` | dict | no | `{}` | Arbitrary CLI flags passed to `claude` |

### The Flags Dict

The `flags` dict is converted to CLI arguments. Template substitution is applied to string values.

| Value Type | Example Config | CLI Result |
|------------|---------------|------------|
| String | `{"model": "opus"}` | `--model opus` |
| Integer | `{"max-turns": 3}` | `--max-turns 3` |
| Boolean (true) | `{"verbose": true}` | `--verbose` |
| Boolean (false) | `{"verbose": false}` | *(omitted)* |
| List | `{"allowedTools": ["Read", "Grep"]}` | `--allowedTools Read Grep` |

Common flags:

- `model` -- which Claude model to use (e.g., `"sonnet"`, `"opus"`)
- `max-turns` -- limit the number of agentic turns
- `permission-mode` -- permission handling mode
- `allowedTools` -- restrict which tools Claude can use
- `append-system-prompt` -- add text to the system prompt
- `verbose` -- enable verbose output

Keys that do not start with `-` are automatically prefixed with `--`.

### Output Handling

#### Without `parse_json` (default)

Returns `{"response": "<Claude's text response>"}`.

#### With `parse_json: true`

1. Adds `--output-format json` to the CLI invocation.
2. Parses the structured JSON response from Claude.
3. If the parsed object contains a `result` field, tries to parse that field's value as JSON in turn (since `--output-format json` wraps the actual response in a structured envelope).
4. If the `result` field is not valid JSON, returns `{"response": <result_text>}`.
5. If the top-level parse fails, falls back to extracting JSON from the freeform text via regex (`\{[\s\S]*\}`).
6. If all parsing fails, returns `{"response": <raw_text>}`.

### Max-Turns Edge Case

When Claude hits the `--max-turns` limit, the subprocess exits with code 1 and includes "Reached max turns" in the output. Rather than failing the step, the engine extracts the actual response (everything before the error line) and returns it normally. This means workflows using `max-turns` to cap cost will still capture Claude's partial work.

### Example

```json
{
  "id": "summarize",
  "type": "claude",
  "prompt": "Summarize these GitHub items for {user}:\n\nPRs: {fetch-prs.prs}\nIssues: {fetch-issues.issues}",
  "parse_json": true,
  "flags": {
    "model": "sonnet",
    "max-turns": 1
  }
}
```

With this config, the engine:

1. Template-substitutes `{user}`, `{fetch-prs.prs}`, and `{fetch-issues.issues}` from context
2. Builds the command: `claude -p "<substituted prompt>" --output-format json --model sonnet --max-turns 1`
3. Runs the subprocess with a 120-second timeout
4. Parses the structured JSON response

---

## When to Use Each

| Scenario | Step Type | Why |
|----------|-----------|-----|
| Custom data processing logic | script | Full Python environment, testable independently, can import libraries |
| Quick CLI tool invocation | shell (inline) | One-liner, uses existing CLI tools like `gh`, `curl`, `jq` |
| Complex shell workflow | shell (file) | Multi-step scripts, version-controlled alongside the workflow |
| Text analysis or generation | claude | LLM judgment, natural language processing, non-deterministic reasoning |
| Classification or summarization | claude (`parse_json`) | Structured LLM output you can route on downstream |

### Choosing Between Script and Shell

- **Script** if you need to import Python libraries, handle complex data structures, or want to unit test the logic independently.
- **Shell (inline)** if you are calling a single CLI command and just need the output.
- **Shell (file)** if you need multiple shell commands chained together or want the script version-controlled.

### Choosing Between Script and Claude

- **Script** when the logic is deterministic -- parsing, filtering, API calls with known schemas.
- **Claude** when you need judgment -- summarizing text, classifying content, generating natural language, or making decisions that would be hard to express as code.

---

## See Also

- [Step Types Overview](index.md) -- step type overview and the step contract
- [Query, HTTP, and Transform Steps](query-http-transform.md) -- data step types
- [Gate, Fan-Out, and Fan-In Steps](gate-fanout-fanin.md) -- flow control step types
- [Context and Data Flow](../../concepts/context-and-data-flow.md) -- template substitution details and context accumulation
- [Documentation Home](../../index.md)
