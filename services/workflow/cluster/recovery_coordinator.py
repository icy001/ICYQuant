"""Recovery Coordinator — orchestrates cross-node workflow recovery.

Responsibilities::

    Checkpoint Discovery
         │
    Journal Replay
         │
    Worker Assignment
         │
    Resume Execution

Implements cross-node recovery by loading the latest checkpoint, replaying
the execution journal, and reassigning the workflow to a healthy worker.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .checkpoint_sync import CheckpointSync
from .worker_registry import WorkerRegistry
from .dispatcher import Dispatcher, DispatchRequest, DispatchPolicy

logger = logging.getLogger(__name__)


class RecoveryPhase(str, Enum):
    """Phases of the recovery process."""

    DISCOVERY = "discovery"
    JOURNAL_REPLAY = "journal_replay"
    ASSIGNMENT = "assignment"
    RESUME = "resume"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class RecoveryTask:
    """A single recovery task for a failed workflow execution."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    workflow_id: str = ""
    failed_node_id: str = ""
    phase: RecoveryPhase = RecoveryPhase.DISCOVERY
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    assigned_node_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    replayed_entries: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return self.phase in (RecoveryPhase.COMPLETE, RecoveryPhase.FAILED)

    @property
    def duration_seconds(self) -> float:
        end = self.completed_at or datetime.utcnow()
        return (end - self.created_at).total_seconds()


class RecoveryCoordinator:
    """Coordinates cross-node workflow recovery.

    Usage::

        coordinator = RecoveryCoordinator(checkpoints=..., workers=..., dispatcher=...)
        await coordinator.start()
        tasks = await coordinator.recover_node("failed_node_abc")
    """

    def __init__(
        self,
        *,
        checkpoints: CheckpointSync,
        workers: WorkerRegistry,
        dispatcher: Dispatcher,
        max_concurrent_recoveries: int = 10,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        self._checkpoints = checkpoints
        self._workers = workers
        self._dispatcher = dispatcher
        self._max_concurrent = max_concurrent_recoveries
        self._recovery_timeout = recovery_timeout_seconds
        self._lock = threading.RLock()
        self._started = False

        # Active recovery tasks
        self._active_tasks: Dict[str, RecoveryTask] = {}

        # Recovery history
        self._history: List[RecoveryTask] = []
        self._max_history = 5000

        # Callbacks
        self._on_recovery_complete_callbacks: List[Callable] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        logger.info("RecoveryCoordinator: started")

    async def stop(self) -> None:
        self._started = False
        logger.info("RecoveryCoordinator: stopped")

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    async def recover_node(self, failed_node_id: str) -> List[RecoveryTask]:
        """Recover all workflow executions from a failed node."""
        logger.info("RecoveryCoordinator: recovering node %s", failed_node_id)

        # Step 1: Discover checkpoints for the failed node
        checkpoints = await self._checkpoints.list_checkpoints(node_id=failed_node_id)
        logger.info("RecoveryCoordinator: found %d checkpoints for node %s",
                     len(checkpoints), failed_node_id)

        tasks: List[RecoveryTask] = []
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def recover_one(ckpt: Dict[str, Any]) -> Optional[RecoveryTask]:
            async with semaphore:
                return await self._recover_execution(
                    execution_id=ckpt.get("execution_id", ""),
                    workflow_id=ckpt.get("workflow_id", ""),
                    failed_node_id=failed_node_id,
                    checkpoint_id=ckpt.get("checkpoint_id"),
                )

        coros = [recover_one(c) for c in checkpoints]
        results = await asyncio.gather(*coros, return_exceptions=True)

        for result in results:
            if isinstance(result, RecoveryTask):
                tasks.append(result)
            elif isinstance(result, Exception):
                logger.exception("RecoveryCoordinator: recovery task error")

        return tasks

    async def _recover_execution(
        self,
        execution_id: str,
        workflow_id: str,
        failed_node_id: str,
        checkpoint_id: Optional[str] = None,
    ) -> RecoveryTask:
        """Recover a single workflow execution."""
        task = RecoveryTask(
            execution_id=execution_id,
            workflow_id=workflow_id,
            failed_node_id=failed_node_id,
            checkpoint_id=checkpoint_id,
        )

        try:
            # Phase 1: Journal replay
            task.phase = RecoveryPhase.JOURNAL_REPLAY
            replayed = await self._checkpoints.replay_journal(execution_id)
            task.replayed_entries = replayed

            # Phase 2: Worker assignment
            task.phase = RecoveryPhase.ASSIGNMENT
            worker_id = await self._workers.select_best_worker()
            if worker_id is None:
                task.phase = RecoveryPhase.FAILED
                task.error = "No available workers"
                return task

            task.assigned_node_id = worker_id

            # Phase 3: Resume
            task.phase = RecoveryPhase.RESUME
            request = DispatchRequest(
                execution_id=execution_id,
                workflow_id=workflow_id,
                workflow_version="",
                policy=DispatchPolicy.AFFINITY,
            )
            result = await self._dispatcher.dispatch(request)

            if result.success:
                task.phase = RecoveryPhase.COMPLETE
                task.completed_at = datetime.utcnow()
            else:
                task.phase = RecoveryPhase.FAILED
                task.error = result.reason

        except asyncio.TimeoutError:
            task.phase = RecoveryPhase.FAILED
            task.error = "Recovery timed out"
        except Exception as e:
            task.phase = RecoveryPhase.FAILED
            task.error = str(e)
            logger.exception("RecoveryCoordinator: recovery failed for %s", execution_id)

        # Record
        with self._lock:
            self._history.append(task)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        if task.phase == RecoveryPhase.COMPLETE:
            for cb in self._on_recovery_complete_callbacks:
                try:
                    cb(task)
                except Exception:
                    logger.exception("RecoveryCoordinator: callback error")

        return task

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_recovery_status(self, execution_id: str) -> Optional[RecoveryTask]:
        """Get the recovery status for an execution."""
        with self._lock:
            for task in reversed(self._history):
                if task.execution_id == execution_id:
                    return task
            return None

    async def get_recovery_history(self, limit: int = 100) -> List[RecoveryTask]:
        with self._lock:
            return list(self._history[-limit:])

    async def active_recovery_count(self) -> int:
        with self._lock:
            return len(self._active_tasks)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_recovery_complete(self, callback: Callable) -> None:
        self._on_recovery_complete_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            completed = sum(1 for t in self._history[-1000:] if t.phase == RecoveryPhase.COMPLETE)
            failed = sum(1 for t in self._history[-1000:] if t.phase == RecoveryPhase.FAILED)
            return {
                "active_recoveries": len(self._active_tasks),
                "total_recoveries": len(self._history),
                "recent_completed": completed,
                "recent_failed": failed,
                "success_rate": completed / max(1, completed + failed),
            }
