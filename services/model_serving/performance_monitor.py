"""
ICYQuant Performance Monitor — Real-time inference performance monitoring.

Tracks:
  - Request latency (avg, p50, p95, p99)
  - Throughput (requests/sec)
  - Error rates
  - Queue depth
  - Resource utilization
  - SLA compliance
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class PerformanceWindow:
    """Sliding window of performance metrics."""
    latencies: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    errors: Deque[bool] = field(default_factory=lambda: deque(maxlen=1000))
    window_start: float = field(default_factory=time.time)

    def record(self, latency_ms: float, is_error: bool) -> None:
        self.latencies.append(latency_ms)
        self.errors.append(is_error)

    @property
    def count(self) -> int:
        return len(self.latencies)

    @property
    def error_rate(self) -> float:
        if not self.errors:
            return 0.0
        return sum(self.errors) / len(self.errors)

    def get_percentile(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        arr = sorted(self.latencies)
        idx = int((p / 100.0) * len(arr))
        return arr[min(idx, len(arr) - 1)]

    def get_stats(self) -> Dict[str, Any]:
        n = len(self.latencies)
        if n == 0:
            return {}
        arr = sorted(self.latencies)
        return {
            "count": n,
            "avg_ms": round(sum(arr) / n, 2),
            "p50_ms": round(arr[n // 2], 2),
            "p95_ms": round(arr[int(n * 0.95)], 2),
            "p99_ms": round(arr[int(n * 0.99)], 2),
            "min_ms": round(arr[0], 2),
            "max_ms": round(arr[-1], 2),
            "error_rate": round(self.error_rate, 6),
        }


# ---------------------------------------------------------------------------
# Performance Monitor
# ---------------------------------------------------------------------------

class PerformanceMonitor:
    """Real-time inference performance monitor.

    Usage::

        monitor = PerformanceMonitor()
        await monitor.initialize()

        # After each inference
        monitor.record("nvda_model", latency_ms=45.2, is_error=False)

        # Check SLA
        compliance = monitor.get_sla_compliance("nvda_model")
    """

    def __init__(
        self,
        window_size: int = 1000,
        sla_target_ms: float = 100.0,
        sla_percentile: float = 99.0,
    ):
        self.window_size = window_size
        self.sla_target_ms = sla_target_ms
        self.sla_percentile = sla_percentile
        self._initialized = False

        # Per-model windows
        self._windows: Dict[str, PerformanceWindow] = {}

        # Alert callbacks
        self._alert_callbacks: List[Callable[[str, str, AlertLevel, Dict[str, Any]], None]] = []

        # Aggregate stats
        self._total_requests: int = 0
        self._total_errors: int = 0
        self._start_time: float = 0.0

    async def initialize(self) -> None:
        self._initialized = True
        self._start_time = time.time()
        logger.info("PerformanceMonitor initialized — SLA p%d < %.0fms",
                    self.sla_percentile, self.sla_target_ms)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        model_id: str,
        latency_ms: float,
        is_error: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an inference result.

        Args:
            model_id: Model identifier.
            latency_ms: Inference latency in milliseconds.
            is_error: Whether this was an error.
            metadata: Additional metadata.
        """
        if model_id not in self._windows:
            self._windows[model_id] = PerformanceWindow()

        self._windows[model_id].record(latency_ms, is_error)
        self._total_requests += 1
        if is_error:
            self._total_errors += 1

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_model_stats(self, model_id: str) -> Dict[str, Any]:
        """Get performance stats for a specific model."""
        window = self._windows.get(model_id)
        if window is None:
            return {}
        return {
            "model_id": model_id,
            **window.get_stats(),
        }

    def get_all_stats(self) -> Dict[str, Any]:
        """Get performance stats for all models."""
        stats = {
            model_id: self.get_model_stats(model_id)
            for model_id in self._windows
        }
        elapsed = max(time.time() - self._start_time, 0.001)
        return {
            "models": stats,
            "aggregate": {
                "total_requests": self._total_requests,
                "total_errors": self._total_errors,
                "overall_error_rate": round(
                    self._total_errors / max(self._total_requests, 1), 6
                ),
                "throughput": round(self._total_requests / elapsed, 2),
                "uptime_seconds": round(elapsed, 1),
            },
        }

    def get_sla_compliance(self, model_id: str) -> Dict[str, Any]:
        """Check SLA compliance for a model.

        SLA: p_percentile latency < target_ms
        """
        window = self._windows.get(model_id)
        if window is None or window.count == 0:
            return {"model_id": model_id, "compliant": True, "reason": "no_data"}

        p_value = window.get_percentile(self.sla_percentile)
        compliant = p_value <= self.sla_target_ms

        return {
            "model_id": model_id,
            "compliant": compliant,
            "sla_target_ms": self.sla_target_ms,
            "sla_percentile": self.sla_percentile,
            f"p{self.sla_percentile:.0f}_actual_ms": p_value,
            "samples": window.count,
        }

    def get_latency_distribution(self, model_id: str) -> Dict[str, int]:
        """Get latency bucket distribution."""
        window = self._windows.get(model_id)
        if window is None or not window.latencies:
            return {}

        buckets = {
            "<10ms": 0, "10-25ms": 0, "25-50ms": 0,
            "50-100ms": 0, "100-250ms": 0, "250-500ms": 0,
            "500ms-1s": 0, "1s-5s": 0, ">5s": 0,
        }
        for lat in window.latencies:
            if lat < 10:
                buckets["<10ms"] += 1
            elif lat < 25:
                buckets["10-25ms"] += 1
            elif lat < 50:
                buckets["25-50ms"] += 1
            elif lat < 100:
                buckets["50-100ms"] += 1
            elif lat < 250:
                buckets["100-250ms"] += 1
            elif lat < 500:
                buckets["250-500ms"] += 1
            elif lat < 1000:
                buckets["500ms-1s"] += 1
            elif lat < 5000:
                buckets["1s-5s"] += 1
            else:
                buckets[">5s"] += 1
        return buckets

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def check_thresholds(self) -> List[Dict[str, Any]]:
        """Check all models against alert thresholds.

        Returns:
            List of alerts triggered.
        """
        alerts = []
        for model_id, window in self._windows.items():
            if window.count < 10:
                continue

            # Error rate threshold
            if window.error_rate > 0.10:
                alerts.append({
                    "model_id": model_id,
                    "type": "high_error_rate",
                    "level": AlertLevel.CRITICAL,
                    "value": window.error_rate,
                    "threshold": 0.10,
                })

            # Latency spike
            p99 = window.get_percentile(99)
            if p99 > self.sla_target_ms * 3:
                alerts.append({
                    "model_id": model_id,
                    "type": "high_latency",
                    "level": AlertLevel.WARNING,
                    "value": p99,
                    "threshold": self.sla_target_ms * 3,
                })

        for alert in alerts:
            for cb in self._alert_callbacks:
                try:
                    cb(alert["model_id"], alert["type"],
                       alert["level"], alert)
                except Exception:
                    logger.exception("Alert callback error")

        return alerts

    def on_alert(
        self,
        callback: Callable[[str, str, AlertLevel, Dict[str, Any]], None],
    ) -> None:
        """Register alert callback."""
        self._alert_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        sla_checks = {
            mid: self.get_sla_compliance(mid)
            for mid in self._windows
        }
        non_compliant = sum(
            1 for s in sla_checks.values() if not s.get("compliant", True)
        )
        return {
            "status": "degraded" if non_compliant > 0 else "healthy",
            "sla_non_compliant": non_compliant,
            "stats": self.get_all_stats(),
        }

    def __repr__(self) -> str:
        return f"PerformanceMonitor(requests={self._total_requests})"
