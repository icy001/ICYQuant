"""Node Scoring Engine — multi-dimensional node suitability scoring.

The :class:`NodeScoringEngine` computes a composite score for each candidate
node, considering CPU, memory, latency, current load, failure history, and
optional affinity bonuses.  The highest-scoring node wins placement.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .node_inventory import NodeRecord


@dataclass
class NodeScore:
    """Composite score for a candidate node."""

    node_id: str
    total_score: float = 0.0
    cpu_score: float = 0.0
    memory_score: float = 0.0
    latency_score: float = 0.0
    load_score: float = 0.0
    failure_score: float = 0.0
    affinity_bonus: float = 0.0
    breakdown: Dict[str, float] = field(default_factory=dict)


class NodeScoringEngine:
    """Multi-dimensional node scoring for placement decisions.

    Scoring dimensions (all 0–1 normalized, weighted):
    * CPU availability (higher is better)
    * Memory availability (higher is better)
    * Latency (lower is better)
    * Current load (lower is better)
    * Failure rate (lower is better)
    * Affinity bonus (extra points for preferred nodes)

    Usage::

        engine = NodeScoringEngine()
        scores = engine.score_nodes(candidates, cpu_cores=4, memory_mb=8192)
        best = max(scores, key=lambda s: s.total_score)
    """

    def __init__(
        self,
        cpu_weight: float = 0.30,
        memory_weight: float = 0.25,
        latency_weight: float = 0.15,
        load_weight: float = 0.15,
        failure_weight: float = 0.10,
        affinity_weight: float = 0.05,
    ) -> None:
        self._lock = threading.RLock()
        self._weights = {
            "cpu": cpu_weight, "memory": memory_weight,
            "latency": latency_weight, "load": load_weight,
            "failure": failure_weight, "affinity": affinity_weight,
        }

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_node(
        self, node: NodeRecord, cpu_request: float = 0.0,
        memory_request_mb: float = 0.0,
        preferred_nodes: Optional[List[str]] = None,
    ) -> NodeScore:
        """Score a single node."""
        # CPU: availability ratio
        cpu_avail = node.cpu_available / max(node.cpu_cores, 0.001)
        cpu_score = self._normalize(cpu_avail, 0.0, 1.0) * self._weights["cpu"]

        # Memory: availability ratio
        mem_avail = node.memory_available_mb / max(node.memory_mb, 0.001)
        mem_score = self._normalize(mem_avail, 0.0, 1.0) * self._weights["memory"]

        # Latency: inverse (lower is better)
        lat_norm = 1.0 / max(node.avg_latency_ms + 1.0, 1.0)
        lat_score = lat_norm * self._weights["latency"]

        # Load: 1 - utilization
        load = (node.cpu_used / max(node.cpu_cores, 0.001))
        load_score = (1.0 - self._normalize(load, 0.0, 1.0)) * self._weights["load"]

        # Failure: inverse of failure_count
        fail_score = (1.0 / max(node.failure_count + 1, 1)) * self._weights["failure"]

        # Affinity bonus
        affinity_bonus = 0.0
        if preferred_nodes and node.node_id in preferred_nodes:
            affinity_bonus = self._weights["affinity"]

        total = cpu_score + mem_score + lat_score + load_score + fail_score + affinity_bonus

        return NodeScore(
            node_id=node.node_id, total_score=total,
            cpu_score=cpu_score, memory_score=mem_score,
            latency_score=lat_score, load_score=load_score,
            failure_score=fail_score, affinity_bonus=affinity_bonus,
            breakdown={
                "cpu": cpu_score, "memory": mem_score,
                "latency": lat_score, "load": load_score,
                "failure": fail_score, "affinity": affinity_bonus,
            },
        )

    def score_nodes(
        self, candidates: List[NodeRecord],
        cpu_request: float = 0.0, memory_request_mb: float = 0.0,
        preferred_nodes: Optional[List[str]] = None,
    ) -> List[NodeScore]:
        """Score all candidate nodes, sorted descending."""
        scores = [
            self.score_node(n, cpu_request, memory_request_mb, preferred_nodes)
            for n in candidates
        ]
        return sorted(scores, key=lambda s: s.total_score, reverse=True)

    def best_node(
        self, candidates: List[NodeRecord],
        cpu_request: float = 0.0, memory_request_mb: float = 0.0,
        preferred_nodes: Optional[List[str]] = None,
    ) -> Optional[NodeScore]:
        """Return the single best node score, or None if no candidates."""
        scores = self.score_nodes(candidates, cpu_request, memory_request_mb, preferred_nodes)
        return scores[0] if scores else None

    # ------------------------------------------------------------------
    # Weight tuning
    # ------------------------------------------------------------------

    def set_weights(
        self, cpu: float = None, memory: float = None,
        latency: float = None, load: float = None,
        failure: float = None, affinity: float = None,
    ) -> None:
        with self._lock:
            if cpu is not None:
                self._weights["cpu"] = cpu
            if memory is not None:
                self._weights["memory"] = memory
            if latency is not None:
                self._weights["latency"] = latency
            if load is not None:
                self._weights["load"] = load
            if failure is not None:
                self._weights["failure"] = failure
            if affinity is not None:
                self._weights["affinity"] = affinity

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(value: float, min_v: float, max_v: float) -> float:
        if max_v == min_v:
            return 1.0
        return max(0.0, min(1.0, (value - min_v) / (max_v - min_v)))

    def health_report(self) -> Dict[str, Any]:
        return {"weights": dict(self._weights)}
