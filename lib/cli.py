"""CLI interface for liteflow — invoked by Claude Code plugin commands.

Usage:
    python -m lib.cli <subcommand> [options]
    python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py <subcommand> [options]
"""

import argparse
import json
import sys
from typing import Any, Dict


def _output(data: Any) -> None:
    """Print JSON output to stdout."""
    print(json.dumps(data, indent=2, default=str))


def _error(message: str, code: int = 1) -> None:
    """Print an error message and exit."""
    _output({"error": message})
    sys.exit(code)


def cmd_setup(args: argparse.Namespace) -> None:
    """Initialize all databases and install dependencies."""
    from .engine import LiteflowEngine

    engine = LiteflowEngine()
    result = engine.setup()
    _output(result)


def cmd_run(args: argparse.Namespace) -> None:
    """Execute a workflow."""
    from .engine import LiteflowEngine

    engine = LiteflowEngine()

    try:
        context = json.loads(args.context)
    except json.JSONDecodeError as e:
        _error(f"Invalid context JSON: {e}")
        return

    try:
        run_id = engine.run_workflow(
            args.workflow_id, context=context, dry_run=args.dry_run
        )
        run = engine.inspect_run(run_id)
        _output({"run_id": run_id, "details": run})
    except ValueError as e:
        _error(str(e))
    except Exception as e:
        _error(f"Workflow execution failed: {e}")


def cmd_list(args: argparse.Namespace) -> None:
    """List all workflows."""
    from .engine import LiteflowEngine

    engine = LiteflowEngine()
    workflows = engine.list_workflows()
    _output({"workflows": workflows, "count": len(workflows)})


def cmd_show(args: argparse.Namespace) -> None:
    """Show workflow details."""
    from .engine import LiteflowEngine

    engine = LiteflowEngine()
    wf = engine.get_workflow(args.workflow_id)
    if wf is None:
        _error(f"Workflow '{args.workflow_id}' not found")
    else:
        _output(wf)


def cmd_history(args: argparse.Namespace) -> None:
    """Show execution history."""
    from .engine import LiteflowEngine

    engine = LiteflowEngine()
    runs = engine.get_history(workflow_id=args.workflow, limit=args.limit)
    _output({"runs": runs, "count": len(runs)})


def cmd_inspect(args: argparse.Namespace) -> None:
    """Inspect a specific run."""
    from .engine import LiteflowEngine

    engine = LiteflowEngine()
    run = engine.inspect_run(args.run_id)
    if run is None:
        _error(f"Run '{args.run_id}' not found")
    else:
        _output(run)


def cmd_status(args: argparse.Namespace) -> None:
    """Show system status."""
    from .engine import LiteflowEngine

    engine = LiteflowEngine()
    status = engine.get_status()
    _output(status)


def cmd_auth(args: argparse.Namespace) -> None:
    """Manage credentials."""
    from .creds import SecureStore

    store = SecureStore()

    if args.action == "set":
        if not args.service or not args.token:
            _error("--service and --token are required for 'set'")
            return
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            metadata = {}
        store.set_token(args.service, args.token, metadata=metadata)
        _output({"status": "stored", "service": args.service})

    elif args.action == "get":
        if not args.service:
            _error("--service is required for 'get'")
            return
        cred = store.get_credential(args.service)
        if cred is None:
            _error(f"No credentials found for '{args.service}'")
        else:
            # Redact token for display
            display = dict(cred)
            if "token" in display and display["token"]:
                token = display["token"]
                display["token"] = token[:4] + "..." + token[-4:] if len(token) > 8 else "****"
            _output(display)

    elif args.action == "list":
        services = store.list_services()
        _output({"services": services, "count": len(services)})

    elif args.action == "remove":
        if not args.service:
            _error("--service is required for 'remove'")
            return
        store.remove(args.service)
        _output({"status": "removed", "service": args.service})

    elif args.action == "test":
        if not args.service:
            _error("--service is required for 'test'")
            return
        result = store.test_credential(args.service)
        _output(result)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="liteflow - DAG-based workflow engine"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # setup
    subparsers.add_parser("setup", help="Initialize databases and install dependencies")

    # run
    sub = subparsers.add_parser("run", help="Execute a workflow")
    sub.add_argument("workflow_id", help="Workflow identifier to execute")
    sub.add_argument(
        "--context",
        type=str,
        default="{}",
        help="Initial context as JSON string",
    )
    sub.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would execute without running",
    )

    # list
    subparsers.add_parser("list", help="List all workflows")

    # show
    sub = subparsers.add_parser("show", help="Show workflow details")
    sub.add_argument("workflow_id", help="Workflow identifier")

    # history
    sub = subparsers.add_parser("history", help="Show execution history")
    sub.add_argument(
        "--workflow",
        type=str,
        default=None,
        help="Filter by workflow ID",
    )
    sub.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of records (default: 20)",
    )

    # inspect
    sub = subparsers.add_parser("inspect", help="Inspect a specific run")
    sub.add_argument("run_id", help="Run identifier to inspect")

    # status
    subparsers.add_parser("status", help="Show system status")

    # auth
    sub = subparsers.add_parser("auth", help="Manage credentials")
    sub.add_argument(
        "action",
        choices=["set", "get", "list", "remove", "test"],
        help="Auth action to perform",
    )
    sub.add_argument("--service", type=str, help="Service name")
    sub.add_argument("--token", type=str, help="API token (for 'set')")
    sub.add_argument(
        "--metadata",
        type=str,
        default="{}",
        help="Additional metadata as JSON (for 'set')",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "setup": cmd_setup,
        "run": cmd_run,
        "list": cmd_list,
        "show": cmd_show,
        "history": cmd_history,
        "inspect": cmd_inspect,
        "status": cmd_status,
        "auth": cmd_auth,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        _error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
