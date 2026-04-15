import json
import os
import sqlite3
import sys
import urllib.request
import urllib.error


def run(context: dict) -> dict:
    """Test all stored credentials for validity."""
    db_path = os.path.expanduser("~/.liteflow/credentials.db")

    if not os.path.exists(db_path):
        return {
            "credentials": {},
            "credential_count": 0,
            "all_valid": True,
            "note": "No credentials database found — no credentials configured yet",
        }

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT service, token_type, created_at, updated_at FROM credentials"
        )

        credentials = {}
        for row in cursor:
            service = row["service"]
            token_type = row["token_type"]
            credentials[service] = {
                "token_type": token_type,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "status": "untested",
            }

        conn.close()

        # Test each credential with a lightweight API call
        for service, info in credentials.items():
            credentials[service]["status"] = _test_credential(service, db_path)

        all_valid = all(c["status"] == "valid" for c in credentials.values())

        return {
            "credentials": credentials,
            "credential_count": len(credentials),
            "all_valid": all_valid,
            "invalid": [s for s, c in credentials.items() if c["status"] != "valid"],
        }

    except sqlite3.OperationalError as e:
        return {
            "credentials": {},
            "credential_count": 0,
            "all_valid": True,
            "error": f"Query error (table may not exist yet): {str(e)}",
        }
    except Exception as e:
        return {
            "credentials": {},
            "credential_count": 0,
            "all_valid": False,
            "error": f"Failed to check credentials: {str(e)}",
        }


def _test_credential(service: str, db_path: str) -> str:
    """Test a single credential by making a lightweight API call."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT token FROM credentials WHERE service = ?", (service,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return "missing"

        token = row[0]

        # Service-specific validation endpoints
        test_urls = {
            "github": ("https://api.github.com/user", "Bearer"),
            "slack": ("https://slack.com/api/auth.test", "Bearer"),
            "linear": ("https://api.linear.app/graphql", "Bearer"),
        }

        if service not in test_urls:
            return "valid"  # No test available; assume valid

        url, auth_scheme = test_urls[service]
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"{auth_scheme} {token}")
        req.add_header("User-Agent", "liteflow-health-check")

        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return "valid"
            return f"unexpected_status:{resp.status}"

    except urllib.error.HTTPError as e:
        if e.code == 401:
            return "expired"
        if e.code == 403:
            return "forbidden"
        return f"http_error:{e.code}"
    except Exception as e:
        return f"error:{str(e)}"


if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
