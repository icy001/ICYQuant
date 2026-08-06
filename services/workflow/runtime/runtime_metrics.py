"""Runtime Metrics — collects runtime-level metrics for workflow execution.

Tracks:
* Active instance count
* Total instances processed
* Event throughput
* Runtime health indicators
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RuntimeMetricsCollector:
    """Collects runtime-level metrics for workflow instances."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._started = False

        # Counters
        self._total_instances = 0
        self._total_completed = 0
        self._total_failed = 0
        self._total_cancelled = 0
        self._total_events_published = 0

        # Gauges
        self._active_instances = 0

        # Timing
        self._start_time: float = 0.0

    def start(self) -> None:
        self._started = True
        self._start_time = time.time()
        logger.info("RuntimeMetricsCollector: started")

    def shutdown(self) -> None:
        self._started = False
        logger.info("RuntimeMetricsCollector: shutdown")

    # ------------------------------------------------------------------
    # Instance metrics
    # ------------------------------------------------------------------

    def increment_total_instances(self) -> None:
        with self._lock:
            self._total_instances += 1

    def increment_active_instances(self) -> None:
        with self._lock:
            self._active_instances += 1

    def decrement_active_instances(self) -> None:
        with self._lock:
            self._active_instances = max(0, self._active_instances - 1)

    def increment_completed(self) -> None:
        with self._lock:
            self._total_completed += 1
            self.decrement_active_instances()

    def increment_failed(self) -> None:
        with self._lock:
            self._total_failed += 1
            self.decrement_active_instances()

    def increment_cancelled(self) -> None:
        with self._lock:
            self._total_cancelled += 1
            self.decrement_active_instances()

    def increment_events_published(self, count: int = 1) -> None:
        with self._lock:
            self._total_events_published += count

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            uptime = time.time() - self._start_time if self._start_time > 0 else 0
            return {
                "uptime_seconds": uptime,
                "total_instances": self._total_instances,
                "active_instances": self._active_instances,
                "total_completed": self._total_completed,
                "total_failed": self._total_failed,
                "total_cancelled": self._total_cancelled,
                "total_events_published": self._total_events_published,
            }

    def reset(self) -> None:
        with self._lock:
            self._total_instances = 0
            self._total_completed = 0
            self._total_failed = 0
            self._total_cancelled = 0
            self._total_events_published = 0
            self._active_instances = 0
            self._start_time = time.time()
