"""Outlier detection for ICYQuant Service Mesh.

Provides ``OutlierDetector`` for identifying and ejecting unhealthy
instances based on latency, error rate, timeout, and consecutive
failure metrics, with automatic recovery and rejoining.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OutlierDetector:
    """Detects and manages outlier instances."""

    def __init__(
        self,
        consecutive_errors: int = 5,
        interval_s: float = 10.0,
        base_ejection_time_s: float = 30.0,
        max_ejection_percent: int = 50,
        latency_threshold_ms: float = 5000.0,
        error_rate_threshold: float = 0.5,
    ) -> None:
        self._consecutive_errors = consecutive_errors
        self._interval_s = interval_s
        self._base_ejection_time_s = base_ejection_time_s
        self._max_ejection_percent = max_ejection_percent
        self._latency_threshold_ms = latency_threshold_ms
        self._error_rate_threshold = error_rate_threshold
        self._lock = threading.RLock()
        self._instance_stats: Dict[str, Dict[str, Any]] = {}
        self._ejected: Dict[str, float] = {}
        self._detection_count = 0
        self._ejection_count = 0

    def record_request(
        self,
        instance: str,
        success: bool,
        latency_ms: float = 0.0,
    ) -> None:
        with self._lock:
            if instance not in self._instance_stats:
                self._instance_stats[instance] = {
                    "successes": 0,
                    "failures": 0,
                    "consecutive_failures": 0,
                    "last_latency_ms": 0.0,
                    "last_update": time.monotonic(),
                    "latencies": [],
                }
            stats = self._instance_stats[instance]
            if success:
                stats["successes"] += 1
                stats["consecutive_failures"] = 0
            else:
                stats["failures"] += 1
                stats["consecutive_failures"] += 1
            stats["last_latency_ms"] = latency_ms
            stats["last_update"] = time.monotonic()
            stats["latencies"].append(latency_ms)
            if len(stats["latencies"]) > 100:
                stats["latencies"] = stats["latencies"][-100:]

    def check_outlier(
        self, instance: str
    ) -> Dict[str, Any]:
        """Check if an instance should be ejected."""
        with self._lock:
            self._detection_count += 1
            stats = self._instance_stats.get(instance)
            if not stats:
                return {
                    "instance": instance,
                    "ejected": False,
                    "reason": "no_stats",
                }

            # Check consecutive failures
            if (
                stats["consecutive_failures"]
                >= self._consecutive_errors
            ):
                return self._eject(
                    instance,
                    "consecutive_failures",
                )

            # Check latency threshold
            if (
                stats["last_latency_ms"]
                > self._latency_threshold_ms
            ):
                return self._eject(
                    instance,
                    "latency_exceeded",
                )

            # Check error rate
            total = stats["successes"] + stats["failures"]
            if total >= 10:
                error_rate = stats["failures"] / total
                if error_rate >= self._error_rate_threshold:
                    return self._eject(
                        instance,
                        "high_error_rate",
                    )

            return {
                "instance": instance,
                "ejected": False,
                "reason": "healthy",
            }

    def _eject(
        self, instance: str, reason: str
    ) -> Dict[str, Any]:
        self._ejection_count += 1
        ejection_time = self._base_ejection_time_s
        self._ejected[instance] = (
            time.monotonic() + ejection_time
        )
        return {
            "instance": instance,
            "ejected": True,
            "reason": reason,
            "ejection_time_s": ejection_time,
        }

    def is_ejected(self, instance: str) -> bool:
        with self._lock:
            if instance not in self._ejected:
                return False
            if time.monotonic() >= self._ejected[instance]:
                del self._ejected[instance]
                if instance in self._instance_stats:
                    self._instance_stats[instance][
                        "consecutive_failures"
                    ] = 0
                return False
            return True

    def get_ejected(self) -> List[Dict[str, Any]]:
        with self._lock:
            now = time.monotonic()
            result = []
            for instance, until in self._ejected.items():
                remaining = max(0.0, until - now)
                result.append({
                    "instance": instance,
                    "remaining_s": remaining,
                })
            return result

    def rejoin(self, instance: str) -> bool:
        with self._lock:
            if instance in self._ejected:
                del self._ejected[instance]
                if instance in self._instance_stats:
                    self._instance_stats[instance][
                        "consecutive_failures"
                    ] = 0
                return True
            return False

    def get_instance_stats(
        self, instance: str
    ) -> Dict[str, Any]:
        with self._lock:
            stats = self._instance_stats.get(instance, {})
            ejected = self.is_ejected(instance)
            return {
                "instance": instance,
                "ejected": ejected,
                "consecutive_failures": stats.get(
                    "consecutive_failures", 0
                ),
                "last_latency_ms": stats.get(
                    "last_latency_ms", 0.0
                ),
                "total_requests": stats.get(
                    "successes", 0
                )
                + stats.get("failures", 0),
            }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "instance_count": len(self._instance_stats),
                "ejected_count": len(self._ejected),
                "detection_count": self._detection_count,
                "ejection_count": self._ejection_count,
                "config": {
                    "consecutive_errors": self._consecutive_errors,
                    "latency_threshold_ms": (
                        self._latency_threshold_ms
                    ),
                    "error_rate_threshold": (
                        self._error_rate_threshold
                    ),
                },
            }
