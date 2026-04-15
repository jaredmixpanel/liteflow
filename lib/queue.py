"""Execution queue management using litequeue.

Provides a persistent FIFO queue backed by SQLite for scheduling
step executions with visibility timeouts and dead-letter handling.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .deps import ensure_deps


def _get_queue(db_path: str) -> "litequeue.LiteQueue":
    """Create or open a LiteQueue instance."""
    ensure_deps("litequeue")
    from litequeue import LiteQueue

    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return LiteQueue(str(path))


def init_queue(db_path: str) -> None:
    """Create or open the queue database.

    Args:
        db_path: Path to the queue SQLite database.
    """
    _get_queue(db_path)


def enqueue(
    db_path: str,
    step_id: str,
    run_id: str,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Put a step execution message on the queue.

    Args:
        db_path: Path to the queue database.
        step_id: The step to execute.
        run_id: The run this execution belongs to.
        context: Optional context dict to pass to the step.
    """
    q = _get_queue(db_path)
    message = json.dumps({
        "step_id": step_id,
        "run_id": run_id,
        "context": context or {},
    })
    q.put(message)


def dequeue(db_path: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Pop the next message from the queue.

    Locks the message so other consumers won't receive it.
    Call ``acknowledge`` after processing, or ``nack`` to return it.

    Returns:
        Tuple of (message_id, payload_dict) or None if queue is empty.
    """
    q = _get_queue(db_path)
    pop_fn = q._select_pop_func()
    msg = pop_fn()
    if msg is None:
        return None
    payload = json.loads(msg.data)
    return (msg.message_id, payload)


def acknowledge(db_path: str, message_id: str) -> None:
    """Mark a message as successfully processed.

    Args:
        db_path: Path to the queue database.
        message_id: The message identifier returned by dequeue.
    """
    q = _get_queue(db_path)
    q.done(message_id)


def nack(db_path: str, message_id: str) -> None:
    """Return a locked message to the queue for retry.

    Args:
        db_path: Path to the queue database.
        message_id: The message identifier returned by dequeue.
    """
    q = _get_queue(db_path)
    q.retry(message_id)


def queue_size(db_path: str) -> int:
    """Return the number of pending messages in the queue.

    Args:
        db_path: Path to the queue database.

    Returns:
        Number of messages waiting to be processed.
    """
    q = _get_queue(db_path)
    return q.qsize()


def dead_letters(db_path: str) -> List[Dict[str, Any]]:
    """Get messages that have been marked as failed.

    Args:
        db_path: Path to the queue database.

    Returns:
        List of failed message dicts.
    """
    q = _get_queue(db_path)
    results = []
    try:
        for msg in q.list_failed():
            try:
                payload = json.loads(msg.data)
            except (json.JSONDecodeError, TypeError):
                payload = {"raw": msg.data}
            results.append({
                "message_id": msg.message_id,
                "payload": payload,
            })
    except Exception:
        pass
    return results


def clear_queue(db_path: str) -> None:
    """Empty the queue by removing all pending and failed messages.

    Args:
        db_path: Path to the queue database.
    """
    q = _get_queue(db_path)
    # Drain all ready messages
    pop_fn = q._select_pop_func()
    while True:
        msg = pop_fn()
        if msg is None:
            break
        q.done(msg.message_id)
    # Prune completed and failed entries
    q.prune(include_failed=True)
