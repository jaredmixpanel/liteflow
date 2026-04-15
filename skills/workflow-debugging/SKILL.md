---
name: workflow-debugging
description: "Use this skill when a liteflow workflow fails, produces unexpected results, has stuck runs, encounters step errors, credential issues, or queue problems. Also use when the user asks to debug, inspect, troubleshoot, or fix a workflow execution."
---

# Debugging Liteflow Workflows

## Inspection Workflow

When a workflow fails or produces unexpected results, follow this systematic process:

### 1. Get the Run Details

Run the inspect command to see the full execution record:

```bash
python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py inspect <run-id>
```

This shows: workflow name, run status, start/end timestamps, initial context, each step's status (pending/running/completed/failed), each step's input context and output, and the error message and traceback for any failed step.

If you do not have the run ID, list recent runs:

```bash
python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py history --workflow <workflow-name> --limit 10
```

### 2. Identify the Failed Step

Look for the first step with status `failed` in the inspect output. Note:
- The step ID and type
- The input context it received
- The error message and traceback
- Which prior step's output it depended on

### 3. Examine the Step

Read the step script to understand what it was trying to do:
- For `script` steps: read the Python file at `~/.liteflow/steps/<workflow>/<step-id>.py`
- For `shell` steps: examine the command in the workflow definition
- For `claude` steps: check the prompt template and whether substitution succeeded
- For `http` steps: verify the URL, method, and headers
- For `transform`/`gate` steps: examine the expression and the context values it references

### 4. Classify the Error

Determine the root cause category:
- **Step logic error**: Bug in the step script itself
- **Input data error**: Prior step produced unexpected output shape or missing keys
- **External service error**: API down, rate-limited, or returning unexpected responses
- **Credential error**: Expired token, wrong scopes, missing credential
- **Template error**: Variable substitution failed due to missing context key
- **Configuration error**: Wrong step type, missing required config fields

Refer to `${CLAUDE_PLUGIN_ROOT}/skills/workflow-debugging/references/error-patterns.md` for the full error catalog with symptoms, causes, and fixes.

## Common Failure Patterns

### Authentication Failures

Symptoms: HTTP 401/403, "unauthorized", "token expired", "insufficient scopes".

Diagnose:
```bash
python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py auth test --service <service-name>
```

Fix: Re-authenticate via the CLI or update the stored credential.

### Data Shape Mismatches

Symptoms: `TypeError`, `KeyError`, "expected list got dict", "NoneType has no attribute".

Diagnose: Compare the failed step's input context against what it expects. Inspect the prior step's output to see the actual shape.

Fix: Add a `transform` step between the producer and consumer to reshape the data, or fix the producing step's output.

### Missing Context Keys

Symptoms: `KeyError: '<key>'`, "NoneType object is not subscriptable".

Diagnose: Check if the prior step that should produce the key actually ran and succeeded. Verify the key name — step outputs are namespaced by step ID.

Fix: Correct the key path (e.g., `context['fetch_data']['items']` not `context['items']`), or add a default value with `.get()`.

### Template Substitution Failures

Symptoms: "KeyError in template", unresolved `{variable}` in executed command/prompt, `ValueError: Unknown format code`.

Diagnose: Check the template string in the step config and verify that every `{placeholder}` has a matching key in the context at the point of execution.

Fix: Ensure prior steps produce the expected keys, or add defaults in the template.

### HTTP Errors

Symptoms: HTTP 429 (rate limit), 500/502/503 (server error), connection timeout, DNS resolution failure.

Fix: For rate limits, add delays or reduce `fan-out` parallelism. For server errors, retry or check service status. For timeouts, increase the step timeout config.

### Queue Issues

Symptoms: Run stuck in "running" state indefinitely, no step progress.

Diagnose: Check queue.db for unacknowledged messages:
```bash
sqlite3 ~/.liteflow/queue.db "SELECT * FROM messages WHERE ack_at IS NULL ORDER BY created_at"
```

Fix: Clear stuck messages or restart the queue processor.

## Diagnostic Commands

### Full Run Inspection
```bash
python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py inspect <run-id>
```
Shows complete run state including all step inputs, outputs, and errors.

### Run History
```bash
python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py history --workflow <name> --limit 20
```
Lists recent runs with status and duration. Use to spot patterns (e.g., failures started at a specific time).

### System Health
```bash
python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py status
```
Shows engine status, queue depth, database sizes, and recent error counts.

### Credential Check
```bash
python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py auth test --service <name>
```
Validates stored credential against the service. Reports token validity, expiry, and scopes.

### Direct Database Queries

For advanced debugging, query the databases directly:

```bash
# Recent failed runs
sqlite3 ~/.liteflow/execution.db "SELECT id, workflow, status, error FROM runs WHERE status='failed' ORDER BY started_at DESC LIMIT 5"

# Step details for a run
sqlite3 ~/.liteflow/execution.db "SELECT step_id, status, started_at, finished_at, error FROM step_runs WHERE run_id='<run-id>' ORDER BY started_at"

# Context snapshot for a step
sqlite3 ~/.liteflow/execution.db "SELECT input_context, output FROM step_runs WHERE run_id='<run-id>' AND step_id='<step-id>'"

# Pending queue messages
sqlite3 ~/.liteflow/queue.db "SELECT * FROM messages WHERE ack_at IS NULL"

# Workflow graph definition
sqlite3 ~/.liteflow/workflows.db "SELECT body FROM nodes WHERE source='<workflow-id>'"
```

## Fix Strategies

### Script Errors

1. Read the step script and the error traceback.
2. Reproduce locally: `echo '<input-context-json>' | python ~/.liteflow/steps/<workflow>/<step>.py`
3. Fix the script.
4. Re-run the workflow: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py run <workflow> --context '<original-context>'`

### Credential Errors

1. Test the credential: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py auth test --service <name>`
2. If expired or invalid, re-authenticate.
3. Re-run the workflow.

### Data Shape Issues

1. Inspect the producing step's actual output.
2. Add a `transform` step to reshape data between producer and consumer.
3. Or fix the producing step to output the expected shape.
4. Re-run the workflow.

### Stuck Runs

1. Check `queue.db` for unacknowledged messages.
2. Check if the step process is still running (zombie process).
3. If stuck, manually update the run status:
   ```bash
   sqlite3 ~/.liteflow/execution.db "UPDATE runs SET status='failed', error='Manually terminated: stuck run' WHERE id='<run-id>'"
   ```
4. Investigate why the step hung (timeout too long, infinite loop, blocking I/O).

### Gate Logic Errors

1. Check the gate condition expression.
2. Evaluate it manually against the context at that point:
   ```python
   context = <paste-context-from-inspect>
   print(eval("context['fetch_issues']['count'] > 10"))
   ```
3. Fix the condition or the data it evaluates.

## Prevention

1. **Dry-run before live execution**: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py run <workflow> --dry-run` validates the graph, checks credentials, and simulates template substitution without executing steps.

2. **Validate credentials upfront**: Run `auth test` for every service the workflow uses before starting execution.

3. **Use transform steps for data validation**: Insert a transform step that checks the shape of data before passing it to steps with strict input requirements.

4. **Set appropriate timeouts**: Every step type supports a `timeout` config. Set realistic values — too short causes false failures, too long masks hangs.

5. **Test steps independently**: Before wiring steps into a workflow, test each one by piping sample JSON. Verify output shape matches what downstream steps expect.

6. **Monitor run history**: Periodic failures may indicate flaky external services, expiring tokens, or growing data volumes exceeding timeouts.

## Reference

- `${CLAUDE_PLUGIN_ROOT}/skills/workflow-debugging/references/error-patterns.md` — Complete error pattern catalog with symptoms, causes, and fixes
