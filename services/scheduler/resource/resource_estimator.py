"""Resource Estimator — predicts resource needs for incoming jobs.

The :class:`ResourceEstimator` combines historical execution data with
declared requirements to produce an :class:`EstimateResult` that guides
placement decisions.  Accuracy improves over time as more history accumulates.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class EstimateResult:
    """Estimated resource requirements for a job."""

    job_id: str
    cpu_cores: float = 0.0
    memory_mb: float = 0.0
    disk_io_mbps: float = 0.0
    network_mbps: float = 0.0
    gpu_units: float = 0.0
    execution_time_ms: float = 0.0
    confidence: float = 1.0  # 0.0–1.0
    source: str = "declared"  # declared / historical / model

    def to_requirements_dict(self) -> Dict[str, float]:
        return {
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "disk_io_mbps": self.disk_io_mbps,
            "network_mbps": self.network_mbps,
            "gpu_units": self.gpu_units,
        }


class ResourceEstimator:
    """Estimates resource requirements for scheduling decisions.

    Uses a three-tier strategy:
    1. Declared requirements (explicit from job definition)
    2. Historical averages (from past executions of the same job type)
    3. Model-based prediction (placeholder for ML integration)

    Usage::

        estimator = ResourceEstimator()
        result = estimator.estimate(job_id="job-1", declared={"cpu_cores": 2})
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Historical data: job_type → [(cpu, mem, duration_ms), ...]
        self._history: Dict[str, List[Tuple[float, float, float]]] = defaultdict(list)
        self._max_history_per_type = 500

    # ------------------------------------------------------------------
    # Estimation
    # ------------------------------------------------------------------

    def estimate(
        self,
        job_id: str,
        job_type: str = "",
        declared: Optional[Dict[str, float]] = None,
    ) -> EstimateResult:
        """Estimate resource needs for a job.

        Priority: declared > historical > default
        """
        declared = declared or {}

        # If fully declared, trust it with high confidence
        if declared.get("cpu_cores") and declared.get("memory_mb"):
            return EstimateResult(
                job_id=job_id,
                cpu_cores=declared["cpu_cores"],
                memory_mb=declared["memory_mb"],
                disk_io_mbps=declared.get("disk_io_mbps", 0.0),
                network_mbps=declared.get("network_mbps", 0.0),
                gpu_units=declared.get("gpu_units", 0.0),
                execution_time_ms=declared.get("execution_time_ms", 0.0),
                confidence=1.0,
                source="declared",
            )

        # Historical estimation
        key = job_type or job_id
        hist = self._get_history_stats(key)
        if hist:
            return EstimateResult(
                job_id=job_id,
                cpu_cores=declared.get("cpu_cores", hist["cpu_avg"]),
                memory_mb=declared.get("memory_mb", hist["memory_avg"]),
                disk_io_mbps=declared.get("disk_io_mbps", 0.0),
                network_mbps=declared.get("network_mbps", 0.0),
                gpu_units=declared.get("gpu_units", 0.0),
                execution_time_ms=hist["duration_avg_ms"],
                confidence=hist["confidence"],
                source="historical",
            )

        # Default fallback
        return EstimateResult(
            job_id=job_id,
            cpu_cores=declared.get("cpu_cores", 1.0),
            memory_mb=declared.get("memory_mb", 512.0),
            confidence=0.3,
            source="default",
        )

    # ------------------------------------------------------------------
    # History recording
    # ------------------------------------------------------------------

    def record_execution(
        self, job_type: str, cpu_used: float,
        memory_used_mb: float, duration_ms: float,
    ) -> None:
        """Record actual resource usage after a job completes."""
        with self._lock:
            self._history[job_type].append((cpu_used, memory_used_mb, duration_ms))
            if len(self._history[job_type]) > self._max_history_per_type:
                self._history[job_type] = self._history[job_type][-self._max_history_per_type:]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_history_stats(self, job_type: str) -> Optional[Dict[str, float]]:
        with self._lock:
            data = self._history.get(job_type, [])
            if len(data) < 3:
                return None
            cpus = [d[0] for d in data]
            mems = [d[1] for d in data]
            durs = [d[2] for d in data]
            return {
                "cpu_avg": sum(cpus) / len(cpus),
                "cpu_p95": self._percentile(cpus, 95),
                "memory_avg": sum(mems) / len(mems),
                "memory_p95": self._percentile(mems, 95),
                "duration_avg_ms": sum(durs) / len(durs),
                "sample_count": len(data),
                "confidence": min(1.0, len(data) / 50.0),
            }

    @staticmethod
    def _percentile(values: list, pct: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * pct / 100.0)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "job_types_tracked": len(self._history),
                "total_samples": sum(len(v) for v in self._history.values()),
            }
