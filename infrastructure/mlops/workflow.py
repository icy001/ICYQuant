"""
Workflow Engine — DAG-based MLOps pipeline orchestration.

Defines and executes MLOps workflows as directed acyclic graphs (DAGs)
of steps. Each step can be a training run, evaluation, drift check,
or deployment action with dependencies and conditional execution.
"""

import enum
import time
import uuid
import threading
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StepStatus(str, enum.Enum):
    """Status of a workflow step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class WorkflowStep:
    """A single step in a workflow DAG."""

    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""

    # Execution
    action: Optional[Callable] = None
    action_name: str = ""

    # Dependencies — step IDs that must complete before this runs
    depends_on: List[str] = field(default_factory=list)

    # Conditions
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    on_failure: str = "stop"  # stop, continue, retry

    # Retry
    max_retries: int = 0
    retry_delay_seconds: float = 60.0
    retry_count: int = 0

    # State
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            StepStatus.COMPLETED, StepStatus.FAILED,
            StepStatus.SKIPPED, StepStatus.CANCELLED,
        )

    @property
    def is_ready(self) -> bool:
        return self.status == StepStatus.PENDING


@dataclass
class WorkflowDAG:
    """A complete MLOps workflow as a DAG of steps."""

    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    description: str = ""

    steps: Dict[str, WorkflowStep] = field(default_factory=dict)
    step_order: List[str] = field(default_factory=list)  # topological order

    # State
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Context shared across steps
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "steps": {sid: s.to_dict() for sid, s in self.steps.items()},
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @property
    def all_completed(self) -> bool:
        return all(s.is_terminal for s in self.steps.values())

    @property
    def has_failures(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps.values())

    def get_ready_steps(self) -> List[WorkflowStep]:
        """Get steps whose dependencies are all satisfied."""
        ready = []
        for step in self.steps.values():
            if not step.is_ready:
                continue
            deps_met = all(
                self.steps[dep_id].status == StepStatus.COMPLETED
                for dep_id in step.depends_on
                if dep_id in self.steps
            )
            if deps_met:
                ready.append(step)
        return ready


@dataclass
class WorkflowConfig:
    """Configuration for the workflow engine."""

    max_parallel_steps: int = 5
    step_timeout_seconds: float = 3600.0
    default_retries: int = 1
    auto_retry_on_failure: bool = True

    notify_on_start: bool = False
    notify_on_complete: bool = True
    notify_on_failure: bool = True


# ---------------------------------------------------------------------------
# Workflow Engine
# ---------------------------------------------------------------------------

class WorkflowEngine:
    """Executes MLOps workflows as DAGs of steps.

    Steps execute in dependency order with configurable parallelism.
    Supports conditional execution, retry, and failure handling.

    Usage::

        engine = WorkflowEngine(config)
        dag = WorkflowDAG(name="Daily Training Pipeline")

        train_step = WorkflowStep(name="Train", action=train_fn)
        eval_step = WorkflowStep(name="Evaluate", action=eval_fn, depends_on=[train_step.step_id])
        deploy_step = WorkflowStep(name="Deploy", action=deploy_fn, depends_on=[eval_step.step_id])

        dag.steps[train_step.step_id] = train_step
        dag.steps[eval_step.step_id] = eval_step
        dag.steps[deploy_step.step_id] = deploy_step
        dag.step_order = [train_step.step_id, eval_step.step_id, deploy_step.step_id]

        engine.run(dag)
    """

    def __init__(self, config: WorkflowConfig):
        self.config = config
        self._workflows: Dict[str, WorkflowDAG] = {}
        self._history: List[WorkflowDAG] = []
        self._on_step_complete: List[Callable] = []
        self._on_workflow_complete: List[Callable] = []
        self._running_threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Workflow Execution
    # ------------------------------------------------------------------

    def run(self, dag: WorkflowDAG) -> WorkflowDAG:
        """Execute a workflow DAG synchronously.

        Args:
            dag: The workflow DAG to execute.

        Returns:
            The executed workflow DAG (updated with results).
        """
        dag.started_at = time.time()
        self._workflows[dag.workflow_id] = dag

        logger.info(f"Starting workflow: {dag.name} ({dag.workflow_id})")

        # Topological sort if not provided
        if not dag.step_order:
            dag.step_order = self._topological_sort(dag)

        # Execute steps in order with parallelism
        while not dag.all_completed:
            ready = dag.get_ready_steps()

            if not ready:
                # Check for deadlock
                running = any(
                    s.status == StepStatus.RUNNING for s in dag.steps.values()
                )
                if not running:
                    # All remaining steps have unmet dependencies — deadlock
                    logger.error(f"Workflow {dag.workflow_id} deadlocked")
                    for s in dag.steps.values():
                        if s.status == StepStatus.PENDING:
                            s.status = StepStatus.FAILED
                            s.error = "Deadlock: unmet dependencies"
                    break
                time.sleep(0.01)
                continue

            # Execute ready steps in parallel (up to max_parallel)
            for step in ready[: self.config.max_parallel_steps]:
                self._execute_step(step, dag.context)

            # Small sleep to yield
            time.sleep(0.01)

        dag.completed_at = time.time()
        status = "completed" if not dag.has_failures else "failed"
        logger.info(
            f"Workflow {dag.name} {status} in {dag.completed_at - dag.started_at:.2f}s"
        )

        self._history.append(dag)
        self._notify_workflow_complete(dag)
        return dag

    def run_async(self, dag: WorkflowDAG) -> str:
        """Execute a workflow asynchronously.

        Returns:
            The workflow ID for tracking.
        """
        thread = threading.Thread(
            target=self.run,
            args=(dag,),
            daemon=True,
            name=f"workflow-{dag.workflow_id}",
        )
        self._running_threads[dag.workflow_id] = thread
        thread.start()
        return dag.workflow_id

    # ------------------------------------------------------------------
    # Step Execution
    # ------------------------------------------------------------------

    def _execute_step(
        self, step: WorkflowStep, context: Dict[str, Any]
    ) -> None:
        """Execute a single workflow step."""
        step.status = StepStatus.RUNNING
        step.started_at = time.time()

        logger.debug(f"Executing step: {step.name}")

        # Check condition
        if step.condition and not step.condition(context):
            step.status = StepStatus.SKIPPED
            step.completed_at = time.time()
            logger.info(f"Step {step.name} skipped (condition not met)")
            return

        # Execute action
        if step.action:
            try:
                result = step.action(context)
                step.result = result
                step.status = StepStatus.COMPLETED
                context[step.step_id] = result
            except Exception as e:
                step.error = str(e)
                logger.error(f"Step {step.name} failed: {e}")

                if step.retry_count < step.max_retries:
                    step.retry_count += 1
                    logger.info(
                        f"Retrying step {step.name} "
                        f"({step.retry_count}/{step.max_retries})"
                    )
                    time.sleep(step.retry_delay_seconds * 0.001)
                    self._execute_step(step, context)
                    return

                if step.on_failure == "continue":
                    step.status = StepStatus.COMPLETED
                else:
                    step.status = StepStatus.FAILED
        else:
            # No action — auto-complete
            step.status = StepStatus.COMPLETED

        step.completed_at = time.time()
        self._notify_step_complete(step)

    # ------------------------------------------------------------------
    # Workflow Building Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def create_linear_workflow(
        name: str,
        steps: List[tuple],  # [(name, action), ...]
    ) -> WorkflowDAG:
        """Create a linear (sequential) workflow DAG.

        Args:
            name: Workflow name.
            steps: List of (step_name, action_fn) tuples.

        Returns:
            Configured WorkflowDAG.
        """
        dag = WorkflowDAG(name=name)
        prev_id: Optional[str] = None

        for step_name, action in steps:
            step = WorkflowStep(name=step_name, action=action)
            if prev_id:
                step.depends_on = [prev_id]
            dag.steps[step.step_id] = step
            dag.step_order.append(step.step_id)
            prev_id = step.step_id

        return dag

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDAG]:
        """Get a workflow by ID."""
        return self._workflows.get(workflow_id)

    def get_history(self, limit: int = 50) -> List[WorkflowDAG]:
        """Get workflow execution history."""
        return sorted(
            self._history,
            key=lambda w: w.started_at or 0,
            reverse=True,
        )[:limit]

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_step_complete(self, callback: Callable) -> None:
        """Register a callback for step completion."""
        self._on_step_complete.append(callback)

    def on_workflow_complete(self, callback: Callable) -> None:
        """Register a callback for workflow completion."""
        self._on_workflow_complete.append(callback)

    def _notify_step_complete(self, step: WorkflowStep) -> None:
        for cb in self._on_step_complete:
            try:
                cb(step)
            except Exception as e:
                logger.error(f"Step callback error: {e}")

    def _notify_workflow_complete(self, dag: WorkflowDAG) -> None:
        for cb in self._on_workflow_complete:
            try:
                cb(dag)
            except Exception as e:
                logger.error(f"Workflow callback error: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _topological_sort(dag: WorkflowDAG) -> List[str]:
        """Topologically sort workflow steps (Kahn's algorithm)."""
        in_degree: Dict[str, int] = {sid: 0 for sid in dag.steps}
        for step in dag.steps.values():
            for dep_id in step.depends_on:
                if dep_id in in_degree:
                    in_degree[step.step_id] += 1

        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            sid = queue.pop(0)
            order.append(sid)
            for step in dag.steps.values():
                if sid in step.depends_on:
                    in_degree[step.step_id] -= 1
                    if in_degree[step.step_id] == 0:
                        queue.append(step.step_id)

        return order

    def reset(self) -> None:
        """Reset state (for testing)."""
        self._workflows.clear()
        self._history.clear()
        self._running_threads.clear()
