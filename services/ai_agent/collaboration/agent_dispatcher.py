"""Agent Dispatcher — task dispatch engine that executes routed tasks on agents.

Pipeline:
    DispatchTask (agent + payload + timeout)
        -> AgentDispatcher.dispatch() (validate + prepare)
        -> invoke agent handler (execute)
        -> DispatchResult (status + output + timing)
        -> MessageBus (publish result event)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from services.ai_agent.collaboration.agent_registry import (
    AgentRegistration,
    AgentRegistry,
    AgentStatus,
)
from services.ai_agent.collaboration.agent_router import (
    AgentRouter,
    RouteDecision,
)
from services.ai_agent.collaboration.agent_scheduler import (
    AgentScheduler,
    ScheduleRequest,
    TaskPriority,
)

logger = logging.getLogger(__name__)


class DispatchStatus(str, Enum):
    """Status of a dispatch operation."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class DispatchTask:
    """A task to be dispatched to an agent.

    Attributes:
        task_id: Unique task identifier.
        agent_id: Target agent ID.
        payload: Task payload data.
        timeout_seconds: Maximum execution time.
        priority: Task priority.
        metadata: Additional dispatch metadata.
    """

    task_id: str = ""
    agent_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 60.0
    priority: TaskPriority = TaskPriority.MEDIUM
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DispatchResult:
    """Result of a task dispatch operation.

    Attributes:
        task_id: Original task identifier.
        agent_id: Agent that executed the task.
        status: Final dispatch status.
        output: Task output data.
        error: Error message if failed.
        duration_ms: Execution duration in milliseconds.
        started_at: Execution start time.
        finished_at: Execution end time.
    """

    task_id: str = ""
    agent_id: str = ""
    status: DispatchStatus = DispatchStatus.PENDING
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0

    @property
    def is_success(self) -> bool:
        """Return whether the dispatch was successful."""
        return self.status == DispatchStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        """Return result as a dictionary."""
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "output": str(self.output)[:500] if self.output else None,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class AgentDispatcher:
    """Task dispatch engine for the multi-agent system.

    Receives routing decisions and scheduler plans, then dispatches tasks
    to agent handlers for execution. Manages concurrency, timeouts, and
    result collection.

    Supports:
        - Single-task dispatch
        - Batch/parallel dispatch
        - Timeout enforcement
        - Agent status management during execution
        - Result aggregation

    Usage:
        dispatcher = AgentDispatcher(router, scheduler)
        await dispatcher.initialize()
        task = DispatchTask(task_id="t1", agent_id="a1", payload={...})
        result = await dispatcher.dispatch(task)
    """

    def __init__(self, router: AgentRouter, scheduler: AgentScheduler) -> None:
        """Initialize the dispatcher.

        Args:
            router: Agent router for routing decisions.
            scheduler: Agent scheduler for task sequencing.
        """
        self._router: AgentRouter = router
        self._scheduler: AgentScheduler = scheduler
        self._initialized: bool = False
        logger.info("AgentDispatcher created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the dispatcher."""
        if self._initialized:
            logger.warning("AgentDispatcher already initialized")
            return
        self._initialized = True
        logger.info("AgentDispatcher initialized")

    async def shutdown(self) -> None:
        """Shut down the dispatcher."""
        if not self._initialized:
            return
        self._initialized = False
        logger.info("AgentDispatcher shutdown complete")

    # ── Dispatch ──

    async def dispatch(self, task: DispatchTask) -> DispatchResult:
        """Dispatch a single task to an agent for execution.

        Args:
            task: The task to dispatch.

        Returns:
            DispatchResult with execution status and output.
        """
        if not self._initialized:
            raise RuntimeError("AgentDispatcher not initialized")

        self._scheduler.mark_running(task.task_id)

        result = DispatchResult(
            task_id=task.task_id,
            agent_id=task.agent_id,
            status=DispatchStatus.RUNNING,
            started_at=time.monotonic(),
        )

        try:
            # Execute with timeout
            output = await asyncio.wait_for(
                self._execute_task(task),
                timeout=task.timeout_seconds,
            )
            result.status = DispatchStatus.SUCCESS
            result.output = output
            self._scheduler.mark_completed(task.task_id)
            logger.info("Task dispatched successfully: %s (agent=%s)",
                        task.task_id, task.agent_id)

        except asyncio.TimeoutError:
            result.status = DispatchStatus.TIMEOUT
            result.error = f"Task timed out after {task.timeout_seconds}s"
            self._scheduler.mark_failed(task.task_id)
            logger.error("Task timeout: %s (agent=%s)", task.task_id, task.agent_id)

        except Exception as e:
            result.status = DispatchStatus.FAILED
            result.error = str(e)
            self._scheduler.mark_failed(task.task_id)
            logger.exception("Task failed: %s (agent=%s)", task.task_id, task.agent_id)

        finally:
            result.finished_at = time.monotonic()
            result.duration_ms = (result.finished_at - result.started_at) * 1000

        return result

    async def dispatch_all(
        self, tasks: List[DispatchTask],
    ) -> List[DispatchResult]:
        """Dispatch multiple tasks in parallel.

        Args:
            tasks: List of tasks to dispatch.

        Returns:
            List of dispatch results (one per task).
        """
        if not tasks:
            return []

        coros = [self.dispatch(task) for task in tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        output: List[DispatchResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                output.append(DispatchResult(
                    task_id=tasks[i].task_id if i < len(tasks) else "unknown",
                    agent_id=tasks[i].agent_id if i < len(tasks) else "unknown",
                    status=DispatchStatus.FAILED,
                    error=str(result),
                ))
            else:
                output.append(result)

        return output

    async def dispatch_from_decision(self, decision: RouteDecision) -> List[DispatchResult]:
        """Dispatch tasks based on a routing decision.

        Args:
            decision: The route decision with selected agents.

        Returns:
            List of dispatch results.
        """
        import uuid

        tasks: List[DispatchTask] = []
        for i, selected in enumerate(decision.selected_agents):
            task = DispatchTask(
                task_id=uuid.uuid4().hex[:12],
                agent_id=selected.agent.agent_id,
                payload={
                    "task_description": decision.request.task_description,
                    "context": decision.request.context,
                    "route_rank": i,
                },
            )
            tasks.append(task)

        return await self.dispatch_all(tasks)

    # ── Task Execution ──

    async def _execute_task(self, task: DispatchTask) -> Any:
        """Execute a task by invoking the agent handler.

        This is a placeholder that would invoke the actual agent's handler.
        In the full implementation, this would look up the agent instance
        and call its execute method.

        Args:
            task: The task to execute.

        Returns:
            Task execution output.
        """
        # In full implementation, this would:
        #   1. Look up agent from registry
        #   2. Check agent is callable
        #   3. Invoke agent.execute(task.payload)
        #   4. Return result
        logger.debug("Executing task: %s on agent: %s", task.task_id, task.agent_id)

        # Simulate execution for now
        await asyncio.sleep(0.01)
        return {"task_id": task.task_id, "status": "executed"}

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the dispatcher state.

        Returns:
            Dict with initialization status.
        """
        return {
            "initialized": self._initialized,
        }
