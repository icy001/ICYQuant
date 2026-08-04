"""
Canary health monitoring.

Provides health status tracking for canary
deployments, including latency, error rates,
and business KPI monitoring.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class HealthStatus:
    """Health status constants."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """
    Result of a canary health check.

    Attributes:
        status: Overall health status.
        score: Health score (0-100).
        error_rate: Current error rate percentage.
        latency_p50_ms: P50 latency in milliseconds.
        latency_p99_ms: P99 latency in milliseconds.
        request_count: Total requests observed.
        error_count: Total errors observed.
        checks: Individual check results.
        timestamp: When the check was performed.
    """

    status: str = HealthStatus.UNKNOWN
    score: float = 100.0
    error_rate: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p99_ms: float = 0.0
    request_count: int = 0
    error_count: int = 0
    checks: Dict[str, bool] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "status": self.status,
            "score": self.score,
            "error_rate": self.error_rate,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "checks": self.checks,
            "timestamp": self.timestamp,
        }


class HealthMonitor:
    """
    Health monitoring for canary deployments.

    Collects metrics and evaluates the health
    of a canary deployment based on configurable
    thresholds for error rate, latency, and
    business KPIs.

    Usage:
        monitor = HealthMonitor()
        monitor.record_request(latency_ms=45.0, error=False)
        monitor.record_request(latency_ms=120.0, error=True)
        result = monitor.check_health(
            error_rate_threshold=5.0,
            latency_p99_threshold_ms=500.0,
        )
        # result.status == "healthy" or "warning" or "critical"
    """

    def __init__(self, max_samples: int = 10000) -> None:
        """
        Initialize the health monitor.

        Args:
            max_samples: Maximum latency samples to retain.
        """
        self._latencies: List[float] = []
        self._max_samples = max_samples
        self._request_count = 0
        self._error_count = 0
        self._timeout_count = 0
        self._exception_count = 0
        self._kpi_values: Dict[str, List[float]] = {}
        self._start_time: Optional[float] = None

    def start(self) -> None:
        """Start the health monitoring window."""
        self._start_time = time.time()
        self._latencies.clear()
        self._request_count = 0
        self._error_count = 0
        self._timeout_count = 0
        self._exception_count = 0

    def record_request(
        self,
        latency_ms: float = 0.0,
        error: bool = False,
        timeout: bool = False,
        exception: bool = False,
        kpi: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Record a request observation.

        Args:
            latency_ms: Request latency in milliseconds.
            error: Whether the request resulted in an error.
            timeout: Whether the request timed out.
            exception: Whether the request raised an exception.
            kpi: Optional business KPI values.
        """
        self._request_count += 1
        if error:
            self._error_count += 1
        if timeout:
            self._timeout_count += 1
        if exception:
            self._exception_count += 1

        if latency_ms > 0:
            self._latencies.append(latency_ms)
            if len(self._latencies) > self._max_samples:
                self._latencies = self._latencies[-self._max_samples:]

        if kpi:
            for key, value in kpi.items():
                if key not in self._kpi_values:
                    self._kpi_values[key] = []
                self._kpi_values[key].append(value)
                if len(self._kpi_values[key]) > self._max_samples:
                    self._kpi_values[key] = self._kpi_values[key][-self._max_samples:]

    def check_health(
        self,
        error_rate_threshold: float = 5.0,
        latency_p99_threshold_ms: float = 500.0,
        health_threshold: float = 95.0,
    ) -> HealthCheckResult:
        """
        Evaluate the current health status.

        Args:
            error_rate_threshold: Max error rate percentage.
            latency_p99_threshold_ms: Max P99 latency.
            health_threshold: Minimum health score.

        Returns:
            HealthCheckResult with status and details.
        """
        result = HealthCheckResult(
            request_count=self._request_count,
            error_count=self._error_count,
        )

        # Calculate error rate
        if self._request_count > 0:
            result.error_rate = (self._error_count / self._request_count) * 100

        # Calculate latencies
        if self._latencies:
            sorted_lat = sorted(self._latencies)
            result.latency_p50_ms = sorted_lat[int(len(sorted_lat) * 0.5)]
            result.latency_p99_ms = sorted_lat[int(len(sorted_lat) * 0.99)]

        # Individual checks
        error_check = result.error_rate <= error_rate_threshold
        latency_check = result.latency_p99_ms <= latency_p99_threshold_ms
        result.checks = {
            "error_rate": error_check,
            "latency_p99": latency_check,
        }

        # Calculate score
        score = 100.0
        if not error_check:
            score -= min(50, (result.error_rate / error_rate_threshold) * 25)
        if not latency_check:
            score -= min(30, (result.latency_p99_ms / latency_p99_threshold_ms) * 15)
        result.score = max(0.0, score)

        # Determine status
        if result.score >= health_threshold:
            result.status = HealthStatus.HEALTHY
        elif result.score >= health_threshold * 0.7:
            result.status = HealthStatus.WARNING
        else:
            result.status = HealthStatus.CRITICAL

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get health monitor statistics."""
        error_rate = (
            (self._error_count / self._request_count) * 100
            if self._request_count > 0
            else 0.0
        )
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "timeout_count": self._timeout_count,
            "exception_count": self._exception_count,
            "error_rate": error_rate,
            "latency_samples": len(self._latencies),
            "kpi_keys": list(self._kpi_values.keys()),
        }

    def reset(self) -> None:
        """Reset all health monitor data."""
        self._latencies.clear()
        self._request_count = 0
        self._error_count = 0
        self._timeout_count = 0
        self._exception_count = 0
        self._kpi_values.clear()
        self._start_time = None
