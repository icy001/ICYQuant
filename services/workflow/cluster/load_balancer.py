"""Load Balancer — distributes workflow execution load across workers.

Algorithms:

* **Least Loaded** — route to the worker with the lowest current load
* **Weighted** — assign weights to workers and distribute proportionally
* **Round Robin** — cycle through workers in order
* **Resource Aware** — consider CPU, memory, and queue depth

Supports runtime dynamic adjustment of algorithm and worker weights.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .worker_registry import WorkerRegistry, WorkerRecord

logger = logging.getLogger(__name__)


class LoadBalancerAlgorithm(str, Enum):
    """Supported load balancing algorithms."""

    LEAST_LOADED = "least_loaded"
    WEIGHTED = "weighted"
    ROUND_ROBIN = "round_robin"
    RESOURCE_AWARE = "resource_aware"


@dataclass
class WorkerWeight:
    """Weight configuration for a worker node."""

    node_id: str
    weight: float = 1.0
    updated_at: datetime = field(default_factory=datetime.utcnow)


class LoadBalancer:
    """Distributes workflow execution load across worker nodes.

    Usage::

        balancer = LoadBalancer(workers=..., algorithm=LoadBalancerAlgorithm.LEAST_LOADED)
        node_id = await balancer.select_worker()
    """

    def __init__(
        self,
        *,
        workers: WorkerRegistry,
        algorithm: LoadBalancerAlgorithm = LoadBalancerAlgorithm.LEAST_LOADED,
    ) -> None:
        self._workers = workers
        self._algorithm = algorithm
        self._lock = threading.RLock()

        # Round-robin state
        self._rr_index: int = 0

        # Worker weights
        self._weights: Dict[str, WorkerWeight] = {}

        # Selection history
        self._history: List[str] = []
        self._max_history = 10000

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def algorithm(self) -> LoadBalancerAlgorithm:
        return self._algorithm

    async def set_algorithm(self, algorithm: LoadBalancerAlgorithm) -> None:
        with self._lock:
            self._algorithm = algorithm
        logger.info("LoadBalancer: algorithm changed to %s", algorithm.value)

    # ------------------------------------------------------------------
    # Worker selection
    # ------------------------------------------------------------------

    async def select_worker(self) -> Optional[str]:
        """Select the best worker based on the current algorithm."""
        workers = await self._workers.list_workers(available_only=True)
        if not workers:
            return None

        selected: Optional[str] = None

        if self._algorithm == LoadBalancerAlgorithm.LEAST_LOADED:
            selected = self._select_least_loaded(workers)
        elif self._algorithm == LoadBalancerAlgorithm.WEIGHTED:
            selected = self._select_weighted(workers)
        elif self._algorithm == LoadBalancerAlgorithm.ROUND_ROBIN:
            selected = self._select_round_robin(workers)
        elif self._algorithm == LoadBalancerAlgorithm.RESOURCE_AWARE:
            selected = self._select_resource_aware(workers)

        if selected:
            with self._lock:
                self._history.append(selected)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]

        return selected

    async def select_workers(self, count: int) -> List[str]:
        """Select the top N workers."""
        workers = await self._workers.list_workers(available_only=True)
        if not workers:
            return []

        if self._algorithm == LoadBalancerAlgorithm.LEAST_LOADED:
            workers.sort(key=lambda w: w.load_score)
        elif self._algorithm == LoadBalancerAlgorithm.RESOURCE_AWARE:
            workers.sort(key=lambda w: w.load_score)
        else:
            workers.sort(key=lambda w: w.load_score)

        return [w.node_id for w in workers[:count]]

    # ------------------------------------------------------------------
    # Selection strategies
    # ------------------------------------------------------------------

    def _select_least_loaded(self, workers: List[WorkerRecord]) -> str:
        return min(workers, key=lambda w: w.load_score).node_id

    def _select_weighted(self, workers: List[WorkerRecord]) -> str:
        # Weighted random selection based on configured weights
        import random
        with self._lock:
            total_weight = sum(
                self._weights.get(w.node_id, WorkerWeight(w.node_id)).weight
                for w in workers
            )
            if total_weight <= 0:
                return workers[0].node_id

            r = random.uniform(0, total_weight)
            cumulative = 0.0
            for w in workers:
                weight = self._weights.get(w.node_id, WorkerWeight(w.node_id)).weight
                cumulative += weight
                if r <= cumulative:
                    return w.node_id
            return workers[-1].node_id

    def _select_round_robin(self, workers: List[WorkerRecord]) -> str:
        with self._lock:
            idx = self._rr_index % len(workers)
            self._rr_index += 1
        return workers[idx].node_id

    def _select_resource_aware(self, workers: List[WorkerRecord]) -> str:
        # Composite score: lower is better
        def score(w: WorkerRecord) -> float:
            cpu = w.resources.cpu_usage_pct / 100.0
            mem = w.resources.memory_usage_pct / 100.0
            queue = min(1.0, w.queue_length / 100.0)
            return 0.4 * cpu + 0.3 * mem + 0.3 * queue

        return min(workers, key=score).node_id

    # ------------------------------------------------------------------
    # Weights management
    # ------------------------------------------------------------------

    async def set_weight(self, node_id: str, weight: float) -> None:
        """Set the weight for a worker (higher = more traffic)."""
        with self._lock:
            self._weights[node_id] = WorkerWeight(node_id=node_id, weight=max(0.0, weight))

    async def get_weight(self, node_id: str) -> float:
        with self._lock:
            w = self._weights.get(node_id)
            return w.weight if w else 1.0

    async def list_weights(self) -> Dict[str, float]:
        with self._lock:
            return {nid: w.weight for nid, w in self._weights.items()}

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def get_selection_distribution(self) -> Dict[str, int]:
        """Get how many times each worker was selected recently."""
        with self._lock:
            dist: Dict[str, int] = {}
            for node_id in self._history[-1000:]:
                dist[node_id] = dist.get(node_id, 0) + 1
            return dist

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "algorithm": self._algorithm.value,
                "weighted_workers": len(self._weights),
                "selection_count": len(self._history),
            }
