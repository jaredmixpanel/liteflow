import json
import sys
import urllib.request
import urllib.error


def run(context: dict) -> dict:
    """Fetch recent GitHub notifications for the authenticated user."""
    token = context.get("credentials", {}).get("github", {}).get("token", "")

    if not token:
        return {"notifications": [], "error": "GitHub token not configured. Run /liteflow:flow-auth github"}

    url = "https://api.github.com/notifications?per_page=25&all=false"

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "liteflow-morning-briefing")
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"notifications": [], "error": f"GitHub API error: {e.code} {e.reason}"}
    except Exception as e:
        return {"notifications": [], "error": f"Request failed: {str(e)}"}

    notifications = []
    for item in data:
        notifications.append({
            "reason": item.get("reason"),
            "title": item.get("subject", {}).get("title"),
            "type": item.get("subject", {}).get("type"),
            "repo": item.get("repository", {}).get("full_name"),
            "updated_at": item.get("updated_at"),
            "unread": item.get("unread"),
        })

    return {"notifications": notifications, "notification_count": len(notifications)}


if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
