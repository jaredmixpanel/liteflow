# Error Pattern Catalog

This catalog covers the most common liteflow workflow errors. For each pattern: symptom, root cause, diagnostic steps, and fix.

---

## Authentication Failures

**Symptom**: HTTP 401 or 403 status code. Error messages containing "unauthorized", "forbidden", "token expired", "invalid credentials", or "insufficient scopes".

**Root cause**: The stored API token has expired, been revoked, or lacks the required scopes for the endpoint being called.

**Diagnose**:
1. Run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py auth test --service <name>` to validate the token.
2. Check the token's expiry timestamp in the output.
3. Verify the required scopes for the API endpoint match the token's granted scopes.

**Fix**: Re-authenticate via `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py auth set --service <name>`. For OAuth tokens, run the full OAuth flow. Ensure the new token has all required scopes.

---

## Data Shape Mismatches

**Symptom**: `TypeError: 'NoneType' object is not iterable`, `TypeError: list indices must be integers, not str`, `AttributeError: 'dict' object has no attribute 'append'`. Step expects one data structure but receives another.

**Root cause**: A producing step's output shape changed or differs from what the consuming step assumes. Common when an API response format changes or when a step returns a single object instead of a list.

**Diagnose**:
1. Inspect the failed step's input context: `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py inspect <run-id>`
2. Compare the actual shape of the upstream step's output with what the failing step expects.
3. Look for `None` values where a dict or list was expected.

**Fix**: Insert a `transform` step between the producer and consumer to normalize the shape. Alternatively, make the consuming step tolerant with `.get()` defaults and type checks.

---

## Missing Context Keys

**Symptom**: `KeyError: 'step_name'` or `KeyError: 'expected_key'`. The step tries to access a context key that does not exist.

**Root cause**: The prior step that should produce this key either did not run (skipped by a gate), failed silently, or uses a different key name. Another common cause: accessing `context['key']` instead of `context['step_id']['key']` (forgetting the step-ID namespace).

**Diagnose**:
1. Inspect the run to see which steps completed and what they produced.
2. Check if the step that should produce the key has status `completed`.
3. Verify the exact key path: outputs are namespaced by step ID.

**Fix**: Correct the key path to include the step ID namespace. Add `.get()` with defaults for optional keys. Ensure the producing step is not gated off or failing.

---

## HTTP Errors

**Symptom**: HTTP 429 (Too Many Requests), 500/502/503 (Server Error), `ConnectionError`, `TimeoutError`, `URLError`.

**Root cause**: External API rate limiting, service outage, network issues, or request timeout.

**Diagnose**:
1. Check the HTTP status code and response body in the step output.
2. For 429: look at `Retry-After` header. Check if `fan-out` parallelism is too high.
3. For 5xx: check the external service's status page.
4. For timeouts: compare the step timeout config with the actual request latency.

**Fix**:
- 429: Reduce `max_parallel` on fan-out steps. Add a `shell` step with `sleep` between batches.
- 5xx: Retry the workflow after the service recovers. Consider adding retry logic in the script step.
- Timeout: Increase the `timeout` config on the step or the HTTP request.

---

## Template Substitution Failures

**Symptom**: `KeyError` during template rendering, unresolved `{variable}` strings in executed commands or prompts, `ValueError: Unknown format code 'f'`.

**Root cause**: The template references a context key that does not exist at the time of substitution. Also occurs when context values contain curly braces that conflict with the template syntax.

**Diagnose**:
1. Find the template string in the step config (in the workflow definition).
2. List every `{placeholder}` in the template.
3. Check whether each placeholder key exists in the context at that point in execution.

**Fix**: Ensure all referenced keys are produced by prior steps. Use the full dot-path: `{step_id.key}` not just `{key}`. If context values contain literal curly braces, escape them in the template with double braces `{{` and `}}`.

---

## Queue Stuck / Unacknowledged Messages

**Symptom**: Run status shows "running" but no step progress for an extended period. The CLI `status` command shows pending queue messages.

**Root cause**: A step process crashed without acknowledging its queue message, or the engine process was terminated while a step was running.

**Diagnose**:
1. Query unacknowledged messages: `sqlite3 ~/.liteflow/queue.db "SELECT id, payload, created_at FROM messages WHERE ack_at IS NULL"`
2. Check if the step's process is still running: look for zombie Python processes.
3. Check engine logs for crash indicators.

**Fix**:
1. If the step process is gone, manually acknowledge or delete the stuck message:
   ```sql
   UPDATE messages SET ack_at = datetime('now') WHERE id = '<message-id>';
   ```
2. Mark the run as failed: `UPDATE runs SET status='failed', error='Queue stuck - manual recovery' WHERE id='<run-id>'` in execution.db.
3. Re-run the workflow.

---

## Timeout Errors

**Symptom**: `TimeoutError`, "step exceeded maximum execution time", process killed by signal.

**Root cause**: Step execution takes longer than the configured timeout. Common with large data sets, slow APIs, or unbounded loops.

**Diagnose**:
1. Check the step's timeout config in the workflow definition.
2. Compare with the step's actual execution duration from the inspect output.
3. For scripts, check for unbounded loops or large data processing without pagination.

**Fix**: Increase the timeout config to a realistic value. For large data, implement pagination or batching. For slow APIs, use fan-out with reasonable parallelism.

---

## Script Import Errors

**Symptom**: `ModuleNotFoundError: No module named 'xyz'`, `ImportError`.

**Root cause**: The step script imports a Python package that is not installed in the runtime environment. Liteflow uses lazy dependency installation via `deps.py`, but the step must declare its dependencies.

**Diagnose**:
1. Read the step script's imports.
2. Check if the required packages are available: `python -c "import xyz"`.
3. Check if `deps.py` lazy-install is configured for this dependency.

**Fix**: Install the missing package (`pip install xyz`) or use liteflow's deps system. Prefer stdlib and urllib for zero-dependency steps when possible.

---

## Permission Errors

**Symptom**: `PermissionError: [Errno 13] Permission denied`, file not found errors for step scripts.

**Root cause**: Step script file is not readable or executable. Database files are locked by another process. Step tries to write to a directory without write permission.

**Diagnose**:
1. Check file permissions: `ls -la ~/.liteflow/steps/<workflow>/<step>.py`
2. Check database locks: `fuser ~/.liteflow/*.db` or `lsof ~/.liteflow/*.db`
3. Check if another liteflow process is running.

**Fix**: Fix file permissions with `chmod`. Kill conflicting processes holding database locks. Ensure step scripts write to allowed directories only.

---

## Database Lock Errors

**Symptom**: `sqlite3.OperationalError: database is locked`, step hangs waiting for database access.

**Root cause**: Multiple processes or steps are trying to write to the same SQLite database simultaneously. SQLite supports concurrent reads but only one writer at a time.

**Diagnose**:
1. Check for concurrent liteflow processes: `ps aux | grep liteflow`
2. Check which database is locked (workflows.db, execution.db, queue.db).
3. Check if a `query` step is writing to a database that the engine also writes to.

**Fix**: Avoid concurrent workflow runs that write to the same database. Use WAL mode if not already enabled (liteflow sets this by default). Kill stale processes holding locks. If using `query` steps with write operations, ensure they target databases not used by other concurrent steps.

---

## Fan-Out / Fan-In Errors

**Symptom**: `KeyError: '_fan_out'`, "fan-in step has no matching fan-out", partial results in fan-in collection.

**Root cause**: Fan-in step's `fan_out_step` config does not match any fan-out step ID. Or some fan-out branches failed and `continue_on_error` is false.

**Diagnose**:
1. Verify the fan-in step's `fan_out_step` config matches the exact ID of the fan-out step.
2. Check how many fan-out branches succeeded vs failed.
3. Inspect individual branch failures in the run details.

**Fix**: Correct the `fan_out_step` ID. Set `continue_on_error: true` on the fan-out step if partial results are acceptable. Fix individual branch failures.

---

## Gate Condition Errors

**Symptom**: `NameError: name 'x' is not defined`, `SyntaxError` in gate condition, gate always evaluates to the same branch.

**Root cause**: The condition expression has a syntax error, references undefined variables, or evaluates against unexpected context values.

**Diagnose**:
1. Read the gate condition from the workflow definition.
2. Get the actual context at the gate step from the inspect output.
3. Evaluate the condition manually in a Python shell with the actual context.

**Fix**: Fix the condition syntax. Ensure it references `context['step_id']['key']` with correct paths. Test the condition with representative context values for both true and false cases.
