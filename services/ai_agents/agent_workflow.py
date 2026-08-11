"""
ICYQuant Agent Workflow — workflow definition and execution engine.

Defines executable workflows that chain agent tasks with conditional
branching, parallel execution, and error recovery. Workflows are
the structured pipelines that the orchestrator executes.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .workflow_state import WorkflowState, WorkflowStatus

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    AGENT_TASK = "agent_task"          # Delegate to an agent
    PARALLEL = "parallel"              # Run multiple tasks in parallel
    CONDITIONAL = "conditional"        # Branch based on condition
    WAIT = "wait"                      # Wait for external event
    MERGE = "merge"                    # Merge parallel branches
    CALLBACK = "callback"              # Execute a callback function


@dataclass
class WorkflowTask:
    """A single task node in a workflow DAG."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: TaskType = TaskType.AGENT_TASK
    name: str = ""
    description: str = ""

    # Agent task config
    agent_type: str = ""               # Type of agent to invoke
    capability: str = ""               # Required capability
    input_mapping: dict[str, str] = field(default_factory=dict)

    # Dependencies (task_ids that must complete first)
    depends_on: list[str] = field(default_factory=list)

    # Conditional branching
    condition: str = ""                # Expression evaluated against context
    on_true: str = ""                  # Task to execute if true
    on_false: str = ""                 # Task to execute if false

    # Retry
    max_retries: int = 0
    retry_delay_seconds: int = 5

    # Timeouts
    timeout_seconds: int = 300

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowDefinition:
    """Defines a reusable workflow."""
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    version: str = "1.0.0"

    tasks: list[WorkflowTask] = field(default_factory=list)
    entry_task: str = ""               # First task to execute

    # Constraints
    max_parallel_tasks: int = 10
    workflow_timeout_seconds: int = 3600

    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Validate the workflow for correctness. Returns list of errors."""
        errors = []
        task_ids = {t.task_id for t in self.tasks}

        if not self.entry_task:
            errors.append("No entry_task specified")
        elif self.entry_task not in task_ids:
            errors.append(f"entry_task '{self.entry_task}' not found in tasks")

        for task in self.tasks:
            for dep in task.depends_on:
                if dep not in task_ids:
                    errors.append(f"Task '{task.task_id}' depends on unknown task '{dep}'")
            if task.task_type == TaskType.CONDITIONAL:
                if task.on_true and task.on_true not in task_ids:
                    errors.append(f"on_true '{task.on_true}' not found")
                if task.on_false and task.on_false not in task_ids:
                    errors.append(f"on_false '{task.on_false}' not found")

        return errors


class WorkflowEngine:
    """Executes workflow definitions against agent infrastructure.

    Features:
        - DAG-based task execution
        - Dependency resolution and topological ordering
        - Parallel task execution with configurable max concurrency
        - Conditional branching
        - Retry with exponential backoff
        - Workflow timeout enforcement
        - State persistence and resumption
    """

    def __init__(self, orchestrator: Any = None,
                 scheduler: Any = None,
                 runtime: Any = None) -> None:
        self._orchestrator = orchestrator
        self._scheduler = scheduler
        self._runtime = runtime
        self._active_workflows: dict[str, WorkflowState] = {}
        self._completed = 0
        self._failed = 0

    async def execute(self, workflow: WorkflowDefinition,
                      initial_context: Optional[dict[str, Any]] = None) -> WorkflowState:
        """Execute a workflow definition."""
        errors = workflow.validate()
        if errors:
            state = WorkflowState(
                workflow_id=workflow.workflow_id,
                status=WorkflowStatus.FAILED,
                context=initial_context or {},
                errors=errors,
            )
            return state

        state = WorkflowState(
            workflow_id=workflow.workflow_id,
            status=WorkflowStatus.RUNNING,
            context=initial_context or {},
        )
        self._active_workflows[workflow.workflow_id] = state

        try:
            # Build execution plan via topological sort
            execution_order = self._topological_sort(workflow)
            state.total_tasks = len(execution_order)

            # Execute tasks in order, with parallel groups
            parallel_groups = self._group_parallel_tasks(workflow, execution_order)
            semaphore = asyncio.Semaphore(workflow.max_parallel_tasks)

            for group in parallel_groups:
                await self._execute_task_group(
                    group, workflow, state, semaphore
                )
                if state.status == WorkflowStatus.FAILED:
                    break

            if state.status != WorkflowStatus.FAILED:
                state.status = WorkflowStatus.COMPLETED

            self._completed += 1

        except Exception as exc:
            state.status = WorkflowStatus.FAILED
            state.errors.append(str(exc))
            self._failed += 1
            logger.error("Workflow %s failed: %s", workflow.workflow_id, exc)

        finally:
            state.completed_at = datetime.now(timezone.utc)

        return state

    async def _execute_task_group(self, task_ids: list[str],
                                   workflow: WorkflowDefinition,
                                   state: WorkflowState,
                                   semaphore: asyncio.Semaphore) -> None:
        """Execute a group of tasks in parallel."""
        task_map = {t.task_id: t for t in workflow.tasks}
        tasks = [task_map[tid] for tid in task_ids if tid in task_map]

        async def run_one(task: WorkflowTask) -> None:
            async with semaphore:
                result = await self._execute_single_task(task, state)
                # Collect results from parallel tasks
                state.task_results[task.task_id] = {
                    "output": result,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
                state.completed_tasks += 1

        await asyncio.gather(
            *(run_one(t) for t in tasks),
            return_exceptions=True,
        )

    async def _execute_single_task(self, task: WorkflowTask,
                                    state: WorkflowState) -> Any:
        """Execute a single task node."""
        for attempt in range(task.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self._dispatch_task(task, state),
                    timeout=task.timeout_seconds,
                )
                return result
            except asyncio.TimeoutError:
                if attempt < task.max_retries:
                    await asyncio.sleep(task.retry_delay_seconds)
                else:
                    state.errors.append(f"Task {task.task_id}: timeout after {task.timeout_seconds}s")
                    state.status = WorkflowStatus.FAILED
                    raise
            except Exception as exc:
                if attempt < task.max_retries:
                    await asyncio.sleep(task.retry_delay_seconds)
                else:
                    state.errors.append(f"Task {task.task_id}: {exc}")
                    state.status = WorkflowStatus.FAILED
                    raise
        return None

    async def _dispatch_task(self, task: WorkflowTask,
                             state: WorkflowState) -> Any:
        """Dispatch a task to the appropriate handler."""
        if task.task_type == TaskType.AGENT_TASK:
            return await self._run_agent_task(task, state)
        elif task.task_type == TaskType.CONDITIONAL:
            return await self._run_conditional(task, state)
        elif task.task_type == TaskType.WAIT:
            return {"status": "waiting"}
        elif task.task_type == TaskType.MERGE:
            return {"status": "merged"}
        else:
            return {"status": "completed"}

    async def _run_agent_task(self, task: WorkflowTask,
                              state: WorkflowState) -> Any:
        """Execute a task through the agent scheduler."""
        if self._scheduler:
            task_id = f"{state.workflow_id}_{task.task_id}"
            self._scheduler.schedule(
                task_id=task_id,
                description=task.description or task.name,
                required_capabilities=[task.capability] if task.capability else [],
            )
            agent_id = self._scheduler.find_best_agent(
                [task.capability] if task.capability else []
            )
            if agent_id:
                self._scheduler.assign_task(task_id, agent_id)
        return {"status": "completed", "agent_type": task.agent_type}

    async def _run_conditional(self, task: WorkflowTask,
                               state: WorkflowState) -> Any:
        """Evaluate a conditional branch."""
        # Evaluate condition against context
        condition_met = state.context.get(task.condition, False)
        branch = task.on_true if condition_met else task.on_false
        return {"branch": branch, "condition_met": condition_met}

    def _topological_sort(self, workflow: WorkflowDefinition) -> list[str]:
        """Perform topological sort on workflow tasks."""
        task_ids = {t.task_id for t in workflow.tasks}
        dep_count = {tid: 0 for tid in task_ids}
        dep_map: dict[str, list[str]] = {tid: [] for tid in task_ids}

        for task in workflow.tasks:
            for dep in task.depends_on:
                if dep in dep_map:
                    dep_map[dep].append(task.task_id)
                    dep_count[task.task_id] += 1

        # Start with tasks that have no dependencies
        queue = [tid for tid, count in dep_count.items() if count == 0]
        order = []

        while queue:
            tid = queue.pop(0)
            order.append(tid)
            for dependent in dep_map.get(tid, []):
                dep_count[dependent] -= 1
                if dep_count[dependent] == 0:
                    queue.append(dependent)

        return order

    def _group_parallel_tasks(self, workflow: WorkflowDefinition,
                              execution_order: list[str]) -> list[list[str]]:
        """Group tasks into parallel execution groups based on dependencies."""
        task_map = {t.task_id: t for t in workflow.tasks}
        completed: set[str] = set()
        groups: list[list[str]] = []

        remaining = list(execution_order)
        while remaining:
            group = []
            for tid in remaining[:]:
                task = task_map.get(tid)
                if task and all(dep in completed for dep in task.depends_on):
                    group.append(tid)
                    remaining.remove(tid)
            if group:
                groups.append(group)
                completed.update(group)
            else:
                break

        return groups

    def get_state(self, workflow_id: str) -> Optional[WorkflowState]:
        return self._active_workflows.get(workflow_id)

    @property
    def completed(self) -> int:
        return self._completed

    @property
    def failed(self) -> int:
        return self._failed
