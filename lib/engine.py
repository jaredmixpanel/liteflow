"""Core workflow execution engine for liteflow.

The LiteflowEngine orchestrates workflow execution by reading workflow
definitions from the graph database, scheduling steps via the execution
queue, and tracking results in the state database.
"""

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import graph, queue, state
from .helpers import RunLogger, StepContext
from .steps import execute_step


class LiteflowEngine:
    """DAG-based workflow execution engine backed by SQLite.

    Manages workflow definitions, execution scheduling, state tracking,
    and credential storage through a set of SQLite databases stored
    in the liteflow home directory.
    """

    def __init__(self, home_dir: str = "~/.liteflow") -> None:
        self.home = Path(home_dir).expanduser()
        self.home.mkdir(parents=True, exist_ok=True)

        self.workflows_db = str(self.home / "workflows.db")
        self.execution_db = str(self.home / "execution.db")
        self.queue_db = str(self.home / "queue.db")
        self.credentials_db = str(self.home / "credentials.db")
        self.config_db = str(self.home / "config.db")

    def setup(self) -> Dict[str, Any]:
        """Initialize all databases and install core dependencies.

        Returns:
            Dict with setup status for each component.
        """
        from .deps import ensure_deps, check_deps

        results: Dict[str, Any] = {}

        # Install core dependencies
        try:
            ensure_deps(
                "simple-graph-sqlite", "litequeue", "sqlite-utils", "sqlitedict"
            )
            results["dependencies"] = "installed"
        except Exception as e:
            results["dependencies"] = f"error: {e}"

        # Initialize databases
        try:
            graph.init_graph_db(self.workflows_db)
            results["workflows_db"] = "ready"
        except Exception as e:
            results["workflows_db"] = f"error: {e}"

        try:
            state.init_state_db(self.execution_db)
            results["execution_db"] = "ready"
        except Exception as e:
            results["execution_db"] = f"error: {e}"

        try:
            queue.init_queue(self.queue_db)
            results["queue_db"] = "ready"
        except Exception as e:
            results["queue_db"] = f"error: {e}"

        results["home"] = str(self.home)
        results["dep_status"] = check_deps()

        return results

    def run_workflow(
        self,
        workflow_id: str,
        context: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> str:
        """Execute a workflow and return the run ID.

        Args:
            workflow_id: The workflow to execute.
            context: Optional initial context dict.
            dry_run: If True, log what would execute without running.

        Returns:
            The generated run_id string.

        Raises:
            ValueError: If the workflow is not found or has no entry steps.
        """
        # Validate workflow exists
        wf = graph.get_workflow(self.workflows_db, workflow_id)
        if wf is None:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        # Generate run ID
        run_id = uuid.uuid4().hex[:12]

        # Create run record
        state.create_run(self.execution_db, run_id, workflow_id, context)

        # Find entry steps
        entry_steps = graph.get_entry_steps(self.workflows_db, workflow_id)
        if not entry_steps:
            state.complete_run(
                self.execution_db, run_id, "failed", "No entry steps found"
            )
            raise ValueError(f"Workflow '{workflow_id}' has no entry steps")

        # Enqueue entry steps
        for step in entry_steps:
            queue.enqueue(self.queue_db, step["id"], run_id, context)

        # Execute
        try:
            self._run_loop(run_id, dry_run)
            # Check if all steps passed
            run_record = state.get_run(self.execution_db, run_id)
            if run_record and run_record["status"] == "running":
                state.complete_run(self.execution_db, run_id, "completed")
        except Exception as e:
            state.complete_run(self.execution_db, run_id, "failed", str(e))
            raise

        return run_id

    def _run_loop(self, run_id: str, dry_run: bool = False) -> None:
        """Core execution loop: dequeue, execute, enqueue successors.

        Args:
            run_id: The current run identifier.
            dry_run: If True, log steps without executing.
        """
        max_iterations = 1000  # safety limit
        iterations = 0

        while iterations < max_iterations:
            iterations += 1

            # Dequeue next message
            msg = queue.dequeue(self.queue_db)
            if msg is None:
                break

            message_id, payload = msg
            step_id = payload["step_id"]
            msg_run_id = payload["run_id"]

            # Skip messages from other runs
            if msg_run_id != run_id:
                queue.acknowledge(self.queue_db, message_id)
                continue

            logger = RunLogger(run_id, step_id, self.execution_db)

            # Load step config from graph
            step_config = self._get_step_config(step_id)
            if step_config is None:
                logger.error(f"Step config not found for '{step_id}'")
                queue.acknowledge(self.queue_db, message_id)
                continue

            # Build context from prior step outputs
            context = state.get_run_context(self.execution_db, run_id)
            # Merge any context passed in the message
            if payload.get("context"):
                context.update(payload["context"])

            if dry_run:
                logger.info(
                    f"DRY RUN: Would execute step '{step_id}' "
                    f"(type={step_config.get('type')})"
                )
                logger.info("Context keys", list(context.keys()))
                queue.acknowledge(self.queue_db, message_id)
                # Still enqueue successors for dry-run visibility
                successors = graph.get_successors(self.workflows_db, step_id)
                for edge in successors:
                    queue.enqueue(
                        self.queue_db, edge["target"], run_id, context
                    )
                continue

            # Execute the step
            logger.info(f"Executing step '{step_id}' (type={step_config.get('type')})")
            state.create_step_run(self.execution_db, run_id, step_id, context)

            try:
                output = execute_step(
                    step_config, context, run_id, str(self.home)
                )
                state.complete_step_run(
                    self.execution_db, run_id, step_id, "completed", output
                )
                logger.info(f"Step '{step_id}' completed")

                # Handle fan-out
                if "_fan_out_items" in output:
                    self._handle_fan_out(
                        run_id, step_id, output["_fan_out_items"], context, logger
                    )
                elif context.get("_fan_out_step"):
                    # This step was spawned by a fan-out — check if
                    # all parallel items are now complete
                    merged = self._check_fan_out_complete(
                        run_id, step_id, context
                    )
                    if merged is not None:
                        logger.info(
                            f"All fan-out items complete, "
                            f"collected {len(merged.get('_fan_in_results', []))} results"
                        )
                        # Enqueue successors with collected results
                        successors = graph.get_successors(
                            self.workflows_db, step_id
                        )
                        merged[step_id] = output
                        for edge in successors:
                            if self._evaluate_edge(edge, merged, output):
                                queue.enqueue(
                                    self.queue_db,
                                    edge["target"],
                                    run_id,
                                    merged,
                                )
                                logger.info(
                                    f"Enqueued successor '{edge['target']}'"
                                )
                else:
                    # Get successors and evaluate edge conditions
                    successors = graph.get_successors(self.workflows_db, step_id)
                    # Merge output into context for edge evaluation
                    context[step_id] = output

                    for edge in successors:
                        if self._evaluate_edge(edge, context, output):
                            # Check if all predecessors of the target have
                            # completed before enqueuing (fan-in gate)
                            if self._all_predecessors_done(
                                run_id, edge["target"]
                            ):
                                queue.enqueue(
                                    self.queue_db,
                                    edge["target"],
                                    run_id,
                                    context,
                                )
                                logger.info(
                                    f"Enqueued successor '{edge['target']}'"
                                )

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Step '{step_id}' failed: {error_msg}")
                state.complete_step_run(
                    self.execution_db, run_id, step_id, "failed", error=error_msg
                )

                # Handle error policy
                error_policy = step_config.get("on_error", "fail")
                if error_policy == "retry":
                    max_retries = step_config.get("max_retries", 3)
                    step_runs = state.get_step_runs(self.execution_db, run_id)
                    attempts = sum(
                        1
                        for sr in step_runs
                        if sr["step_id"] == step_id and sr["status"] == "failed"
                    )
                    if attempts < max_retries:
                        logger.info(
                            f"Retrying step '{step_id}' "
                            f"(attempt {attempts + 1}/{max_retries})"
                        )
                        queue.enqueue(self.queue_db, step_id, run_id, context)
                    else:
                        logger.error(
                            f"Step '{step_id}' exhausted retries ({max_retries})"
                        )
                        raise
                elif error_policy == "skip":
                    logger.warn(f"Skipping failed step '{step_id}' per error policy")
                    successors = graph.get_successors(self.workflows_db, step_id)
                    for edge in successors:
                        queue.enqueue(
                            self.queue_db, edge["target"], run_id, context
                        )
                else:
                    # fail — propagate the error
                    raise

            finally:
                queue.acknowledge(self.queue_db, message_id)

    def _handle_fan_out(
        self,
        run_id: str,
        step_id: str,
        items: List[Dict[str, Any]],
        context: Dict[str, Any],
        logger: RunLogger,
    ) -> None:
        """Handle fan-out by enqueuing the next step once per item.

        Each fanned-out message carries metadata so the engine can track
        completion and collect results for the fan-in step.

        Args:
            run_id: Current run identifier.
            step_id: The fan-out step that produced the items.
            items: List of item dicts to fan out over.
            context: Current execution context.
            logger: Logger instance.
        """
        successors = graph.get_successors(self.workflows_db, step_id)
        if not successors:
            logger.warn("Fan-out step has no successors")
            return

        logger.info(f"Fanning out {len(items)} items to {len(successors)} successor(s)")

        for edge in successors:
            for idx, item in enumerate(items):
                item_context = dict(context)
                item_context.update(item)
                item_context["_fan_out_step"] = step_id
                item_context["_fan_out_total"] = len(items)
                item_context["_fan_out_index"] = idx
                queue.enqueue(
                    self.queue_db, edge["target"], run_id, item_context
                )

    def _check_fan_out_complete(
        self,
        run_id: str,
        step_id: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Check if all fan-out items for a step have completed.

        When all items are done, collects their outputs into
        _fan_in_results and returns the merged context. Returns None
        if items are still pending.
        """
        fan_out_step = context.get("_fan_out_step")
        fan_out_total = context.get("_fan_out_total", 0)

        if not fan_out_step or fan_out_total == 0:
            return None

        # Count completed runs of this step spawned by the fan-out
        step_runs = state.get_step_runs(self.execution_db, run_id)
        completed = [
            sr for sr in step_runs
            if sr["step_id"] == step_id and sr["status"] == "completed"
        ]

        if len(completed) < fan_out_total:
            return None  # Still waiting for more items

        # All items done — collect results
        results = []
        for sr in completed:
            output = sr.get("output", {})
            if isinstance(output, str):
                try:
                    output = json.loads(output)
                except (json.JSONDecodeError, TypeError):
                    output = {}
            results.append(output)

        # Build merged context with collected results
        merged = dict(context)
        # Remove fan-out metadata
        merged.pop("_fan_out_step", None)
        merged.pop("_fan_out_total", None)
        merged.pop("_fan_out_index", None)
        merged["_fan_in_results"] = results

        return merged

    def _evaluate_edge(
        self,
        edge: Dict[str, Any],
        context: Dict[str, Any],
        step_output: Dict[str, Any],
    ) -> bool:
        """Check if an edge's transition condition is met.

        Args:
            edge: Edge dict with optional 'conditions'.
            context: Current execution context.
            step_output: Output from the step that produced this edge.

        Returns:
            True if the edge should be followed.
        """
        conditions = edge.get("conditions", {})
        if not conditions:
            return True

        # Handle gate results
        gate_result = step_output.get("_gate_result")

        if "when" in conditions:
            when = conditions["when"]
            if when == "true" and gate_result is True:
                return True
            if when == "false" and gate_result is False:
                return True
            if when == "always":
                return True
            if gate_result is not None:
                return False

        if "expression" in conditions:
            ctx = StepContext(context)
            safe_builtins = {
                "len": len, "str": str, "int": int, "float": float,
                "bool": bool, "any": any, "all": all,
                "True": True, "False": False, "None": None,
            }
            try:
                result = eval(  # noqa: S307
                    conditions["expression"],
                    {"__builtins__": safe_builtins},
                    {"ctx": ctx, **context},
                )
                return bool(result)
            except Exception:
                return False

        return True

    def _all_predecessors_done(self, run_id: str, target_step_id: str) -> bool:
        """Check if all predecessor steps of a target have completed.

        Used to prevent a step with multiple inbound edges from being
        enqueued before all its predecessors finish (fan-in gate).

        Args:
            run_id: Current run identifier.
            target_step_id: The step we want to enqueue.

        Returns:
            True if all predecessors have a completed step_run.
        """
        predecessors = graph.get_predecessors(self.workflows_db, target_step_id)
        if len(predecessors) <= 1:
            return True  # Single predecessor or entry step — always ready

        step_runs = state.get_step_runs(self.execution_db, run_id)
        completed_steps = {
            sr["step_id"]
            for sr in step_runs
            if sr["status"] == "completed"
        }

        for pred in predecessors:
            if pred["source"] not in completed_steps:
                return False

        return True

    def _get_step_config(self, step_id: str) -> Optional[Dict[str, Any]]:
        """Load step configuration from the graph database.

        Args:
            step_id: Step identifier.

        Returns:
            Step config dict, or None if not found.
        """
        import sqlite3 as _sqlite3

        conn = _sqlite3.connect(self.workflows_db)
        try:
            cursor = conn.execute(
                "SELECT body FROM nodes WHERE id = ?",
                (step_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            body = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            if isinstance(body, dict) and body.get("node_type") == "step":
                return body
            return None
        except Exception:
            return None
        finally:
            conn.close()

    def get_status(self) -> Dict[str, Any]:
        """Return system status: database sizes, queue depth, recent runs.

        Returns:
            Status dict with database info and summary statistics.
        """
        status: Dict[str, Any] = {"home": str(self.home), "databases": {}}

        # Database sizes
        for name in ["workflows", "execution", "queue", "credentials", "config"]:
            db_file = self.home / f"{name}.db"
            if db_file.exists():
                size = db_file.stat().st_size
                status["databases"][name] = {
                    "path": str(db_file),
                    "size_bytes": size,
                    "size_human": (
                        f"{size / 1024:.1f} KB"
                        if size > 1024
                        else f"{size} B"
                    ),
                }
            else:
                status["databases"][name] = {"path": str(db_file), "exists": False}

        # Queue depth
        try:
            status["queue_depth"] = queue.queue_size(self.queue_db)
        except Exception:
            status["queue_depth"] = 0

        # Recent runs
        try:
            runs = state.get_runs(self.execution_db, limit=5)
            status["recent_runs"] = runs
        except Exception:
            status["recent_runs"] = []

        # Workflow count
        try:
            workflows = graph.list_workflows(self.workflows_db)
            status["workflow_count"] = len(workflows)
        except Exception:
            status["workflow_count"] = 0

        return status

    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all registered workflows.

        Returns:
            List of workflow dicts with id, name, description, metadata.
        """
        return graph.list_workflows(self.workflows_db)

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get a workflow definition with all steps and edges.

        Args:
            workflow_id: The workflow identifier.

        Returns:
            Workflow dict or None if not found.
        """
        return graph.get_workflow(self.workflows_db, workflow_id)

    def get_history(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Show execution history.

        Args:
            workflow_id: Optional filter by workflow.
            limit: Maximum number of records to return.

        Returns:
            List of run records.
        """
        return state.get_runs(self.execution_db, workflow_id=workflow_id, limit=limit)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a run record.

        Args:
            run_id: The run identifier.

        Returns:
            Run record dict or None.
        """
        return state.get_run(self.execution_db, run_id)

    def inspect_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed run information with all step results.

        Args:
            run_id: The run identifier.

        Returns:
            Dict with run record, step runs, and accumulated context.
        """
        run = state.get_run(self.execution_db, run_id)
        if run is None:
            return None

        step_runs = state.get_step_runs(self.execution_db, run_id)
        context = state.get_run_context(self.execution_db, run_id)

        # Parse JSON fields for readability
        for sr in step_runs:
            for field in ("input_context", "output"):
                if sr.get(field) and isinstance(sr[field], str):
                    try:
                        sr[field] = json.loads(sr[field])
                    except json.JSONDecodeError:
                        pass

        if run.get("context") and isinstance(run["context"], str):
            try:
                run["context"] = json.loads(run["context"])
            except json.JSONDecodeError:
                pass

        return {
            "run": run,
            "step_runs": step_runs,
            "accumulated_context": context,
        }
