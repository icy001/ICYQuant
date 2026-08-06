"""
Scheduler — orchestrates DAG node execution by driving the Ready Queue and Worker Pool.

The scheduler is the central coordination point:
    Ready Node → Dispatch → Worker → Retry/Timeout → Completion → Next Ready Nodes
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from services.workflow.dag.dag import DAG, DAGStatus
from services.workflow.dag.dependency_resolver import DependencyResolver
from services.workflow.dag.ready_queue import ReadyQueue, QueueDiscipline
from services.workflow.dag.dispatcher import Dispatcher
from services.workflow.dag.parallel_executor import ParallelExecutor
from services.workflow.dag.retry_scheduler import RetryScheduler
from services.workflow.dag.timeout_manager import TimeoutManager

logger = logging.getLogger(__name__)


class SchedulerStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    DRAINING = "draining"
    STOPPED = "stopped"


@dataclass
class ScheduleStats:
    """Runtime statistics for the scheduler."""

    total_dispatched: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_retried: int = 0
    total_timed_out: int = 0
    peak_parallelism: int = 0
    current_parallelism: int = 0


class Scheduler:
    """
    DAG Scheduler — drives workflow execution through the DAG.

    Responsibilities:
    1. Populate ready queue with source nodes
    2. Dispatch ready nodes to workers
    3. On completion, resolve dependencies and enqueue newly-ready nodes
    4. Handle retries and timeouts
    5. Track overall progress and completion
    """

    def __init__(
        self,
        dispatcher: Optional[Dispatcher] = None,
        executor: Optional[ParallelExecutor] = None,
        retry_scheduler: Optional[RetryScheduler] = None,
        timeout_manager: Optional[TimeoutManager] = None,
    ):
        self.dispatcher = dispatcher or Dispatcher()
        self.executor = executor or ParallelExecutor()
        self.retry_scheduler = retry_scheduler or RetryScheduler()
        self.timeout_manager = timeout_manager or TimeoutManager()

        self._ready_queue: Optional[ReadyQueue] = None
        self._resolver: Optional[DependencyResolver] = None
        self._dag: Optional[DAG] = None
        self._status = SchedulerStatus.IDLE
        self._stats = ScheduleStats()
        self._completion_event = asyncio.Event()
        self._failure_event = asyncio.Event()
        self._running_tasks: Dict[str, asyncio.Task] = {}

    async def schedule(self, dag: DAG, resolver: DependencyResolver) -> bool:
        """
        Execute the full DAG through the scheduler.

        Returns True if all nodes completed successfully.
        """
        self._dag = dag
        self._resolver = resolver
        self._ready_queue = ReadyQueue(discipline=QueueDiscipline.PRIORITY)
        self._status = SchedulerStatus.RUNNING
        self._stats = ScheduleStats()
        self._completion_event.clear()
        self._failure_event.clear()
        self._running_tasks.clear()

        dag.status = DAGStatus.EXECUTING

        # Phase 1: Enqueue source nodes
        initial_ready = await resolver.get_ready_nodes()
        if not initial_ready:
            # No source nodes — try the resolver's initial state
            for node_id in dag.nodes:
                if dag.nodes[node_id].is_source:
                    initial_ready.append(node_id)

        await self._ready_queue.enqueue_batch([(nid, 0) for nid in initial_ready])

        # Phase 2: Main scheduling loop
        try:
            while True:
                # Check completion
                if await resolver.is_complete():
                    break

                # Check failures
                if await resolver.has_failures():
                    dag.status = DAGStatus.FAILED
                    self._failure_event.set()
                    return False

                # Get next batch of ready nodes
                ready_nodes = await self._ready_queue.dequeue_batch(
                    max_count=self._dag.node_count
                )

                if not ready_nodes:
                    # Wait for new ready nodes or completion
                    try:
                        done, pending = await asyncio.wait(
                            [
                                asyncio.create_task(resolver.wait_for_ready(timeout=1.0)),
                                asyncio.create_task(self._check_running_completion()),
                            ],
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        for task in pending:
                            task.cancel()
                    except asyncio.TimeoutError:
                        continue
                    ready_nodes = await resolver.get_ready_nodes()
                    if ready_nodes:
                        await self._ready_queue.enqueue_batch([(nid, 0) for nid in ready_nodes])
                    continue

                # Dispatch ready nodes
                for node_id in ready_nodes:
                    await resolver.mark_running(node_id)
                    task = asyncio.create_task(
                        self._execute_node(node_id),
                        name=f"sched_{node_id}",
                    )
                    self._running_tasks[node_id] = task
                    self._stats.total_dispatched += 1

                self._stats.current_parallelism = len(self._running_tasks)
                self._stats.peak_parallelism = max(
                    self._stats.peak_parallelism, self._stats.current_parallelism
                )

        except asyncio.CancelledError:
            dag.status = DAGStatus.CANCELLED
            self._status = SchedulerStatus.STOPPED
            return False

        dag.status = DAGStatus.COMPLETED
        self._status = SchedulerStatus.IDLE
        self._completion_event.set()
        return True

    async def _execute_node(self, node_id: str) -> None:
        """Execute a single node with retry and timeout handling."""
        dag_node = self._dag.nodes.get(node_id) if self._dag else None
        if not dag_node:
            await self._resolver.mark_failed(node_id)
            return

        try:
            # Apply timeout if configured
            timeout = self.timeout_manager.get_timeout(node_id)
            if timeout:
                result = await asyncio.wait_for(
                    self.dispatcher.dispatch(dag_node.node),
                    timeout=timeout,
                )
            else:
                result = await self.dispatcher.dispatch(dag_node.node)

            if result.success:
                await self._resolver.mark_completed(node_id)
                self._stats.total_completed += 1
                # Enqueue newly ready dependents
                newly_ready = await self._resolver.get_ready_nodes()
                if newly_ready:
                    await self._ready_queue.enqueue_batch([(nid, 0) for nid in newly_ready])
            else:
                # Check retry policy
                if self.retry_scheduler.should_retry(node_id, result):
                    self._stats.total_retried += 1
                    await self.retry_scheduler.schedule_retry(node_id, self._ready_queue)
                else:
                    await self._resolver.mark_failed(node_id)
                    self._stats.total_failed += 1

        except asyncio.TimeoutError:
            self._stats.total_timed_out += 1
            if self.retry_scheduler.should_retry(node_id, None):
                self._stats.total_retried += 1
                await self.retry_scheduler.schedule_retry(node_id, self._ready_queue)
            else:
                await self._resolver.mark_failed(node_id)
                self._stats.total_failed += 1

        except Exception:
            logger.exception(f"Unexpected error executing node {node_id}")
            await self._resolver.mark_failed(node_id)
            self._stats.total_failed += 1

        finally:
            self._running_tasks.pop(node_id, None)
            self._stats.current_parallelism = len(self._running_tasks)

    async def _check_running_completion(self) -> None:
        """Wait for any running task to complete."""
        if self._running_tasks:
            done, _ = await asyncio.wait(
                list(self._running_tasks.values()),
                return_when=asyncio.FIRST_COMPLETED,
            )

    async def pause(self) -> None:
        """Pause the scheduler (stop dispatching new nodes)."""
        self._status = SchedulerStatus.PAUSED

    async def resume(self) -> None:
        """Resume the scheduler."""
        if self._status == SchedulerStatus.PAUSED:
            self._status = SchedulerStatus.RUNNING

    async def stop(self) -> None:
        """Gracefully stop the scheduler."""
        self._status = SchedulerStatus.DRAINING
        for task in self._running_tasks.values():
            task.cancel()
        self._status = SchedulerStatus.STOPPED

    @property
    def status(self) -> SchedulerStatus:
        return self._status

    @property
    def stats(self) -> ScheduleStats:
        return self._stats
