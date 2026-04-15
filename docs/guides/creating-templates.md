# Creating Workflow Templates

Templates package reusable workflow patterns -- a DAG definition, step scripts, and metadata -- into a self-contained directory that anyone can instantiate with a single command. This guide walks through the template format, how to write one from scratch, and how to test it.

---

## Template Directory Structure

Every template lives in its own directory under `templates/` at the plugin root:

```
templates/<name>/
├── manifest.json     # Template metadata and configuration
├── workflow.json     # DAG definition (nodes + edges)
└── steps/            # Step implementation files
    ├── step_one.py
    ├── step_two.sh
    └── ...
```

Templates are auto-discovered by the `flow-templates` command. When a user runs `/liteflow:flow-templates` with no arguments, the command scans `${CLAUDE_PLUGIN_ROOT}/templates/` and reads each subdirectory's `manifest.json` to build a listing.

---

## manifest.json

The manifest declares template metadata and the configuration a user must provide at instantiation time.

```json
{
  "name": "my-template",
  "description": "What this template does",
  "version": "1.0.0",
  "required_credentials": ["github", "slack"],
  "variables": {
    "repo": "GitHub repository (owner/repo format)",
    "channel": "Slack channel for notifications"
  }
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Template identifier. Used in `flow-templates <name>` to select this template. Must match the directory name. |
| `description` | string | Yes | Human-readable summary shown in the template listing. |
| `version` | string | Yes | Semantic version (e.g., `1.0.0`). |
| `required_credentials` | array | No | Service names that must have stored credentials before the workflow can run. The instantiation process checks these and directs users to `/liteflow:flow-auth` if any are missing. |
| `variables` | object | No | Key-value pairs where each key is a variable name and each value is a description shown to the user during setup. Variable values are injected into the workflow context at run time as top-level keys. |

### Real-world example

The built-in `morning-briefing` template declares one required credential and two variables:

```json
{
  "name": "morning-briefing",
  "description": "Daily briefing: GitHub activity, pending PRs, open issues",
  "version": "1.0.0",
  "required_credentials": ["github"],
  "variables": {
    "github_username": "Your GitHub username",
    "repos": "Comma-separated list of repos to monitor (owner/repo)"
  }
}
```

---

## workflow.json

The workflow definition describes the DAG as a list of nodes (steps) and edges (transitions).

```json
{
  "nodes": [
    {
      "id": "fetch-data",
      "type": "shell",
      "command": "gh api repos/{repo}/pulls --jq '.[].title'",
      "description": "Fetch PR titles from GitHub"
    },
    {
      "id": "analyze",
      "type": "claude",
      "prompt": "Analyze these PR titles and summarize trends:\n\n{fetch-data.stdout}",
      "description": "Analyze PR patterns"
    },
    {
      "id": "notify",
      "type": "http",
      "url": "slack",
      "endpoint": "/chat.postMessage",
      "method": "POST",
      "body": {
        "channel": "{channel}",
        "text": "{analyze.response}"
      },
      "description": "Send summary to Slack"
    }
  ],
  "edges": [
    {"from": "fetch-data", "to": "analyze"},
    {"from": "analyze", "to": "notify"}
  ]
}
```

### Node fields

Each node object uses the same fields as a step configuration. The `id` and `type` fields are always present; the remaining fields are type-specific:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique step identifier within the workflow. Used as the context key for this step's output. |
| `type` | Yes | Step type -- one of `script`, `shell`, `claude`, `query`, `http`, `transform`, `gate`, `fan-out`, `fan-in`. |
| `description` | Yes | Human-readable summary of what this step does. |
| (type-specific) | Varies | Configuration fields for the chosen step type (`command`, `prompt`, `script`, `url`, `expression`, `condition`, `over`, etc.). See the [step types reference](../reference/step-types/index.md) for full details. |

Template variables use `{variable}` syntax and are substituted from context at execution time. Dot-path notation is supported for accessing nested values: `{step-id.nested.key}`.

### Edge fields

| Field | Required | Description |
|-------|----------|-------------|
| `from` | Yes | Source step ID. |
| `to` | Yes | Target step ID. |
| `conditions` | No | Optional conditions object. Supports `when` (for gate-based branching) and `expression` (for expression-based conditions). See [edge conditions](../concepts/workflows-and-dags.md#edge-conditions). |

### Script-type nodes

For `script`-type steps, the `script` field should reference files in the template's `steps/` directory. At instantiation time, these files are copied to `~/.liteflow/steps/<workflow-name>/`.

```json
{
  "id": "process",
  "type": "script",
  "script": "steps/process.py",
  "description": "Process and transform raw data"
}
```

---

## Writing Step Scripts

Step scripts for templates follow the same **step contract** as all liteflow steps: read JSON from stdin, expose a `run(context)` function that returns a dict, and write JSON to stdout.

```python
import json
import sys


def run(context: dict) -> dict:
    """Process data from prior steps."""
    # Template variables are top-level context keys
    repo = context.get("repo", "")

    # Prior step outputs are keyed by step ID
    data = context.get("fetch-data", {})

    if not repo:
        return {"error": "repo variable not configured"}

    return {"result": "processed", "repo": repo}


if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    output = run(ctx)
    json.dump(output, sys.stdout)
```

### Tips for template scripts

- **Use `context.get()` with defaults.** Template variables and upstream outputs may be absent during dry runs or partial executions. Defensive access prevents `KeyError` crashes.
- **Template variables are top-level context keys.** A variable named `repo` in `manifest.json` is available as `context["repo"]` at run time.
- **Prior step outputs are keyed by step ID.** A step with `"id": "fetch-data"` stores its output under `context["fetch-data"]`.
- **Return clear error messages.** When required context is missing, return a dict with an `"error"` key explaining what was expected. This makes debugging much easier when a user has not configured a variable or credential.
- **Avoid external dependencies when possible.** Use `urllib.request` instead of `requests`, `json` instead of third-party parsers. If an external package is necessary, liteflow's lazy dependency system (`deps.py`) will install it on first use -- just import normally and it will be handled.
- **Credentials are injected automatically.** For `http` steps, `HTTPStep._inject_auth()` handles credential injection. For `script` steps, credentials are available at `context["credentials"]["<service>"]["token"]`.

### Shell step scripts

Shell scripts in `steps/` follow a simpler contract -- they receive context as a JSON argument or via environment variables, and their stdout is captured as the step output:

```bash
#!/bin/bash
# steps/fetch_diff.sh
set -euo pipefail

PR_URL="${1:-}"
if [ -z "$PR_URL" ]; then
    echo '{"error": "pr_url not provided"}' >&2
    exit 1
fi

gh pr diff "$PR_URL" --color=never
```

---

## Template Instantiation Process

When a user runs `/liteflow:flow-templates my-template`, the following steps occur:

1. **Reads `manifest.json`** from `${CLAUDE_PLUGIN_ROOT}/templates/my-template/` to load template metadata.
2. **Prompts for variable values.** Each entry in the `variables` object is presented to the user with its description. The user provides values that become top-level context keys at run time.
3. **Checks required credentials.** Verifies that each service listed in `required_credentials` has stored credentials. If any are missing, directs the user to `/liteflow:flow-auth <service>`.
4. **Copies step scripts** from the template's `steps/` directory to `~/.liteflow/steps/<workflow-name>/`. Configuration placeholders in scripts are substituted with the user's variable values where applicable.
5. **Registers the workflow graph** from `workflow.json`. Creates the workflow node in the graph database.
6. **Creates step nodes and transition edges.** Each node from `workflow.json` becomes a step node linked to the workflow via a "contains" edge. Each edge becomes a transition edge between step nodes.
7. **Shows the resulting workflow structure** -- step listing, edge connections, and a Mermaid diagram for visual confirmation.

After instantiation, the command suggests next steps:
- Set up any missing credentials: `/liteflow:flow-auth <service>`
- Validate with a dry run: `/liteflow:flow-run <workflow-name> --dry-run`
- Schedule recurring execution: `/liteflow:flow-schedule <workflow-name> <cadence>`

---

## Worked Example: daily-standup

This section walks through creating a `daily-standup` template that gathers commit activity, open PRs, and assigned issues from GitHub, then generates a formatted standup summary.

### 1. Create the directory structure

```
templates/daily-standup/
├── manifest.json
├── workflow.json
└── steps/
    ├── fetch_commits.py
    ├── fetch_prs.py
    ├── fetch_issues.py
    └── generate_standup.py
```

### 2. Write manifest.json

```json
{
  "name": "daily-standup",
  "description": "Generate a daily standup summary from GitHub activity",
  "version": "1.0.0",
  "required_credentials": ["github"],
  "variables": {
    "github_username": "Your GitHub username",
    "repos": "Comma-separated repos to check (owner/repo)",
    "days_back": "Number of days to look back for commits (default: 1)"
  }
}
```

### 3. Design the DAG in workflow.json

Three data-gathering steps run in parallel (no edges between them), then all feed into a single summarization step:

```json
{
  "nodes": [
    {
      "id": "fetch-commits",
      "type": "script",
      "script": "steps/fetch_commits.py",
      "description": "Fetch recent commits by the user across configured repos"
    },
    {
      "id": "fetch-prs",
      "type": "script",
      "script": "steps/fetch_prs.py",
      "description": "Fetch open PRs authored by or requesting review from the user"
    },
    {
      "id": "fetch-issues",
      "type": "script",
      "script": "steps/fetch_issues.py",
      "description": "Fetch open issues assigned to the user"
    },
    {
      "id": "generate-standup",
      "type": "claude",
      "prompt": "Generate a concise daily standup summary from this data.\n\nCommits:\n{fetch-commits.commits}\n\nOpen PRs:\n{fetch-prs.prs}\n\nAssigned Issues:\n{fetch-issues.issues}\n\nFormat as:\n## Done\n## In Progress\n## Blocked",
      "description": "Generate formatted standup from gathered data"
    }
  ],
  "edges": [
    {"from": "fetch-commits", "to": "generate-standup"},
    {"from": "fetch-prs", "to": "generate-standup"},
    {"from": "fetch-issues", "to": "generate-standup"}
  ]
}
```

Because `fetch-commits`, `fetch-prs`, and `fetch-issues` have no inbound edges, they are all entry steps and execute in parallel. The `generate-standup` step has three predecessors, so the engine waits for all three to complete before running it.

### 4. Write step scripts

Each script follows the step contract. Here is `steps/fetch_commits.py`:

```python
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta


def run(context: dict) -> dict:
    """Fetch recent commits by the user across configured repos."""
    username = context.get("github_username", "")
    repos_str = context.get("repos", "")
    days_back = int(context.get("days_back", 1))
    token = context.get("credentials", {}).get("github", {}).get("token", "")

    if not username:
        return {"commits": [], "error": "github_username not set"}

    since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
    repos = [r.strip() for r in repos_str.split(",") if r.strip()]
    all_commits = []

    for repo in repos:
        url = f"https://api.github.com/repos/{repo}/commits?author={username}&since={since}&per_page=50"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "liteflow-daily-standup")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            for c in data:
                all_commits.append({
                    "repo": repo,
                    "message": c.get("commit", {}).get("message", "").split("\n")[0],
                    "sha": c.get("sha", "")[:7],
                    "date": c.get("commit", {}).get("author", {}).get("date", ""),
                })
        except Exception as e:
            all_commits.append({"repo": repo, "error": str(e)})

    return {"commits": all_commits, "commit_count": len(all_commits)}


if __name__ == "__main__":
    ctx = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    json.dump(run(ctx), sys.stdout)
```

The other two scripts (`fetch_prs.py`, `fetch_issues.py`) follow the same pattern -- use `urllib.request` to call the GitHub API, parse the response, and return a structured dict.

### 5. Test by creating a workflow from the template

```
/liteflow:flow-templates daily-standup
```

The command reads the manifest, prompts for `github_username`, `repos`, and `days_back`, checks that GitHub credentials are configured, copies the step scripts, and registers the workflow.

### 6. Verify with a dry run

```
/liteflow:flow-run daily-standup --dry-run
```

The dry run validates the graph structure, confirms all step scripts exist, and checks that required credentials are present -- without actually executing any steps.

### 7. Full run

```
/liteflow:flow-run daily-standup --context '{"github_username": "octocat", "repos": "octocat/hello-world", "days_back": "1"}'
```

---

## Testing Templates

Use this sequence to validate a template before sharing it:

```bash
# 1. Create a workflow from the template
/liteflow:flow-templates my-template

# 2. Verify the workflow structure was created correctly
/liteflow:flow-show my-template

# 3. Dry run to validate graph, scripts, and credentials
/liteflow:flow-run my-template --dry-run

# 4. Full run with explicit context
/liteflow:flow-run my-template --context '{"repo": "owner/name"}'

# 5. Inspect results
/liteflow:flow-inspect last
```

### Common issues to check

| Issue | How to detect | Fix |
|-------|---------------|-----|
| Missing step script | Dry run reports "script not found" | Verify `script` paths in `workflow.json` match actual filenames in `steps/` |
| Unresolved template variable | Step output contains literal `{variable}` text | Ensure the variable is declared in `manifest.json` and provided at instantiation |
| Missing credentials | Step fails with 401/403 | Add the service to `required_credentials` and run `/liteflow:flow-auth <service>` |
| Incorrect edge wiring | Steps run in wrong order or a step never executes | Check `edges` in `workflow.json` -- every step except entry steps must have at least one inbound edge |
| Step contract violation | Step fails with JSON parse error | Verify the script reads from stdin and writes valid JSON to stdout |

---

## Built-in Template Reference

liteflow ships with three templates that serve as practical examples:

### Morning Briefing

Three parallel entry steps gather GitHub data, then a Claude step summarizes everything into a daily briefing.

```
templates/morning-briefing/
├── manifest.json          # requires: github; variables: github_username, repos
├── workflow.json          # 3 parallel fetch steps -> 1 summarize step
└── steps/
    ├── fetch_prs.py
    ├── fetch_issues.py
    ├── fetch_notifications.py
    └── summarize.py
```

### PR Review

A five-step pipeline: fetch the diff, run analysis and test checks in parallel, generate a structured review, then post it.

```
templates/pr-review/
├── manifest.json          # requires: github; variables: pr_url
├── workflow.json          # fetch-diff -> (analyze-changes + check-tests) -> generate-review -> post-review
└── steps/
    ├── fetch_diff.sh
    ├── analyze_changes.py
    ├── check_tests.sh
    ├── generate_review.py
    └── post_review.sh
```

### Health Check

Five parallel checks (databases, stale runs, dead letters, credentials, disk usage) feed into a single report generation step.

```
templates/liteflow-health/
├── manifest.json          # requires: none; variables: none
├── workflow.json          # 5 parallel check steps -> 1 generate-report step
└── steps/
    ├── check_databases.py
    ├── check_stale_runs.py
    ├── check_dead_letters.py
    ├── check_credentials.py
    ├── check_disk_usage.sh
    └── generate_report.py
```

Study these templates for patterns: parallel entry steps converging on a summarizer, mixed step types (script, shell, claude, query), and defensive error handling in step scripts.

---

## See Also

- [Using Templates](../getting-started/templates.md) -- end-user guide to browsing and instantiating templates
- [Extending liteflow](extending-liteflow.md) -- other extension points (new step types, commands, agents)
- [Step Types Reference](../reference/step-types/index.md) -- full configuration for all nine step types
- [Command Reference: flow-templates](../reference/commands.md#flow-templates) -- command details
- [Workflows and DAGs](../concepts/workflows-and-dags.md) -- the DAG model underlying all workflows
- [Documentation Home](../index.md)
