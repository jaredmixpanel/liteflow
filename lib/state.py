"""Run tracking and step execution state using sqlite-utils.

Manages two tables:
- runs: top-level workflow execution records
- step_runs: individual step execution records within a run
"""

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .deps import ensure_deps


def _now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _get_db(db_path: str) -> "sqlite_utils.Database":
    """Open a sqlite-utils Database, creating parent dirs as needed."""
    ensure_deps("sqlite-utils")
    import sqlite_utils

    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite_utils.Database(str(path))


def init_state_db(db_path: str) -> None:
    """Create the runs and step_runs tables if they don't exist.

    Args:
        db_path: Path to the execution database.
    """
    db = _get_db(db_path)

    if "runs" not in db.table_names():
        db["runs"].create(
            {
                "id": str,
                "workflow_id": str,
                "status": str,
                "started_at": str,
                "completed_at": str,
                "context": str,
                "error": str,
            },
            pk="id",
            not_null={"id", "workflow_id", "status", "started_at"},
        )

    if "step_runs" not in db.table_names():
        db["step_runs"].create(
            {
                "id": str,
                "run_id": str,
                "step_id": str,
                "status": str,
                "started_at": str,
                "completed_at": str,
                "input_context": str,
                "output": str,
                "error": str,
                "attempt": int,
            },
            pk="id",
            not_null={"id", "run_id", "step_id", "status", "started_at"},
        )


def create_run(
    db_path: str,
    run_id: str,
    workflow_id: str,
    initial_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Insert a new run record with status='running'.

    Args:
        db_path: Path to the execution database.
        run_id: Unique run identifier.
        workflow_id: The workflow being executed.
        initial_context: Optional starting context dict.

    Returns:
        The created run record as a dict.
    """
    init_state_db(db_path)
    db = _get_db(db_path)

    record = {
        "id": run_id,
        "workflow_id": workflow_id,
        "status": "running",
        "started_at": _now(),
        "completed_at": None,
        "context": json.dumps(initial_context or {}),
        "error": None,
    }
    db["runs"].insert(record)
    return record


def complete_run(
    db_path: str,
    run_id: str,
    status: str = "completed",
    error: Optional[str] = None,
) -> None:
    """Mark a run as completed or failed.

    Args:
        db_path: Path to the execution database.
        run_id: The run to update.
        status: Final status ('completed', 'failed', 'cancelled').
        error: Optional error message if status is 'failed'.
    """
    db = _get_db(db_path)
    db["runs"].update(
        run_id,
        {"status": status, "completed_at": _now(), "error": error},
    )


def get_run(db_path: str, run_id: str) -> Optional[Dict[str, Any]]:
    """Get a run record by ID.

    Args:
        db_path: Path to the execution database.
        run_id: The run identifier.

    Returns:
        Run record as a dict, or None if not found.
    """
    db = _get_db(db_path)
    try:
        row = db["runs"].get(run_id)
        return dict(row)
    except Exception:
        return None


def get_runs(
    db_path: str,
    workflow_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """List recent runs, optionally filtered by workflow.

    Args:
        db_path: Path to the execution database.
        workflow_id: Optional workflow ID to filter by.
        limit: Maximum number of runs to return.

    Returns:
        List of run records ordered by most recent first.
    """
    db = _get_db(db_path)
    try:
        if workflow_id:
            rows = db["runs"].rows_where(
                "workflow_id = ?",
                [workflow_id],
                order_by="-started_at",
                limit=limit,
            )
        else:
            rows = db["runs"].rows_where(
                order_by="-started_at",
                limit=limit,
            )
        return [dict(r) for r in rows]
    except Exception:
        return []


def create_step_run(
    db_path: str,
    run_id: str,
    step_id: str,
    input_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Insert a step execution record.

    Args:
        db_path: Path to the execution database.
        run_id: The parent run identifier.
        step_id: The step being executed.
        input_context: Context dict passed to the step.

    Returns:
        The generated step_run ID.
    """
    import uuid

    init_state_db(db_path)
    db = _get_db(db_path)

    # Count existing attempts for this step in this run
    existing = list(
        db["step_runs"].rows_where(
            "run_id = ? AND step_id = ?", [run_id, step_id]
        )
    )
    attempt = len(existing) + 1
    step_run_id = uuid.uuid4().hex[:12]

    record = {
        "id": step_run_id,
        "run_id": run_id,
        "step_id": step_id,
        "status": "running",
        "started_at": _now(),
        "completed_at": None,
        "input_context": json.dumps(input_context or {}),
        "output": None,
        "error": None,
        "attempt": attempt,
    }
    db["step_runs"].insert(record)
    return step_run_id


def complete_step_run(
    db_path: str,
    run_id: str,
    step_id: str,
    status: str,
    output: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """Mark the latest step execution as completed or failed.

    Args:
        db_path: Path to the execution database.
        run_id: The parent run identifier.
        step_id: The step that was executed.
        status: Final status ('completed', 'failed', 'skipped').
        output: Optional output dict from the step.
        error: Optional error message.
    """
    db = _get_db(db_path)
    # Find the most recent step_run for this run+step
    rows = list(
        db["step_runs"].rows_where(
            "run_id = ? AND step_id = ? AND status = 'running'",
            [run_id, step_id],
            order_by="-started_at",
            limit=1,
        )
    )
    if rows:
        db["step_runs"].update(
            rows[0]["id"],
            {
                "status": status,
                "completed_at": _now(),
                "output": json.dumps(output) if output is not None else None,
                "error": error,
            },
        )


def get_step_runs(db_path: str, run_id: str) -> List[Dict[str, Any]]:
    """Get all step executions for a run.

    Args:
        db_path: Path to the execution database.
        run_id: The run identifier.

    Returns:
        List of step_run records ordered by start time.
    """
    db = _get_db(db_path)
    try:
        rows = db["step_runs"].rows_where(
            "run_id = ?", [run_id], order_by="started_at"
        )
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_run_context(db_path: str, run_id: str) -> Dict[str, Any]:
    """Build accumulated context by merging all successful step outputs.

    Each step's output is namespaced under its step_id in the resulting
    context dict. The initial run context is used as the base.

    Args:
        db_path: Path to the execution database.
        run_id: The run identifier.

    Returns:
        Merged context dict.
    """
    run = get_run(db_path, run_id)
    if run is None:
        return {}

    # Start with the initial run context
    context = json.loads(run.get("context") or "{}")

    # Merge in outputs from completed steps
    step_runs = get_step_runs(db_path, run_id)
    for sr in step_runs:
        if sr["status"] == "completed" and sr.get("output"):
            try:
                output = json.loads(sr["output"])
                context[sr["step_id"]] = output
            except (json.JSONDecodeError, TypeError):
                pass

    return context
