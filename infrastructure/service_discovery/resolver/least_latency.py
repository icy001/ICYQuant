"""Least-latency selection algorithm.

Provides a thread-safe ``LeastLatency`` class that tracks
EWMA (Exponentially Weighted Moving Average) latency per
instance and selects the one with the lowest observed latency.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance

logger = logging.getLogger(__name__)


class LeastLatency:
    """Selects the instance with the lowest EWMA latency.

    Uses an Exponentially Weighted Moving Average for latency
    tracking. Instances with zero recorded latency are preferred
    (assumed cold-start / healthy). Tracks p99, average, and
    timeout rates. Thread-safe.

    Args:
        window_size: Number of recent latency samples to retain
            for percentile calculations.

    Usage::

        ll = LeastLatency(window_size=10)
        instance = ll.select(instances)
        ll.record_latency(instance.instance_id, 25.5)
    """

    def __init__(self, window_size: int = 10) -> None:
        self._window_size = window_size
        self._lock = threading.RLock()
        self._latencies: Dict[str, List[float]] = {}
        self._ewma: Dict[str, float] = {}
        self._timeouts: Dict[str, int] = {}
        self._requests: Dict[str, int] = {}
        self._select_count = 0
        self._alpha = 2.0 / (window_size + 1)

    def record_latency(self, instance_id: str, latency: float) -> None:
        """Record a latency sample for an instance.

        Args:
            instance_id: The instance identifier.
            latency: Observed latency in milliseconds. Use 0 or
                negative values to record a timeout.
        """
        with self._lock:
            self._requests[instance_id] = (
                self._requests.get(instance_id, 0) + 1
            )
            if latency <= 0:
                self._timeouts[instance_id] = (
                    self._timeouts.get(instance_id, 0) + 1
                )
                return
            samples = self._latencies.setdefault(instance_id, [])
            samples.append(latency)
            if len(samples) > self._window_size:
                del samples[: len(samples) - self._window_size]
            prev_ewma = self._ewma.get(instance_id, latency)
            self._ewma[instance_id] = (self._alpha * latency) + (
                (1.0 - self._alpha) * prev_ewma
            )

    def select(
        self, instances: List[ServiceInstance]
    ) -> Optional[ServiceInstance]:
        """Select the instance with the lowest EWMA latency.

        Instances without recorded latency are preferred.

        Args:
            instances: Candidate instances.

        Returns:
            The selected instance or None if the list is empty.
        """
        if not instances:
            return None
        with self._lock:
            best_instance: Optional[ServiceInstance] = None
            best_latency: float = float("inf")
            for instance in instances:
                iid = instance.instance_id
                latency = self._ewma.get(iid)
                if latency is None:
                    self._select_count += 1
                    return instance
                if latency < best_latency:
                    best_latency = latency
                    best_instance = instance
            if best_instance is not None:
                self._select_count += 1
            return best_instance

    def get_stats(self) -> Dict[str, Any]:
        """Return least-latency statistics.

        Includes EWMA, p99, average latency, timeout rates, and
        request counts per instance.

        Returns:
            A dictionary with latency statistics.
        """
        with self._lock:
            p99_values: Dict[str, float] = {}
            avg_values: Dict[str, float] = {}
            timeout_rates: Dict[str, float] = {}
            for iid, samples in self._latencies.items():
                if samples:
                    sorted_samples = sorted(samples)
                    idx = max(0, int(len(sorted_samples) * 0.99) - 1)
                    p99_values[iid] = sorted_samples[idx]
                    avg_values[iid] = sum(samples) / len(samples)
                total = self._requests.get(iid, 0)
                timeouts = self._timeouts.get(iid, 0)
                timeout_rates[iid] = (timeouts / total) if total > 0 else 0.0
            return {
                "selector": "LeastLatency",
                "ewma": dict(self._ewma),
                "p99": p99_values,
                "avg": avg_values,
                "timeout_rates": timeout_rates,
                "requests": dict(self._requests),
                "timeouts": dict(self._timeouts),
                "select_count": self._select_count,
                "window_size": self._window_size,
            }

    def __repr__(self) -> str:
        tracked = len(self._ewma)
        return f"LeastLatency(tracked_instances={tracked}, selects={self._select_count})"