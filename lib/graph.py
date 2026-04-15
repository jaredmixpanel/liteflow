"""Workflow graph management using simple-graph-sqlite.

Workflows are stored as directed graphs where nodes represent steps
and edges represent transitions between steps. Each workflow is a
logical namespace within the graph database.

The ``simple_graph_sqlite`` library stores nodes as JSON blobs with
a generated ``id`` column extracted from ``$.id`` in the body. Edges
link source to target with JSON properties.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .deps import ensure_deps


def _db_path(db_path: str) -> str:
    """Resolve and ensure parent directory for a database path."""
    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def init_graph_db(db_path: str) -> None:
    """Create or open the graph database and initialize its schema."""
    ensure_deps("simple-graph-sqlite")
    from simple_graph_sqlite import database as sgdb

    sgdb.initialize(_db_path(db_path))


def create_workflow(
    db_path: str,
    workflow_id: str,
    name: str,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Add a workflow node to the graph.

    Args:
        db_path: Path to the graph database.
        workflow_id: Unique identifier for the workflow.
        name: Human-readable workflow name.
        description: Optional description.
        metadata: Optional additional metadata dict.
    """
    ensure_deps("simple-graph-sqlite")
    from simple_graph_sqlite import database as sgdb

    body = {
        "id": workflow_id,
        "type": "workflow",
        "name": name,
        "description": description,
        "metadata": metadata or {},
    }
    resolved = _db_path(db_path)
    sgdb.atomic(resolved, sgdb.upsert_node(workflow_id, body))


def add_step(
    db_path: str,
    workflow_id: str,
    step_id: str,
    step_config: Dict[str, Any],
) -> None:
    """Add a step node to a workflow's graph.

    Creates the step node and a 'contains' edge from the workflow to the step.

    Args:
        db_path: Path to the graph database.
        workflow_id: The parent workflow identifier.
        step_id: Unique step identifier.
        step_config: Dict with 'type' and step-specific fields
                     (script, command, prompt, etc.).

    Raises:
        ValueError: If step_config is missing required 'type' field.
    """
    if "type" not in step_config:
        raise ValueError("step_config must include a 'type' field")

    ensure_deps("simple-graph-sqlite")
    from simple_graph_sqlite import database as sgdb

    body = {
        "id": step_id,
        **step_config,
        "node_type": "step",
        "workflow_id": workflow_id,
    }
    edge_body = {"type": "contains"}

    resolved = _db_path(db_path)

    # Compose upsert + connect into a single atomic closure
    upsert_fn = sgdb.upsert_node(step_id, body)
    connect_fn = sgdb.connect_nodes(workflow_id, step_id, edge_body)

    def _add_step(cursor):
        upsert_fn(cursor)
        connect_fn(cursor)

    sgdb.atomic(resolved, _add_step)


def add_edge(
    db_path: str,
    source_step: str,
    target_step: str,
    conditions: Optional[Dict[str, Any]] = None,
) -> None:
    """Connect two steps with an optional transition condition.

    Args:
        db_path: Path to the graph database.
        source_step: Source step identifier.
        target_step: Target step identifier.
        conditions: Optional dict with transition conditions
                    (e.g. {"when": "true"}, {"expression": "..."}).
    """
    ensure_deps("simple-graph-sqlite")
    from simple_graph_sqlite import database as sgdb

    body = {"type": "transition", "conditions": conditions or {}}
    resolved = _db_path(db_path)
    sgdb.atomic(resolved, sgdb.connect_nodes(source_step, target_step, body))


def get_workflow(db_path: str, workflow_id: str) -> Optional[Dict[str, Any]]:
    """Return a workflow definition with all steps and edges.

    Returns:
        Dict with 'workflow', 'steps', and 'edges' keys, or None if not found.
    """
    ensure_deps("simple-graph-sqlite")
    from simple_graph_sqlite import database as sgdb

    resolved = _db_path(db_path)
    body = sgdb.atomic(resolved, sgdb.find_node(workflow_id))

    if not body:
        return None

    steps = get_steps(db_path, workflow_id)
    edges = get_edges(db_path, workflow_id)
    return {"workflow": {"id": workflow_id, **body}, "steps": steps, "edges": edges}


def get_steps(db_path: str, workflow_id: str) -> List[Dict[str, Any]]:
    """Return all steps belonging to a workflow."""
    resolved = _db_path(db_path)

    conn = sqlite3.connect(resolved)
    try:
        # Find step nodes connected from the workflow via 'contains' edges
        cursor = conn.execute(
            "SELECT target, properties FROM edges WHERE source = ?",
            (workflow_id,),
        )
        step_ids = []
        for row in cursor.fetchall():
            props = json.loads(row[1]) if row[1] else {}
            if props.get("type") == "contains":
                step_ids.append(row[0])

        steps = []
        for sid in step_ids:
            node_cursor = conn.execute(
                "SELECT body FROM nodes WHERE id = ?", (sid,)
            )
            node_row = node_cursor.fetchone()
            if node_row:
                body = json.loads(node_row[0])
                steps.append(body)
        return steps
    finally:
        conn.close()


def get_edges(db_path: str, workflow_id: str) -> List[Dict[str, Any]]:
    """Return all transition edges for a workflow's steps."""
    steps = get_steps(db_path, workflow_id)
    step_ids = {s["id"] for s in steps}
    if not step_ids:
        return []

    resolved = _db_path(db_path)
    conn = sqlite3.connect(resolved)
    try:
        placeholders = ",".join("?" for _ in step_ids)
        cursor = conn.execute(
            f"SELECT source, target, properties "
            f"FROM edges WHERE source IN ({placeholders})",
            list(step_ids),
        )
        edges = []
        for row in cursor.fetchall():
            props = json.loads(row[2]) if row[2] else {}
            if props.get("type") == "transition":
                edges.append({"source": row[0], "target": row[1], **props})
        return edges
    finally:
        conn.close()


def get_successors(db_path: str, step_id: str) -> List[Dict[str, Any]]:
    """Get outbound transition edges from a step."""
    resolved = _db_path(db_path)
    conn = sqlite3.connect(resolved)
    try:
        cursor = conn.execute(
            "SELECT source, target, properties FROM edges WHERE source = ?",
            (step_id,),
        )
        results = []
        for row in cursor.fetchall():
            props = json.loads(row[2]) if row[2] else {}
            if props.get("type") == "transition":
                results.append({"source": row[0], "target": row[1], **props})
        return results
    finally:
        conn.close()


def get_entry_steps(db_path: str, workflow_id: str) -> List[Dict[str, Any]]:
    """Find steps with no inbound transition edges (start nodes)."""
    steps = get_steps(db_path, workflow_id)
    edges = get_edges(db_path, workflow_id)
    targets = {e["target"] for e in edges}
    return [s for s in steps if s["id"] not in targets]


def delete_workflow(db_path: str, workflow_id: str) -> None:
    """Remove a workflow and all its steps and edges."""
    ensure_deps("simple-graph-sqlite")
    from simple_graph_sqlite import database as sgdb

    steps = get_steps(db_path, workflow_id)
    resolved = _db_path(db_path)

    # Compose all removals into a single atomic closure
    remove_fns = [sgdb.remove_node(s["id"]) for s in steps]
    remove_fns.append(sgdb.remove_node(workflow_id))

    def _delete_all(cursor):
        for fn in remove_fns:
            fn(cursor)

    sgdb.atomic(resolved, _delete_all)


def list_workflows(db_path: str) -> List[Dict[str, Any]]:
    """List all workflows with metadata."""
    resolved = _db_path(db_path)
    try:
        conn = sqlite3.connect(resolved)
        cursor = conn.execute("SELECT id, body FROM nodes")
        workflows = []
        for row in cursor.fetchall():
            body = json.loads(row[1]) if row[1] else {}
            if body.get("type") == "workflow":
                workflows.append(body)
        conn.close()
        return workflows
    except Exception:
        return []
