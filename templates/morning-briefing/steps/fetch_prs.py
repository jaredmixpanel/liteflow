import json
import os
import sys
import urllib.request
import urllib.error


def run(context: dict) -> dict:
    """Fetch open PRs requesting review from the user via GitHub API."""
    username = context.get("github_username", "")
    token = context.get("credentials", {}).get("github", {}).get("token", "")

    if not username:
        return {"prs": [], "error": "github_username not set in workflow variables"}

    query = f"type:pr review-requested:{username} is:open"
    url = f"https://api.github.com/search/issues?q={urllib.request.quote(query)}&per_page=25&sort=updated&order=desc"

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "liteflow-morning-briefing")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"prs": [], "error": f"GitHub API error: {e.code} {e.reason}"}
    except Exception as e:
        return {"prs": [], "error": f"Request failed: {str(e)}"}

    prs = []
    for item in data.get("items", []):
        prs.append({
            "title": item.get("title"),
            "url": item.get("html_url"),
            "repo": item.get("repository_url", "").replace("https://api.github.com/repos/", ""),
            "author": item.get("user", {}).get("login"),
            "updated_at": item.get("updated_at"),
            "labels": [l.get("name") for l in item.get("labels", [])],
        })

    return {"prs": prs, "pr_count": len(prs)}


if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
