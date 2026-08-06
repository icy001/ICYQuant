"""Placement Strategy — intelligent workflow placement across cluster nodes.

Considers:

* **CPU** — available cores and current utilization
* **Memory** — available memory and usage
* **Latency** — historical task latency
* **Affinity** — preferred nodes for related workflows
* **Failure Domain** — spread across zones/regions for resilience

Automatically selects the best node for each workflow execution.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .worker_registry import WorkerRegistry, WorkerRecord
from .scheduler import ScheduleRequest

logger = logging.getLogger(__name__)


class PlacementPolicy(str, Enum):
    """Placement policies for node selection."""

    LEAST_LOADED = "least_loaded"
    MOST_AVAILABLE = "most_available"
    AFFINITY = "affinity"
    SPREAD = "spread"
    RESOURCE_AWARE = "resource_aware"


@dataclass
class PlacementDecision:
    """Result of a placement decision."""

    selected_node_id: Optional[str] = None
    score: float = 0.0
    reason: str = ""
    policy: PlacementPolicy = PlacementPolicy.RESOURCE_AWARE
    candidates_evaluated: int = 0
    decided_at: datetime = field(default_factory=datetime.utcnow)
    scores: Dict[str, float] = field(default_factory=dict)


class PlacementStrategy:
    """Intelligent workflow placement across cluster nodes.

    Usage::

        strategy = PlacementStrategy(workers=..., policy=PlacementPolicy.RESOURCE_AWARE)
        decision = await strategy.decide(request=..., candidates=[...], shard_id="shard-0000")
    """

    def __init__(
        self,
        *,
        workers: WorkerRegistry,
        policy: PlacementPolicy = PlacementPolicy.RESOURCE_AWARE,
        cpu_weight: float = 0.35,
        memory_weight: float = 0.25,
        queue_weight: float = 0.25,
        latency_weight: float = 0.15,
    ) -> None:
        self._workers = workers
        self._policy = policy
        self._cpu_weight = cpu_weight
        self._memory_weight = memory_weight
        self._queue_weight = queue_weight
        self._latency_weight = latency_weight
        self._lock = threading.RLock()

        # Affinity: workflow_id → preferred node_id
        self._affinity: Dict[str, str] = {}

        # Failure domain awareness: node_id → zone
        self._failure_domains: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    async def decide(
        self,
        *,
        request: ScheduleRequest,
        candidates: List[str],
        shard_id: str,
    ) -> PlacementDecision:
        """Decide which node should execute the workflow."""
        if not candidates:
            return PlacementDecision(
                reason="No candidates available",
                policy=self._policy,
            )

        worker_records = []
        for node_id in candidates:
            record = await self._workers.get_worker(node_id)
            if record and record.is_available:
                worker_records.append(record)

        if not worker_records:
            return PlacementDecision(
                reason="No available workers among candidates",
                policy=self._policy,
            )

        # Score each candidate
        scores: Dict[str, float] = {}
        for record in worker_records:
            scores[record.node_id] = self._score_worker(record, request)

        # Select best
        if self._policy == PlacementPolicy.LEAST_LOADED:
            best = min(worker_records, key=lambda w: w.load_score)
        elif self._policy == PlacementPolicy.MOST_AVAILABLE:
            best = max(worker_records, key=lambda w: w.available_capacity)
        elif self._policy == PlacementPolicy.AFFINITY:
            best = self._affinity_select(worker_records, request)
        elif self._policy == PlacementPolicy.SPREAD:
            best = self._spread_select(worker_records)
        else:
            # RESOURCE_AWARE — highest composite score
            best = max(worker_records, key=lambda w: scores.get(w.node_id, 0.0))

        return PlacementDecision(
            selected_node_id=best.node_id,
            score=scores.get(best.node_id, 0.0),
            reason=f"Selected by {self._policy.value}",
            policy=self._policy,
            candidates_evaluated=len(worker_records),
            scores=scores,
        )

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_worker(self, record: WorkerRecord, request: ScheduleRequest) -> float:
        """Compute a composite placement score for a worker (0.0 = worst, 1.0 = best)."""
        cpu_score = 1.0 - record.resources.cpu_usage_pct / 100.0
        mem_score = 1.0 - record.resources.memory_usage_pct / 100.0
        queue_score = max(0.0, 1.0 - record.queue_length / 50.0)
        latency_score = max(0.0, 1.0 - record.avg_latency_ms / 5000.0)

        total = (
            self._cpu_weight * cpu_score
            + self._memory_weight * mem_score
            + self._queue_weight * queue_score
            + self._latency_weight * latency_score
        )

        # Affinity bonus
        with self._lock:
            affinity_node = self._affinity.get(request.workflow_id)
        if affinity_node and record.node_id == affinity_node:
            total += 0.15

        # Tag matching bonus
        if request.affinity_tags:
            tag_match = sum(1 for t in request.affinity_tags if t in record.metadata.get("tags", []))
            if tag_match > 0:
                total += 0.1 * min(tag_match, 3)

        return min(1.0, max(0.0, total))

    def _affinity_select(
        self, workers: List[WorkerRecord], request: ScheduleRequest
    ) -> WorkerRecord:
        """Select based on affinity, falling back to least loaded."""
        with self._lock:
            affinity_node = self._affinity.get(request.workflow_id)
        if affinity_node:
            for w in workers:
                if w.node_id == affinity_node:
                    return w
        return min(workers, key=lambda w: w.load_score)

    def _spread_select(self, workers: List[WorkerRecord]) -> WorkerRecord:
        """Select to maximize spread across failure domains."""
        # Prefer workers in different zones than recently used ones
        with self._lock:
            recent_zones = set(self._failure_domains.values())

        # Prefer workers in less-used zones
        zone_counts: Dict[str, int] = {}
        for w in workers:
            zone = self._failure_domains.get(w.node_id, "unknown")
            zone_counts[zone] = zone_counts.get(zone, 0) + 1

        workers_sorted = sorted(
            workers,
            key=lambda w: (zone_counts.get(self._failure_domains.get(w.node_id, "unknown"), 0),
                           w.load_score)
        )
        return workers_sorted[0]

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    async def set_affinity(self, workflow_id: str, node_id: str) -> None:
        with self._lock:
            self._affinity[workflow_id] = node_id

    async def set_failure_domain(self, node_id: str, zone: str) -> None:
        with self._lock:
            self._failure_domains[node_id] = zone

    async def get_failure_domain(self, node_id: str) -> Optional[str]:
        with self._lock:
            return self._failure_domains.get(node_id)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "policy": self._policy.value,
                "affinity_count": len(self._affinity),
                "failure_domains": len(self._failure_domains),
                "weights": {
                    "cpu": self._cpu_weight,
                    "memory": self._memory_weight,
                    "queue": self._queue_weight,
                    "latency": self._latency_weight,
                },
            }
