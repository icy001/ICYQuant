"""
Canary real-time monitoring.

Tracks deployment progress, traffic metrics,
and business KPIs during canary releases.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MonitorSnapshot:
    """
    A point-in-time snapshot of canary metrics.

    Attributes:
        feature_key: Feature flag key.
        current_percentage: Current traffic percentage.
        request_count: Total requests observed.
        success_count: Successful requests.
        failure_count: Failed requests.
        success_rate: Success rate percentage.
        failure_rate: Failure rate percentage.
        latency_p50_ms: P50 latency.
        latency_p99_ms: P99 latency.
        kpi_values: Current business KPI values.
        timestamp: When the snapshot was taken.
    """

    feature_key: str = ""
    current_percentage: float = 0.0
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 100.0
    failure_rate: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p99_ms: float = 0.0
    kpi_values: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "feature_key": self.feature_key,
            "current_percentage": self.current_percentage,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "kpi_values": self.kpi_values,
            "timestamp": self.timestamp,
        }


class CanaryMonitor:
    """
    Real-time monitoring for canary deployments.

    Collects and aggregates metrics during
    canary releases for dashboard display
    and automated decision-making.

    Usage:
        monitor = CanaryMonitor()
        monitor.record("new-risk", success=True, latency_ms=45.0)
        snapshot = monitor.snapshot("new-risk", 25.0)
    """

    def __init__(self, max_history: int = 1000) -> None:
        """
        Initialize the monitor.

        Args:
            max_history: Maximum snapshot history.
        """
        self._metrics: Dict[str, Dict[str, Any]] = {}
        self._history: Dict[str, List[MonitorSnapshot]] = {}
        self._max_history = max_history

    def record(
        self,
        feature_key: str,
        success: bool = True,
        latency_ms: float = 0.0,
        kpi: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Record a canary observation.

        Args:
            feature_key: Feature flag key.
            success: Whether the request succeeded.
            latency_ms: Request latency.
            kpi: Business KPI values.
        """
        if feature_key not in self._metrics:
            self._metrics[feature_key] = {
                "requests": 0,
                "successes": 0,
                "failures": 0,
                "latencies": [],
                "kpi_latest": {},
            }

        m = self._metrics[feature_key]
        m["requests"] += 1
        if success:
            m["successes"] += 1
        else:
            m["failures"] += 1

        if latency_ms > 0:
            m["latencies"].append(latency_ms)
            # Keep only recent latencies
            if len(m["latencies"]) > 10000:
                m["latencies"] = m["latencies"][-10000:]

        if kpi:
            m["kpi_latest"].update(kpi)

    def snapshot(
        self,
        feature_key: str,
        current_percentage: float = 0.0,
    ) -> MonitorSnapshot:
        """
        Take a monitoring snapshot.

        Args:
            feature_key: Feature flag key.
            current_percentage: Current canary percentage.

        Returns:
            MonitorSnapshot with current metrics.
        """
        m = self._metrics.get(feature_key, {})
        requests = m.get("requests", 0)
        successes = m.get("successes", 0)
        failures = m.get("failures", 0)
        latencies = m.get("latencies", [])

        success_rate = (successes / requests * 100) if requests > 0 else 100.0
        failure_rate = (failures / requests * 100) if requests > 0 else 0.0

        p50 = 0.0
        p99 = 0.0
        if latencies:
            sorted_lat = sorted(latencies)
            p50 = sorted_lat[int(len(sorted_lat) * 0.5)]
            p99 = sorted_lat[int(len(sorted_lat) * 0.99)]

        snap = MonitorSnapshot(
            feature_key=feature_key,
            current_percentage=current_percentage,
            request_count=requests,
            success_count=successes,
            failure_count=failures,
            success_rate=success_rate,
            failure_rate=failure_rate,
            latency_p50_ms=p50,
            latency_p99_ms=p99,
            kpi_values=dict(m.get("kpi_latest", {})),
        )

        # Store history
        if feature_key not in self._history:
            self._history[feature_key] = []
        self._history[feature_key].append(snap)
        if len(self._history[feature_key]) > self._max_history:
            self._history[feature_key] = self._history[feature_key][-self._max_history:]

        return snap

    def get_history(
        self,
        feature_key: str,
        limit: int = 100,
    ) -> List[MonitorSnapshot]:
        """Get monitoring history for a feature."""
        history = self._history.get(feature_key, [])
        return list(reversed(history[:limit]))

    def reset(self, feature_key: Optional[str] = None) -> None:
        """Reset monitoring data."""
        if feature_key:
            self._metrics.pop(feature_key, None)
            self._history.pop(feature_key, None)
        else:
            self._metrics.clear()
            self._history.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            "monitored_features": len(self._metrics),
            "total_snapshots": sum(len(h) for h in self._history.values()),
        }
