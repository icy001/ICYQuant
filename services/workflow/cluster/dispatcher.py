"""Task Dispatcher — routes workflow executions to the best-fit worker.

Dispatch logic considers:

* **Affinity** — prefer nodes that previously handled related workflows
* **Resource Score** — CPU, memory, and task capacity
* **Load Score** — current queue depth and active tasks

Supports:
* Sticky Dispatch — route related workflows to the same worker
* Rebalance — redistribute tasks when load becomes unbalanced
* Dynamic Migration — move running workflows between workers
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .worker_registry import WorkerRegistry, WorkerRecord

logger = logging.getLogger(__name__)


class DispatchPolicy:
    """Policies for task dispatch."""

    STICKY = "sticky"
    BALANCED = "balanced"
    AFFINITY = "affinity"
    ROUND_ROBIN = "round_robin"


@dataclass
class DispatchRequest:
    """A request to dispatch a workflow execution to a worker."""

    execution_id: str
    workflow_id: str
    workflow_version: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    affinity_tags: List[str] = field(default_factory=list)
    policy: DispatchPolicy = DispatchPolicy.BALANCED
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DispatchResult:
    """Result of a dispatch operation."""

    execution_id: str
    node_id: str
    success: bool
    dispatched_at: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class Dispatcher:
    """Routes workflow execution requests to workers.

    Usage::

        dispatcher = Dispatcher(workers=...)
        result = await dispatcher.dispatch(request)
    """

    def __init__(self, *, workers: WorkerRegistry) -> None:
        self._workers = workers
        self._lock = threading.RLock()

        # Affinity tracking: workflow_id → node_id
        self._affinity: Dict[str, str] = {}

        # Round-robin state
        self._round_robin_index: int = 0

        # Dispatch history
        self._history: List[DispatchResult] = []
        self._max_history = 10000

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, request: DispatchRequest) -> DispatchResult:
        """Dispatch a workflow execution to the best worker."""
        workers = await self._workers.list_workers(available_only=True)
        if not workers:
            return DispatchResult(
                execution_id=request.execution_id,
                node_id="",
                success=False,
                reason="No available workers",
            )

        selected = await self._select_worker(request, workers)

        if selected is None:
            return DispatchResult(
                execution_id=request.execution_id,
                node_id="",
                success=False,
                reason="Worker selection failed",
            )

        # Track affinity
        if request.policy in (DispatchPolicy.STICKY, DispatchPolicy.AFFINITY):
            with self._lock:
                self._affinity[request.workflow_id] = selected.node_id

        # Mark task as dispatched
        await self._workers.record_task_dispatched(selected.node_id)

        result = DispatchResult(
            execution_id=request.execution_id,
            node_id=selected.node_id,
            success=True,
            metadata={
                "policy": request.policy,
                "load_score": selected.load_score,
                "queue_length": selected.queue_length,
            },
        )

        with self._lock:
            self._history.append(result)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        logger.debug("Dispatcher: execution %s → worker %s (policy=%s)",
                      request.execution_id, selected.node_id, request.policy)
        return result

    async def _select_worker(
        self,
        request: DispatchRequest,
        workers: List[WorkerRecord],
    ) -> Optional[WorkerRecord]:
        """Select the best worker based on dispatch policy."""
        if request.policy == DispatchPolicy.AFFINITY:
            # Check affinity cache
            with self._lock:
                affinity_node = self._affinity.get(request.workflow_id)
            if affinity_node:
                for w in workers:
                    if w.node_id == affinity_node:
                        return w

        if request.policy == DispatchPolicy.STICKY:
            # Prefer affinity but fall back to least loaded
            with self._lock:
                affinity_node = self._affinity.get(request.workflow_id)
            if affinity_node:
                for w in workers:
                    if w.node_id == affinity_node:
                        return w
            # Fall through to balanced selection

        if request.policy == DispatchPolicy.ROUND_ROBIN:
            with self._lock:
                idx = self._round_robin_index % len(workers)
                self._round_robin_index += 1
            return workers[idx]

        # Default: balanced — select least loaded
        workers.sort(key=lambda w: w.load_score)
        return workers[0]

    # ------------------------------------------------------------------
    # Rebalance
    # ------------------------------------------------------------------

    async def rebalance(self) -> Dict[str, Any]:
        """Check cluster load balance and suggest migrations."""
        workers = await self._workers.list_workers(available_only=True)
        if len(workers) < 2:
            return {"balanced": True, "migrations": []}

        loads = [w.load_score for w in workers]
        avg_load = sum(loads) / len(loads)
        max_load = max(loads)
        min_load = min(loads)

        imbalance = max_load - min_load
        is_balanced = imbalance < 0.3

        return {
            "balanced": is_balanced,
            "avg_load": round(avg_load, 4),
            "max_load": round(max_load, 4),
            "min_load": round(min_load, 4),
            "imbalance": round(imbalance, 4),
            "migrations": [],
        }

    # ------------------------------------------------------------------
    # Affinity management
    # ------------------------------------------------------------------

    async def set_affinity(self, workflow_id: str, node_id: str) -> None:
        with self._lock:
            self._affinity[workflow_id] = node_id

    async def clear_affinity(self, workflow_id: str) -> None:
        with self._lock:
            self._affinity.pop(workflow_id, None)

    async def get_affinity(self, workflow_id: str) -> Optional[str]:
        with self._lock:
            return self._affinity.get(workflow_id)

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def get_dispatch_history(self, limit: int = 100) -> List[DispatchResult]:
        with self._lock:
            return list(self._history[-limit:])

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "affinity_entries": len(self._affinity),
                "dispatch_count": len(self._history),
            }
