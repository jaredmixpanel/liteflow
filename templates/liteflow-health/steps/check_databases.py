import json
import os
import sqlite3
import sys


def run(context: dict) -> dict:
    """Run PRAGMA integrity_check on all liteflow SQLite databases."""
    liteflow_dir = os.path.expanduser("~/.liteflow")
    results = {}
    errors = []

    if not os.path.isdir(liteflow_dir):
        return {
            "db_health": {},
            "all_healthy": False,
            "error": f"liteflow directory not found: {liteflow_dir}",
        }

    # Find all .db files in the liteflow directory
    for entry in os.listdir(liteflow_dir):
        if entry.endswith(".db"):
            db_path = os.path.join(liteflow_dir, entry)
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.execute("PRAGMA integrity_check")
                result = cursor.fetchone()[0]
                conn.close()

                results[entry] = {
                    "path": db_path,
                    "status": "ok" if result == "ok" else "corrupt",
                    "detail": result,
                    "size_bytes": os.path.getsize(db_path),
                }

                if result != "ok":
                    errors.append(f"{entry}: {result}")
            except Exception as e:
                results[entry] = {
                    "path": db_path,
                    "status": "error",
                    "detail": str(e),
                    "size_bytes": os.path.getsize(db_path) if os.path.exists(db_path) else 0,
                }
                errors.append(f"{entry}: {str(e)}")

    return {
        "db_health": results,
        "db_count": len(results),
        "all_healthy": len(errors) == 0,
        "errors": errors,
    }


if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
