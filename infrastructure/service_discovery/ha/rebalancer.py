"""Cluster rebalancer for ICYQuant service discovery HA.

Provides ``ClusterRebalancer`` for analyzing instance
distribution and computing weight adjustments based on
CPU, memory, connections, latency, and weight metrics.

Based on: CPU, Memory, Connections, Latency, Weight
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance

logger = logging.getLogger(__name__)


class ClusterRebalancer:
    """Analyzes and rebalances cluster instance distribution.

    Collects metrics from instances and computes optimal
    weight adjustments to balance load across the cluster.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._analysis_count = 0
        self._rebalance_count = 0
        self._last_analysis: Optional[Dict[str, Any]] = None
        self._last_rebalance: Optional[Dict[str, Any]] = None

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    # ── Public API ──

    async def analyze(
        self, instances: List[ServiceInstance]
    ) -> Dict[str, Any]:
        """Analyze the current distribution of instances.

        Args:
            instances: List of ``ServiceInstance`` objects.

        Returns:
            A dictionary with distribution analysis including
            per-instance metrics and overall balance score.
        """
        with self._lock:
            self._analysis_count += 1

        if not instances:
            result: Dict[str, Any] = {
                "analyzed": True,
                "instance_count": 0,
                "balance_score": 1.0,
                "instances": [],
                "timestamp": self._now_iso(),
            }
            self._last_analysis = result
            return result

        instance_metrics: List[Dict[str, Any]] = []
        total_weight = 0
        total_cpu = 0.0
        total_mem = 0.0
        total_connections = 0

        for inst in instances:
            metadata = inst.metadata if isinstance(inst.metadata, dict) else {}
            weight = inst.weight
            cpu = float(metadata.get("cpu_usage", 0.0))
            mem = float(metadata.get("memory_usage", 0.0))
            conn = int(metadata.get("connections", 0))
            latency = float(metadata.get("latency_ms", 0.0))

            total_weight += weight
            total_cpu += cpu
            total_mem += mem
            total_connections += conn

            instance_metrics.append(
                {
                    "instance_id": inst.instance_id,
                    "host": inst.host,
                    "weight": weight,
                    "cpu_usage": cpu,
                    "memory_usage": mem,
                    "connections": conn,
                    "latency_ms": latency,
                    "healthy": inst.is_healthy(),
                }
            )

        count = len(instances)
        avg_cpu = total_cpu / count if count > 0 else 0.0
        avg_mem = total_mem / count if count > 0 else 0.0

        variance_cpu = 0.0
        variance_mem = 0.0
        for m in instance_metrics:
            variance_cpu += (m["cpu_usage"] - avg_cpu) ** 2
            variance_mem += (m["memory_usage"] - avg_mem) ** 2
        variance_cpu = variance_cpu / count if count > 0 else 0.0
        variance_mem = variance_mem / count if count > 0 else 0.0

        cpu_balance = max(0.0, 1.0 - (variance_cpu / max(avg_cpu**2, 1.0)))
        mem_balance = max(0.0, 1.0 - (variance_mem / max(avg_mem**2, 1.0)))
        overall_balance = (cpu_balance + mem_balance) / 2.0

        result = {
            "analyzed": True,
            "instance_count": count,
            "total_weight": total_weight,
            "avg_cpu_usage": avg_cpu,
            "avg_memory_usage": avg_mem,
            "total_connections": total_connections,
            "cpu_balance_score": cpu_balance,
            "memory_balance_score": mem_balance,
            "balance_score": overall_balance,
            "instances": instance_metrics,
            "timestamp": self._now_iso(),
        }

        with self._lock:
            self._last_analysis = result

        logger.debug(
            "Cluster analysis: balance=%.3f, instances=%d.",
            overall_balance,
            count,
        )
        return result

    async def rebalance(
        self,
        instances: List[ServiceInstance],
        metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Rebalance the cluster by computing weight adjustments.

        Args:
            instances: List of ``ServiceInstance`` objects.
            metrics: Optional pre-computed metrics. If not
                provided, analysis is performed first.

        Returns:
            A dictionary with weight adjustments per instance.
        """
        with self._lock:
            self._rebalance_count += 1

        if metrics is None:
            metrics = await self.analyze(instances)

        weights = self.compute_weights(instances)

        adjustments: List[Dict[str, Any]] = []
        for inst in instances:
            metadata = inst.metadata if isinstance(inst.metadata, dict) else {}
            current_weight = inst.weight
            new_weight = weights.get(inst.instance_id, current_weight)
            if new_weight != current_weight:
                adjustments.append(
                    {
                        "instance_id": inst.instance_id,
                        "host": inst.host,
                        "old_weight": current_weight,
                        "new_weight": new_weight,
                        "adjustment": new_weight - current_weight,
                    }
                )

        result: Dict[str, Any] = {
            "rebalanced": True,
            "instance_count": len(instances),
            "adjustments_count": len(adjustments),
            "adjustments": adjustments,
            "balance_before": metrics.get("balance_score", 0.0),
            "timestamp": self._now_iso(),
        }

        with self._lock:
            self._last_rebalance = result

        if adjustments:
            logger.info(
                "Rebalanced %d instances with %d weight adjustments.",
                len(instances),
                len(adjustments),
            )
        return result

    def compute_weights(
        self, instances: List[ServiceInstance]
    ) -> Dict[str, int]:
        """Compute optimal weights for a list of instances.

        Based on: CPU, Memory, Connections, Latency, Weight.

        Args:
            instances: List of ``ServiceInstance`` objects.

        Returns:
            A dictionary mapping instance_id to computed weight.
        """
        if not instances:
            return {}

        weights: Dict[str, int] = {}
        scores: Dict[str, float] = {}

        cpu_values: List[float] = []
        mem_values: List[float] = []
        latency_values: List[float] = []
        conn_values: List[int] = []

        for inst in instances:
            metadata = inst.metadata if isinstance(inst.metadata, dict) else {}
            cpu_values.append(float(metadata.get("cpu_usage", 0.0)))
            mem_values.append(float(metadata.get("memory_usage", 0.0)))
            latency_values.append(float(metadata.get("latency_ms", 0.0)))
            conn_values.append(int(metadata.get("connections", 0)))

        def _normalize(values: List[float]) -> List[float]:
            if not values:
                return []
            min_v = min(values)
            max_v = max(values)
            if max_v == min_v:
                return [0.5 for _ in values]
            return [(v - min_v) / (max_v - min_v) for v in values]

        norm_cpu = _normalize(cpu_values)
        norm_mem = _normalize(mem_values)
        norm_latency = _normalize(latency_values)
        norm_conn = _normalize([float(c) for c in conn_values])

        for i, inst in enumerate(instances):
            if not inst.is_healthy():
                weights[inst.instance_id] = 0
                continue

            cpu_score = 1.0 - norm_cpu[i]
            mem_score = 1.0 - norm_mem[i]
            latency_score = 1.0 - norm_latency[i]
            conn_score = 1.0 - norm_conn[i]

            score = (
                cpu_score * 0.3
                + mem_score * 0.2
                + latency_score * 0.25
                + conn_score * 0.15
                + 0.1
            )
            scores[inst.instance_id] = score

        min_score = min(scores.values()) if scores else 0.0
        max_score = max(scores.values()) if scores else 1.0
        score_range = max_score - min_score if max_score > min_score else 1.0

        for inst in instances:
            score = scores.get(inst.instance_id, 0.5)
            normalized = (score - min_score) / score_range
            base_weight = max(inst.weight, 1)
            new_weight = max(1, int(base_weight * (0.5 + normalized)))
            weights[inst.instance_id] = new_weight

        return weights

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the rebalancer."""
        with self._lock:
            return {
                "analysis_count": self._analysis_count,
                "rebalance_count": self._rebalance_count,
                "last_analysis": (
                    {
                        "balance_score": (
                            self._last_analysis.get("balance_score")
                            if self._last_analysis
                            else None
                        ),
                        "instance_count": (
                            self._last_analysis.get("instance_count")
                            if self._last_analysis
                            else None
                        ),
                    }
                    if self._last_analysis
                    else None
                ),
                "last_rebalance": (
                    {
                        "adjustments_count": (
                            self._last_rebalance.get("adjustments_count")
                            if self._last_rebalance
                            else None
                        ),
                    }
                    if self._last_rebalance
                    else None
                ),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ClusterRebalancer(analyses={self._analysis_count}, "
                f"rebalances={self._rebalance_count})"
            )