"""Timeout management for ICYQuant Service Mesh.

Provides ``TimeoutManager`` for connect/read/write/overall timeout
management with adaptive timeout adjustment based on latency history.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TimeoutManager:
    """Manages timeouts for requests."""

    def __init__(
        self,
        connect_timeout_ms: int = 5000,
        read_timeout_ms: int = 10000,
        write_timeout_ms: int = 10000,
        overall_timeout_ms: int = 30000,
        idle_timeout_ms: int = 60000,
        adaptive: bool = True,
    ) -> None:
        self._connect_timeout_ms = connect_timeout_ms
        self._read_timeout_ms = read_timeout_ms
        self._write_timeout_ms = write_timeout_ms
        self._overall_timeout_ms = overall_timeout_ms
        self._idle_timeout_ms = idle_timeout_ms
        self._adaptive = adaptive
        self._lock = threading.RLock()
        self._latency_history: Dict[str, List[float]] = {}
        self._timeout_count = 0
        self._adjustment_count = 0

    @property
    def connect_timeout_s(self) -> float:
        return self._connect_timeout_ms / 1000.0

    @property
    def read_timeout_s(self) -> float:
        return self._read_timeout_ms / 1000.0

    @property
    def write_timeout_s(self) -> float:
        return self._write_timeout_ms / 1000.0

    @property
    def overall_timeout_s(self) -> float:
        return self._overall_timeout_ms / 1000.0

    def get_timeouts(
        self, target: str = ""
    ) -> Dict[str, float]:
        """Get timeouts, optionally adjusted for target."""
        if self._adaptive and target:
            return self._get_adaptive_timeouts(target)
        return {
            "connect": self.connect_timeout_s,
            "read": self.read_timeout_s,
            "write": self.write_timeout_s,
            "overall": self.overall_timeout_s,
        }

    def _get_adaptive_timeouts(
        self, target: str
    ) -> Dict[str, float]:
        with self._lock:
            history = self._latency_history.get(target, [])

        if len(history) < 10:
            return {
                "connect": self.connect_timeout_s,
                "read": self.read_timeout_s,
                "write": self.write_timeout_s,
                "overall": self.overall_timeout_s,
            }

        sorted_latencies = sorted(history[-50:])
        p99_idx = int(len(sorted_latencies) * 0.99)
        p99 = sorted_latencies[min(p99_idx, len(sorted_latencies) - 1)]

        connect = max(self.connect_timeout_s, p99 * 2.0)
        read = max(self.read_timeout_s, p99 * 3.0)
        write = max(self.write_timeout_s, p99 * 3.0)
        overall = max(self.overall_timeout_s, p99 * 5.0)

        return {
            "connect": min(connect, 30.0),
            "read": min(read, 60.0),
            "write": min(write, 60.0),
            "overall": min(overall, 120.0),
        }

    def record_latency(
        self, target: str, latency_s: float
    ) -> None:
        with self._lock:
            if target not in self._latency_history:
                self._latency_history[target] = []
            self._latency_history[target].append(latency_s)
            history = self._latency_history[target]
            if len(history) > 1000:
                self._latency_history[target] = history[-1000:]

    def record_timeout(self, target: str) -> None:
        with self._lock:
            self._timeout_count += 1

    def set_timeouts(
        self,
        connect_ms: Optional[int] = None,
        read_ms: Optional[int] = None,
        write_ms: Optional[int] = None,
        overall_ms: Optional[int] = None,
    ) -> None:
        with self._lock:
            if connect_ms is not None:
                self._connect_timeout_ms = connect_ms
            if read_ms is not None:
                self._read_timeout_ms = read_ms
            if write_ms is not None:
                self._write_timeout_ms = write_ms
            if overall_ms is not None:
                self._overall_timeout_ms = overall_ms
            self._adjustment_count += 1

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "connect_timeout_ms": self._connect_timeout_ms,
                "read_timeout_ms": self._read_timeout_ms,
                "write_timeout_ms": self._write_timeout_ms,
                "overall_timeout_ms": self._overall_timeout_ms,
                "idle_timeout_ms": self._idle_timeout_ms,
                "adaptive": self._adaptive,
                "target_count": len(self._latency_history),
                "timeout_count": self._timeout_count,
                "adjustment_count": self._adjustment_count,
            }