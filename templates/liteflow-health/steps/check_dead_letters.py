import json
import os
import sqlite3
import sys


def run(context: dict) -> dict:
    """Check queue.db for dead letter messages that failed processing."""
    db_path = os.path.expanduser("~/.liteflow/queue.db")

    if not os.path.exists(db_path):
        return {
            "dead_letters": [],
            "dead_letter_count": 0,
            "error": "queue.db not found",
        }

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Query for dead letter messages
        cursor = conn.execute(
            """
            SELECT id, queue_name, payload, error, failed_at, retry_count
            FROM dead_letters
            ORDER BY failed_at DESC
            LIMIT 50
            """
        )

        dead_letters = []
        for row in cursor:
            dead_letters.append({
                "id": row["id"],
                "queue": row["queue_name"],
                "error": row["error"],
                "failed_at": row["failed_at"],
                "retry_count": row["retry_count"],
            })

        # Get total count
        total_cursor = conn.execute("SELECT COUNT(*) as cnt FROM dead_letters")
        total_count = total_cursor.fetchone()["cnt"]

        conn.close()

        return {
            "dead_letters": dead_letters,
            "dead_letter_count": total_count,
            "showing": len(dead_letters),
        }

    except sqlite3.OperationalError as e:
        # Table may not exist if no messages have been dead-lettered
        return {
            "dead_letters": [],
            "dead_letter_count": 0,
            "error": f"Query error (table may not exist yet): {str(e)}",
        }
    except Exception as e:
        return {
            "dead_letters": [],
            "dead_letter_count": 0,
            "error": f"Failed to query queue.db: {str(e)}",
        }


if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
