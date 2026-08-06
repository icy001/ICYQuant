"""Failover Manager — automatic failover for failed workflow nodes.

Flow::

    Node Failure
         │
    Lease Expired
         │
    Recover Task
         │
    Redispatch
         │
    Continue Workflow

Goals:
* Zero manual intervention
* Minimal Recovery Time Objective (RTO)
* At-most-once execution semantics via lease fencing
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

from .cluster_node import ClusterNode
from .lease_manager import LeaseManager, LeaseType
from .worker_registry import WorkerRegistry
from .dispatcher import Dispatcher, DispatchRequest, DispatchPolicy

logger = logging.getLogger(__name__)


class FailoverState(str, Enum):
    """States in the failover process."""

    DETECTED = "detected"
    LEASE_EXPIRED = "lease_expired"
    RECOVERING = "recovering"
    REDISPATCHING = "redispatching"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class FailoverRecord:
    """Record of a failover event."""

    failover_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    failed_node_id: str = ""
    state: FailoverState = FailoverState.DETECTED
    detected_at: datetime = field(default_factory=datetime.utcnow)
    recovered_at: Optional[datetime] = None
    affected_executions: List[str] = field(default_factory=list)
    recovered_executions: List[str] = field(default_factory=list)
    failed_executions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        end = self.recovered_at or datetime.utcnow()
        return (end - self.detected_at).total_seconds()

    @property
    def recovery_rate(self) -> float:
        total = len(self.affected_executions)
        if total == 0:
            return 1.0
        return len(self.recovered_executions) / total


class FailoverManager:
    """Manages automatic failover for failed nodes.

    Usage::

        failover = FailoverManager(leases=..., workers=..., dispatcher=...)
        await failover.start()
        # When a node fails, failover is triggered automatically
    """

    def __init__(
        self,
        *,
        leases: LeaseManager,
        workers: WorkerRegistry,
        dispatcher: Dispatcher,
        max_retry_attempts: int = 3,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        self._leases = leases
        self._workers = workers
        self._dispatcher = dispatcher
        self._max_retry_attempts = max_retry_attempts
        self._retry_delay = retry_delay_seconds
        self._lock = threading.RLock()
        self._started = False

        # Execution tracking: execution_id → node_id
        self._execution_owner: Dict[str, str] = {}

        # Failover history
        self._history: List[FailoverRecord] = []
        self._max_history = 1000

        # Callbacks
        self._on_failover_callbacks: List[Callable] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        logger.info("FailoverManager: started")

    async def stop(self) -> None:
        self._started = False
        logger.info("FailoverManager: stopped")

    # ------------------------------------------------------------------
    # Failover
    # ------------------------------------------------------------------

    async def handle_node_failure(self, failed_node_id: str) -> FailoverRecord:
        """Handle the failure of a node, recovering affected workflows.

        This is the main entry point triggered by the coordinator when a
        node heartbeat times out.
        """
        record = FailoverRecord(
            failed_node_id=failed_node_id,
            state=FailoverState.DETECTED,
        )

        logger.warning("FailoverManager: handling failure of node %s", failed_node_id)

        try:
            # Step 1: Expire leases held by the failed node
            record.state = FailoverState.LEASE_EXPIRED
            await self._expire_node_leases(failed_node_id)

            # Step 2: Mark worker as unavailable
            await self._workers.mark_unavailable(failed_node_id)

            # Step 3: Find affected executions
            record.state = FailoverState.RECOVERING
            affected = await self._find_affected_executions(failed_node_id)
            record.affected_executions = affected
            logger.info("FailoverManager: %d executions affected by node %s failure",
                         len(affected), failed_node_id)

            # Step 4: Redispatch each affected execution
            record.state = FailoverState.REDISPATCHING
            for execution_id in affected:
                success = await self._redispatch_execution(execution_id)
                if success:
                    record.recovered_executions.append(execution_id)
                else:
                    record.failed_executions.append(execution_id)

            record.state = FailoverState.COMPLETED
            record.recovered_at = datetime.utcnow()

            logger.info("FailoverManager: recovered %d/%d executions for node %s",
                         len(record.recovered_executions), len(affected), failed_node_id)

        except Exception:
            logger.exception("FailoverManager: failover failed for node %s", failed_node_id)
            record.state = FailoverState.FAILED

        # Record history
        with self._lock:
            self._history.append(record)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        # Notify callbacks
        for cb in self._on_failover_callbacks:
            try:
                cb(record)
            except Exception:
                logger.exception("FailoverManager: callback error")

        return record

    async def _expire_node_leases(self, node_id: str) -> None:
        """Expire all leases held by a failed node."""
        leases = await self._leases.list_leases(owner_id=node_id)
        for lease in leases:
            await self._leases.release(lease.lease_id)
        logger.debug("FailoverManager: expired %d leases for node %s", len(leases), node_id)

    async def _find_affected_executions(self, node_id: str) -> List[str]:
        """Find all executions owned by a failed node."""
        with self._lock:
            return [eid for eid, nid in self._execution_owner.items() if nid == node_id]

    async def _redispatch_execution(self, execution_id: str) -> bool:
        """Redispatch a failed execution to a new worker."""
        for attempt in range(self._max_retry_attempts):
            try:
                request = DispatchRequest(
                    execution_id=execution_id,
                    workflow_id="",  # Would be looked up from execution context
                    workflow_version="",
                    policy=DispatchPolicy.BALANCED,
                )
                result = await self._dispatcher.dispatch(request)
                if result.success:
                    with self._lock:
                        self._execution_owner[execution_id] = result.node_id
                    return True
            except Exception:
                logger.exception("FailoverManager: redispatch attempt %d failed for %s",
                                 attempt + 1, execution_id)

            await asyncio.sleep(self._retry_delay * (attempt + 1))

        return False

    # ------------------------------------------------------------------
    # Execution tracking
    # ------------------------------------------------------------------

    async def track_execution(self, execution_id: str, node_id: str) -> None:
        """Register an execution as owned by a node."""
        with self._lock:
            self._execution_owner[execution_id] = node_id

    async def untrack_execution(self, execution_id: str) -> None:
        """Remove an execution from tracking."""
        with self._lock:
            self._execution_owner.pop(execution_id, None)

    async def get_execution_owner(self, execution_id: str) -> Optional[str]:
        with self._lock:
            return self._execution_owner.get(execution_id)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_failover(self, callback: Callable) -> None:
        self._on_failover_callbacks.append(callback)

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def get_failover_history(self, limit: int = 100) -> List[FailoverRecord]:
        with self._lock:
            return list(self._history[-limit:])

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "tracked_executions": len(self._execution_owner),
                "failover_count": len(self._history),
                "last_failover": self._history[-1].failover_id if self._history else None,
            }
