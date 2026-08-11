"""Lifecycle Metrics — Prometheus-compatible metrics for order lifecycle.

Exposes lifecycle engine metrics for monitoring and alerting.

Metrics:
    icyquant_order_lifecycle_events_total    — Total lifecycle events processed
    icyquant_order_transition_total          — Total state transitions
    icyquant_partial_fill_total              — Total partial fills
    icyquant_order_reject_total              — Total order rejections
    icyquant_order_replay_total              — Total event replays
    icyquant_duplicate_events_total          — Total duplicate events detected
    icyquant_transition_latency              — Transition latency histogram
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """Point-in-time metrics snapshot."""
    lifecycle_events_total: int = 0
    transition_total: int = 0
    partial_fill_total: int = 0
    fill_total: int = 0
    cancel_total: int = 0
    reject_total: int = 0
    expire_total: int = 0
    replace_total: int = 0
    suspend_total: int = 0
    replay_total: int = 0
    duplicate_events_total: int = 0
    transition_latency_samples: list[float] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def transition_latency_avg_ms(self) -> float:
        """Average transition latency in milliseconds."""
        if not self.transition_latency_samples:
            return 0.0
        return sum(self.transition_latency_samples) / len(self.transition_latency_samples)

    @property
    def transition_latency_p50_ms(self) -> float:
        """P50 transition latency."""
        return self._percentile(50)

    @property
    def transition_latency_p99_ms(self) -> float:
        """P99 transition latency."""
        return self._percentile(99)

    def _percentile(self, pct: float) -> float:
        """Calculate percentile from latency samples."""
        if not self.transition_latency_samples:
            return 0.0
        sorted_samples = sorted(self.transition_latency_samples)
        idx = int(len(sorted_samples) * pct / 100)
        idx = min(idx, len(sorted_samples) - 1)
        return sorted_samples[idx]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to Prometheus-compatible format."""
        return {
            "icyquant_order_lifecycle_events_total": self.lifecycle_events_total,
            "icyquant_order_transition_total": self.transition_total,
            "icyquant_partial_fill_total": self.partial_fill_total,
            "icyquant_order_fill_total": self.fill_total,
            "icyquant_order_cancel_total": self.cancel_total,
            "icyquant_order_reject_total": self.reject_total,
            "icyquant_order_expire_total": self.expire_total,
            "icyquant_order_replace_total": self.replace_total,
            "icyquant_order_suspend_total": self.suspend_total,
            "icyquant_order_replay_total": self.replay_total,
            "icyquant_duplicate_events_total": self.duplicate_events_total,
            "icyquant_transition_latency_avg_ms": self.transition_latency_avg_ms,
            "icyquant_transition_latency_p50_ms": self.transition_latency_p50_ms,
            "icyquant_transition_latency_p99_ms": self.transition_latency_p99_ms,
        }


class LifecycleMetrics:
    """Collects and exposes lifecycle engine metrics.

    Thread-safe metrics collection for order lifecycle operations.
    Supports Prometheus-compatible output format.

    Usage::

        metrics = LifecycleMetrics()
        metrics.record_transition()
        metrics.record_partial_fill()
        metrics.record_transition_latency(15.5)  # ms
        snapshot = metrics.snapshot()
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._latency_samples: list[float] = []
        self._max_latency_samples: int = 10000

    # ---- Counters ----

    def record_lifecycle_event(self) -> None:
        """Record a lifecycle event processed."""
        with self._lock:
            self._counters["lifecycle_events"] += 1

    def record_transition(self) -> None:
        """Record a state transition."""
        with self._lock:
            self._counters["transitions"] += 1

    def record_partial_fill(self) -> None:
        """Record a partial fill event."""
        with self._lock:
            self._counters["partial_fills"] += 1

    def record_fill(self) -> None:
        """Record a complete fill event."""
        with self._lock:
            self._counters["fills"] += 1

    def record_cancel(self) -> None:
        """Record a cancellation."""
        with self._lock:
            self._counters["cancels"] += 1

    def record_reject(self) -> None:
        """Record a rejection."""
        with self._lock:
            self._counters["rejects"] += 1

    def record_expire(self) -> None:
        """Record an expiration."""
        with self._lock:
            self._counters["expires"] += 1

    def record_replace(self) -> None:
        """Record an order modification."""
        with self._lock:
            self._counters["replaces"] += 1

    def record_suspend(self) -> None:
        """Record an order suspension."""
        with self._lock:
            self._counters["suspends"] += 1

    def record_replay(self) -> None:
        """Record an event replay."""
        with self._lock:
            self._counters["replays"] += 1

    def record_duplicate(self) -> None:
        """Record a duplicate event detected."""
        with self._lock:
            self._counters["duplicates"] += 1

    # ---- Latency ----

    def record_transition_latency(self, latency_ms: float) -> None:
        """Record a transition latency sample.

        Args:
            latency_ms: Transition duration in milliseconds
        """
        with self._lock:
            self._latency_samples.append(latency_ms)
            if len(self._latency_samples) > self._max_latency_samples:
                self._latency_samples = self._latency_samples[-self._max_latency_samples:]

    # ---- Query ----

    def snapshot(self) -> MetricSnapshot:
        """Get a point-in-time metrics snapshot.

        Returns:
            MetricSnapshot with current values
        """
        with self._lock:
            return MetricSnapshot(
                lifecycle_events_total=self._counters["lifecycle_events"],
                transition_total=self._counters["transitions"],
                partial_fill_total=self._counters["partial_fills"],
                fill_total=self._counters["fills"],
                cancel_total=self._counters["cancels"],
                reject_total=self._counters["rejects"],
                expire_total=self._counters["expires"],
                replace_total=self._counters["replaces"],
                suspend_total=self._counters["suspends"],
                replay_total=self._counters["replays"],
                duplicate_events_total=self._counters["duplicates"],
                transition_latency_samples=list(self._latency_samples),
            )

    def get_counter(self, name: str) -> int:
        """Get a specific counter value.

        Args:
            name: Counter name

        Returns:
            Current counter value
        """
        with self._lock:
            return self._counters.get(name, 0)

    def reset(self) -> None:
        """Reset all metrics counters."""
        with self._lock:
            self._counters.clear()
            self._latency_samples.clear()
            logger.info("Lifecycle metrics reset")

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics to dictionary."""
        return self.snapshot().to_dict()
