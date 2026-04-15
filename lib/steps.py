"""Step type executors for liteflow workflows.

Each step type has a dedicated execute function that receives the step
configuration, current context, run ID, and liteflow home directory.
All executors return a dict of output data.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from .helpers import HTTPStep, RunLogger, StepContext


def _template(text: str, context: Dict[str, Any]) -> str:
    """Substitute {variable} placeholders with context values.

    Supports dot-path access (e.g. {github.issues.0.title}).
    Falls back to the raw placeholder if the path is not found.

    Args:
        text: Template string with {placeholder} markers.
        context: Context dict to resolve values from.

    Returns:
        String with placeholders replaced by context values.
    """
    ctx = StepContext(context)

    def _replace(match: re.Match) -> str:
        path = match.group(1)
        value = ctx.get(path)
        if value is None:
            return match.group(0)  # leave unresolved
        return str(value)

    return re.sub(r"\{([a-zA-Z0-9_.]+)\}", _replace, text)


def execute_step(
    step_config: Dict[str, Any],
    context: Dict[str, Any],
    run_id: str,
    liteflow_home: str,
) -> Dict[str, Any]:
    """Dispatch to the right step executor based on step type.

    Args:
        step_config: Step configuration dict with 'type' and type-specific fields.
        context: Current execution context.
        run_id: The current run identifier.
        liteflow_home: Path to the liteflow home directory.

    Returns:
        Output dict from the step execution.

    Raises:
        ValueError: If the step type is unknown.
    """
    step_type = step_config.get("type")
    if not step_type:
        raise ValueError("step_config must include a 'type' field")

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
    }
    executor = executors.get(step_type)
    if executor is None:
        raise ValueError(
            f"Unknown step type: '{step_type}'. "
            f"Available types: {', '.join(sorted(executors))}"
        )
    return executor(step_config, context, run_id, liteflow_home)


def execute_script(
    config: Dict[str, Any],
    context: Dict[str, Any],
    run_id: str,
    liteflow_home: str,
) -> Dict[str, Any]:
    """Run a Python script file.

    Pipes context as JSON to stdin and captures JSON from stdout.

    Config fields:
        script: Path to the Python script (relative to liteflow_home or absolute).
        timeout: Optional timeout in seconds (default 300).
    """
    script = config["script"]
    timeout = config.get("timeout", 300)

    script_path = Path(script).expanduser()
    if not script_path.is_absolute():
        script_path = Path(liteflow_home).expanduser() / script

    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    result = subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(context),
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(script_path.parent),
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Script '{script}' failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    stdout = result.stdout.strip()
    if not stdout:
        return {}

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"output": stdout}


def execute_shell(
    config: Dict[str, Any],
    context: Dict[str, Any],
    run_id: str,
    liteflow_home: str,
) -> Dict[str, Any]:
    """Run a shell command.

    Sets environment variables from context and captures stdout.

    Config fields:
        command: Shell command string.
        timeout: Optional timeout in seconds (default 120).
    """
    command = _template(config["command"], context)
    timeout = config.get("timeout", 120)

    # Flatten context into env vars with LITEFLOW_ prefix
    env = os.environ.copy()
    env["LITEFLOW_RUN_ID"] = run_id
    env["LITEFLOW_CONTEXT"] = json.dumps(context)
    for key, value in context.items():
        if isinstance(value, (str, int, float, bool)):
            env[f"LITEFLOW_{key.upper()}"] = str(value)

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=liteflow_home,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Shell command failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    stdout = result.stdout.strip()
    # Try to parse as JSON first
    try:
        return json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return {"stdout": stdout, "exit_code": result.returncode}


def execute_claude(
    config: Dict[str, Any],
    context: Dict[str, Any],
    run_id: str,
    liteflow_home: str,
) -> Dict[str, Any]:
    """Send a prompt to Claude via the CLI.

    Templates variables in the prompt from context using {variable} syntax.

    Config fields:
        prompt: Prompt template string (required).
        timeout: Timeout in seconds for subprocess (default 120).
        parse_json: If True, use --output-format json for structured output
            and parse the result (default False).
        flags: Dict of arbitrary CLI flags passed directly to `claude`.
            String values become --key value, booleans become --key (if true),
            lists become --key item1 item2. Template substitution is applied
            to string values. Examples:
                {"model": "opus"}              → --model opus
                {"max-turns": 3}               → --max-turns 3
                {"verbose": true}              → --verbose
                {"allowedTools": ["Read"]}      → --allowedTools Read
                {"append-system-prompt": "..."}→ --append-system-prompt ...
    """
    prompt = _template(config["prompt"], context)
    timeout = config.get("timeout", 120)
    parse_json = config.get("parse_json", False)

    cmd = ["claude", "-p", prompt]

    # Use --output-format json when parse_json is requested for reliable parsing
    if parse_json:
        cmd.extend(["--output-format", "json"])

    # Pass through arbitrary CLI flags
    flags = config.get("flags", {})
    for key, value in flags.items():
        flag = f"--{key}" if not key.startswith("-") else key
        if isinstance(value, bool):
            if value:
                cmd.append(flag)
        elif isinstance(value, list):
            cmd.append(flag)
            cmd.extend(str(v) for v in value)
        else:
            cmd.append(flag)
            cmd.append(_template(str(value), context))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Claude command failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    response = result.stdout.strip()

    if parse_json:
        try:
            parsed = json.loads(response)
            # --output-format json wraps the response in a structured object
            # with a "result" field containing the actual text
            if isinstance(parsed, dict) and "result" in parsed:
                result_text = parsed["result"]
                # Try to parse the result text itself as JSON
                try:
                    return json.loads(result_text)
                except (json.JSONDecodeError, TypeError):
                    return {"response": result_text}
            return parsed
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from freeform text
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

    return {"response": response}


def execute_query(
    config: Dict[str, Any],
    context: Dict[str, Any],
    run_id: str,
    liteflow_home: str,
) -> Dict[str, Any]:
    """Run SQL against a SQLite database.

    Config fields:
        database: Path to the SQLite database.
        sql: SQL query string (supports {variable} templating).
        params: Optional list of query parameters.
    """
    db_path = _template(config["database"], context)
    sql = _template(config["sql"], context)
    params = config.get("params", [])

    db_full_path = Path(db_path).expanduser()
    if not db_full_path.is_absolute():
        db_full_path = Path(liteflow_home).expanduser() / db_path

    conn = sqlite3.connect(str(db_full_path))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(sql, params)
        if sql.strip().upper().startswith("SELECT"):
            rows = [dict(row) for row in cursor.fetchall()]
            return {"rows": rows, "count": len(rows)}
        else:
            conn.commit()
            return {"rowcount": cursor.rowcount}
    finally:
        conn.close()


def execute_http(
    config: Dict[str, Any],
    context: Dict[str, Any],
    run_id: str,
    liteflow_home: str,
) -> Dict[str, Any]:
    """Make an HTTP request using HTTPStep helper.

    Config fields:
        method: HTTP method (GET, POST, PUT, DELETE). Default: GET.
        url: URL or service name.
        endpoint: Optional API endpoint path.
        body: Optional request body (supports templating).
        headers: Optional headers dict.
    """
    from .creds import SecureStore

    method = config.get("method", "GET").upper()
    url = _template(config["url"], context)
    endpoint = _template(config.get("endpoint", ""), context)
    headers = config.get("headers", {})
    body = config.get("body")

    if body is not None:
        if isinstance(body, str):
            body = _template(body, context)
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                pass
        elif isinstance(body, dict):
            body = json.loads(_template(json.dumps(body), context))

    creds_db = str(Path(liteflow_home).expanduser() / "credentials.db")
    try:
        store = SecureStore(db_path=creds_db)
    except Exception:
        store = None

    http = HTTPStep(auth_store=store)

    if method == "GET":
        return http.get(url, endpoint=endpoint, headers=headers)
    elif method == "POST":
        return http.post(url, data=body, endpoint=endpoint, headers=headers)
    elif method == "PUT":
        return http.put(url, data=body, endpoint=endpoint, headers=headers)
    elif method == "DELETE":
        return http.delete(url, endpoint=endpoint, headers=headers)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")


def execute_transform(
    config: Dict[str, Any],
    context: Dict[str, Any],
    run_id: str,
    liteflow_home: str,
) -> Dict[str, Any]:
    """Evaluate a Python expression with context available.

    Uses a restricted eval with the context dict, plus safe builtins
    (len, str, int, float, list, dict, sorted, min, max, sum, any, all, zip, enumerate).

    Config fields:
        expression: Python expression string.
    """
    expression = config["expression"]

    safe_builtins = {
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "sorted": sorted,
        "reversed": reversed,
        "min": min,
        "max": max,
        "sum": sum,
        "any": any,
        "all": all,
        "zip": zip,
        "enumerate": enumerate,
        "range": range,
        "abs": abs,
        "round": round,
        "True": True,
        "False": False,
        "None": None,
    }

    eval_globals = {"__builtins__": safe_builtins}
    eval_locals = dict(context)
    eval_locals["context"] = context
    eval_locals["ctx"] = StepContext(context)

    result = eval(expression, eval_globals, eval_locals)  # noqa: S307

    if isinstance(result, dict):
        return result
    return {"result": result}


def execute_gate(
    config: Dict[str, Any],
    context: Dict[str, Any],
    run_id: str,
    liteflow_home: str,
) -> Dict[str, Any]:
    """Evaluate a condition expression against context.

    Returns {"_gate_result": True/False} for the engine to decide
    which edges to follow.

    Config fields:
        condition: Python boolean expression string.
    """
    condition = config["condition"]

    safe_builtins = {
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "any": any,
        "all": all,
        "True": True,
        "False": False,
        "None": None,
    }

    eval_globals = {"__builtins__": safe_builtins}
    eval_locals = dict(context)
    eval_locals["context"] = context
    eval_locals["ctx"] = StepContext(context)

    result = bool(eval(condition, eval_globals, eval_locals))  # noqa: S307
    return {"_gate_result": result}


def execute_fan_out(
    config: Dict[str, Any],
    context: Dict[str, Any],
    run_id: str,
    liteflow_home: str,
) -> Dict[str, Any]:
    """Take an array from context and fan out for parallel processing.

    Config fields:
        over: Dot-path to an array in context to iterate over.
        item_key: Key name for each item in child context (default: "item").
    """
    over = config["over"]
    item_key = config.get("item_key", "item")

    ctx = StepContext(context)
    items = ctx.get(over)

    if items is None:
        raise ValueError(f"Fan-out path '{over}' not found in context")
    if not isinstance(items, (list, tuple)):
        raise ValueError(
            f"Fan-out path '{over}' must be a list, got {type(items).__name__}"
        )

    return {
        "_fan_out_items": [
            {item_key: item, "_fan_out_index": i}
            for i, item in enumerate(items)
        ],
    }


def execute_fan_in(
    config: Dict[str, Any],
    context: Dict[str, Any],
    run_id: str,
    liteflow_home: str,
) -> Dict[str, Any]:
    """Collect results from fan-out executions.

    The engine accumulates fan-out results under _fan_in_results in
    the context before calling this step.

    Config fields:
        merge_key: Optional key to extract from each result for the merged array.
    """
    results = context.get("_fan_in_results", [])
    merge_key = config.get("merge_key")

    if merge_key:
        merged = []
        for r in results:
            if isinstance(r, dict) and merge_key in r:
                merged.append(r[merge_key])
            else:
                merged.append(r)
        return {"results": merged, "count": len(merged)}

    return {"results": results, "count": len(results)}
