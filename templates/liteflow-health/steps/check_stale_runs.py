import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone


def run(context: dict) -> dict:
    """Query execution.db for workflow runs stuck in 'running' status for over 1 hour."""
    db_path = os.path.expanduser("~/.liteflow/execution.db")

    if not os.path.exists(db_path):
        return {
            "stale_runs": [],
            "stale_count": 0,
            "error": "execution.db not found",
        }

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Find runs that have been in "running" status for more than 1 hour
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        cursor = conn.execute(
            """
            SELECT id, workflow_name, status, started_at, updated_at
            FROM runs
            WHERE status = 'running'
              AND started_at < ?
            ORDER BY started_at ASC
            """,
            (cutoff,),
        )

        stale_runs = []
        for row in cursor:
            started = row["started_at"]
            stale_runs.append({
                "run_id": row["id"],
                "workflow": row["workflow_name"],
                "status": row["status"],
                "started_at": started,
                "updated_at": row["updated_at"],
            })

        conn.close()

        return {
            "stale_runs": stale_runs,
            "stale_count": len(stale_runs),
        }

    except sqlite3.OperationalError as e:
        # Table may not exist yet if no workflows have run
        return {
            "stale_runs": [],
            "stale_count": 0,
            "error": f"Query error (table may not exist yet): {str(e)}",
        }
    except Exception as e:
        return {
            "stale_runs": [],
            "stale_count": 0,
            "error": f"Failed to query execution.db: {str(e)}",
        }


if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
