"""Trigger Metrics — Prometheus-compatible metrics for the trigger engine.

Exports metrics for:
* Trigger evaluation and firing rates
* Misfire detection and recovery
* Queue depth and dispatch latency
* Per-trigger-type statistics
"""

from __future__ import annotations

import threading
from typing import Any, Dict


class _Counter:
    """Simple thread-safe counter."""

    def __init__(self) -> None:
        self._value: int = 0
        self._lock = threading.Lock()

    def inc(self, delta: int = 1) -> None:
        with self._lock:
            self._value += delta

    def get(self) -> int:
        return self._value


class _Gauge:
    """Simple thread-safe gauge."""

    def __init__(self) -> None:
        self._value: float = 0.0
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def get(self) -> float:
        return self._value


class _Histogram:
    """Simple histogram with sum/count tracking."""

    def __init__(self) -> None:
        self._sum: float = 0.0
        self._count: int = 0
        self._min: float = float("inf")
        self._max: float = float("-inf")
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        with self._lock:
            self._sum += value
            self._count += 1
            if value < self._min:
                self._min = value
            if value > self._max:
                self._max = value

    def get_stats(self) -> Dict[str, float]:
        with self._lock:
            return {
                "count": self._count,
                "sum": self._sum,
                "avg": self._sum / max(self._count, 1),
                "min": self._min if self._count > 0 else 0.0,
                "max": self._max if self._count > 0 else 0.0,
            }


class TriggerMetrics:
    """Metrics collector for the trigger engine.

    Usage::

        metrics = TriggerMetrics()
        metrics.triggers_fired.inc()
        metrics.evaluation_latency.observe(0.015)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # Counters
        self.triggers_registered = _Counter()
        self.triggers_fired = _Counter()
        self.triggers_misfired = _Counter()
        self.triggers_dispatched = _Counter()
        self.triggers_failed = _Counter()
        self.events_received = _Counter()
        self.webhooks_received = _Counter()
        self.manual_fires = _Counter()

        # Per-type counters
        self._by_type: Dict[str, _Counter] = {}
        self._by_type_lock = threading.Lock()

        # Gauges
        self.active_triggers = _Gauge()
        self.queue_depth = _Gauge()

        # Histograms
        self.evaluation_latency = _Histogram()
        self.dispatch_latency = _Histogram()
        self.misfire_recovery_latency = _Histogram()
        self.queue_wait_time = _Histogram()

    def inc_by_type(self, trigger_type: str) -> None:
        with self._by_type_lock:
            if trigger_type not in self._by_type:
                self._by_type[trigger_type] = _Counter()
            self._by_type[trigger_type].inc()

    def get_by_type(self) -> Dict[str, int]:
        with self._by_type_lock:
            return {k: v.get() for k, v in self._by_type.items()}

    def snapshot(self) -> Dict[str, Any]:
        return {
            "counters": {
                "triggers_registered": self.triggers_registered.get(),
                "triggers_fired": self.triggers_fired.get(),
                "triggers_misfired": self.triggers_misfired.get(),
                "triggers_dispatched": self.triggers_dispatched.get(),
                "triggers_failed": self.triggers_failed.get(),
                "events_received": self.events_received.get(),
                "webhooks_received": self.webhooks_received.get(),
                "manual_fires": self.manual_fires.get(),
                "by_type": self.get_by_type(),
            },
            "gauges": {
                "active_triggers": self.active_triggers.get(),
                "queue_depth": self.queue_depth.get(),
            },
            "histograms": {
                "evaluation_latency": self.evaluation_latency.get_stats(),
                "dispatch_latency": self.dispatch_latency.get_stats(),
                "misfire_recovery_latency": self.misfire_recovery_latency.get_stats(),
                "queue_wait_time": self.queue_wait_time.get_stats(),
            },
        }

    def health_report(self) -> Dict[str, Any]:
        return self.snapshot()
