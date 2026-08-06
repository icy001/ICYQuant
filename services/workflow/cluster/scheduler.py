"""Distributed Scheduler — orchestrates workflow execution across the cluster.

Flow::

    Workflow Submitted
         │
    Shard Selection
         │
    Worker Selection
         │
    Dispatch

Supports:
* Load-aware scheduling
* Priority-based ordering
* Locality-aware placement
* Affinity rules
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .worker_registry import WorkerRegistry
from .shard_manager import ShardManager
from .placement_strategy import PlacementStrategy, PlacementDecision
from .load_balancer import LoadBalancer, LoadBalancerAlgorithm

logger = logging.getLogger(__name__)


class SchedulePriority(int, Enum):
    """Priority levels for workflow scheduling."""

    LOW = 0
    NORMAL = 50
    HIGH = 100
    CRITICAL = 200


@dataclass(order=True)
class ScheduleRequest:
    """A request to schedule a workflow execution."""

    priority: SchedulePriority = SchedulePriority.NORMAL
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    execution_id: str = ""
    workflow_version: str = "1.0.0"
    inputs: Dict[str, Any] = field(default_factory=dict)
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    affinity_tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "workflow_version": self.workflow_version,
            "priority": self.priority.value,
            "inputs": dict(self.inputs),
            "submitted_at": self.submitted_at.isoformat(),
            "affinity_tags": list(self.affinity_tags),
            "metadata": dict(self.metadata),
        }


@dataclass
class ScheduleResult:
    """Result of a scheduling decision."""

    request_id: str
    assigned_node_id: str
    assigned_shard_id: str
    scheduled_at: datetime = field(default_factory=datetime.utcnow)
    success: bool = True
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class DistributedScheduler:
    """Distributed workflow scheduler with load-aware placement.

    Usage::

        scheduler = DistributedScheduler(workers=..., shards=..., balancer=...)
        await scheduler.start()
        result = await scheduler.schedule(request)
    """

    def __init__(
        self,
        *,
        workers: WorkerRegistry,
        shards: ShardManager,
        balancer: LoadBalancer,
        placement: PlacementStrategy,
    ) -> None:
        self._workers = workers
        self._shards = shards
        self._balancer = balancer
        self._placement = placement
        self._lock = threading.RLock()
        self._started = False

        # Priority queue
        self._queue: List[ScheduleRequest] = []
        self._queue_lock = threading.Lock()

        # Schedule task
        self._schedule_task: Optional[asyncio.Task] = None

        # History
        self._schedule_history: List[ScheduleResult] = []
        self._max_history = 10000

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        self._schedule_task = asyncio.create_task(self._schedule_loop())
        logger.info("DistributedScheduler: started")

    async def stop(self) -> None:
        self._started = False
        if self._schedule_task:
            self._schedule_task.cancel()
            try:
                await self._schedule_task
            except asyncio.CancelledError:
                pass
        logger.info("DistributedScheduler: stopped")

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    async def schedule(self, request: ScheduleRequest) -> ScheduleResult:
        """Schedule a workflow execution request.

        This is the main scheduling entry point. The request goes through:
        1. Shard selection
        2. Worker selection (via load balancer + placement strategy)
        3. Dispatch
        """
        # Step 1: Select shard
        shard_id = await self._shards.assign_shard(request.workflow_id)

        # Step 2: Get candidate workers
        candidates = await self._workers.list_workers(available_only=True)
        if not candidates:
            return ScheduleResult(
                request_id=request.request_id,
                assigned_node_id="",
                assigned_shard_id=shard_id,
                success=False,
                reason="No available workers",
            )

        # Step 3: Apply placement strategy
        decision = await self._placement.decide(
            request=request,
            candidates=[w.node_id for w in candidates],
            shard_id=shard_id,
        )

        if not decision.selected_node_id:
            return ScheduleResult(
                request_id=request.request_id,
                assigned_node_id="",
                assigned_shard_id=shard_id,
                success=False,
                reason=decision.reason or "Placement failed",
            )

        result = ScheduleResult(
            request_id=request.request_id,
            assigned_node_id=decision.selected_node_id,
            assigned_shard_id=shard_id,
            metadata={"placement_score": decision.score},
        )

        # Record history
        with self._lock:
            self._schedule_history.append(result)
            if len(self._schedule_history) > self._max_history:
                self._schedule_history = self._schedule_history[-self._max_history:]

        return result

    async def enqueue(self, request: ScheduleRequest) -> None:
        """Add a request to the priority queue for async scheduling."""
        with self._queue_lock:
            self._queue.append(request)
            self._queue.sort(key=lambda r: r.priority.value, reverse=True)

    async def _schedule_loop(self) -> None:
        """Background loop that processes the priority queue."""
        while self._started:
            try:
                await asyncio.sleep(0.1)
                with self._queue_lock:
                    if not self._queue:
                        continue
                    request = self._queue.pop(0)

                await self.schedule(request)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("DistributedScheduler: error in schedule loop")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def queue_size(self) -> int:
        with self._queue_lock:
            return len(self._queue)

    async def get_schedule_history(self, limit: int = 100) -> List[ScheduleResult]:
        with self._lock:
            return list(self._schedule_history[-limit:])

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "queue_size": len(self._queue),
            "history_size": len(self._schedule_history),
            "balancer": self._balancer.health_report(),
        }
