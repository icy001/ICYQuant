"""
Analytics Health — Kubernetes-compatible health probes for the analytics platform.

Provides Liveness, Readiness, and Startup probes for container orchestration.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"


@dataclass
class HealthProbeResult:
    """Result of a health probe."""
    status: HealthStatus
    checks: dict[str, bool]
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class AnalyticsHealth:
    """
    Kubernetes-compatible health probes for the analytics platform.

    Implements:
    - Liveness probe: Is the process alive?
    - Readiness probe: Is the service ready to serve requests?
    - Startup probe: Has the service finished initializing?

    Usage::

        health = AnalyticsHealth()
        await health.initialize()
        await health.set_ready()

        # Probe endpoints
        liveness = await health.liveness_probe()
        readiness = await health.readiness_probe()
        startup = await health.startup_probe()
    """

    def __init__(self) -> None:
        self._is_ready = False
        self._is_started = False
        self._initialized = False
        self._last_liveness: Optional[datetime] = None
        self._circuit_breaker_tripped = False
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        self._dependency_checks: dict[str, Callable] = {}

    async def initialize(self) -> None:
        """Initialize health probe system."""
        self._initialized = True
        self._is_started = True
        logger.info("AnalyticsHealth initialized.")

    async def set_ready(self) -> None:
        """Mark the service as ready."""
        self._is_ready = True
        logger.info("AnalyticsHealth: service marked as ready.")

    async def set_not_ready(self) -> None:
        """Mark the service as not ready."""
        self._is_ready = False
        logger.warning("AnalyticsHealth: service marked as not ready.")

    def register_dependency(self, name: str, check_fn: Callable) -> None:
        """Register a dependency health check."""
        self._dependency_checks[name] = check_fn

    # ---- Probe Endpoints ----

    async def liveness_probe(self) -> HealthProbeResult:
        """
        Liveness probe — Is the process alive?

        Returns healthy if the process is running, circuit breaker not tripped.
        """
        t_start = time.perf_counter()

        if not self._initialized:
            return HealthProbeResult(
                status=HealthStatus.STARTING,
                checks={},
                message="Service is still initializing.",
            )

        if self._circuit_breaker_tripped:
            return HealthProbeResult(
                status=HealthStatus.UNHEALTHY,
                checks={},
                message="Circuit breaker tripped.",
            )

        self._last_liveness = datetime.now(timezone.utc)
        self._consecutive_failures = 0

        elapsed_ms = (time.perf_counter() - t_start) * 1000
        return HealthProbeResult(
            status=HealthStatus.HEALTHY,
            checks={"alive": True},
            message="Service is alive.",
            latency_ms=elapsed_ms,
        )

    async def readiness_probe(self) -> HealthProbeResult:
        """
        Readiness probe — Is the service ready to serve requests?

        Checks all dependencies and internal state.
        """
        t_start = time.perf_counter()

        if not self._is_ready:
            return HealthProbeResult(
                status=HealthStatus.STARTING,
                checks={"ready": False},
                message="Service is not yet ready.",
            )

        # Check dependencies
        checks: dict[str, bool] = {}
        all_healthy = True

        for name, check_fn in self._dependency_checks.items():
            try:
                result = check_fn()
                checks[name] = bool(result)
                if not result:
                    all_healthy = False
            except Exception:
                checks[name] = False
                all_healthy = False

        elapsed_ms = (time.perf_counter() - t_start) * 1000

        if all_healthy:
            self._consecutive_failures = 0
            return HealthProbeResult(
                status=HealthStatus.HEALTHY,
                checks=checks,
                message="All dependencies healthy.",
                latency_ms=elapsed_ms,
            )
        else:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._max_consecutive_failures:
                self._circuit_breaker_tripped = True
                logger.error("AnalyticsHealth: circuit breaker tripped.")

            return HealthProbeResult(
                status=HealthStatus.DEGRADED,
                checks=checks,
                message=f"Some dependencies unhealthy: {[k for k, v in checks.items() if not v]}",
                latency_ms=elapsed_ms,
            )

    async def startup_probe(self) -> HealthProbeResult:
        """
        Startup probe — Has the service finished initializing?
        """
        t_start = time.perf_counter()
        elapsed_ms = (time.perf_counter() - t_start) * 1000

        if self._is_started:
            return HealthProbeResult(
                status=HealthStatus.HEALTHY,
                checks={"started": True},
                message="Service startup complete.",
                latency_ms=elapsed_ms,
            )

        return HealthProbeResult(
            status=HealthStatus.STARTING,
            checks={"started": False},
            message="Service is still starting up.",
            latency_ms=elapsed_ms,
        )

    # ---- Circuit Breaker ----

    async def reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker."""
        self._circuit_breaker_tripped = False
        self._consecutive_failures = 0
        logger.info("AnalyticsHealth: circuit breaker reset.")

    def is_healthy(self) -> bool:
        """Quick check: is the service healthy?"""
        return (
            self._initialized
            and self._is_ready
            and not self._circuit_breaker_tripped
        )

    # ---- Health Summary ----

    async def get_health_summary(self) -> dict[str, Any]:
        """Get a comprehensive health summary."""
        return {
            "status": "healthy" if self.is_healthy() else "degraded",
            "initialized": self._initialized,
            "ready": self._is_ready,
            "started": self._is_started,
            "circuit_breaker_tripped": self._circuit_breaker_tripped,
            "consecutive_failures": self._consecutive_failures,
            "last_liveness": self._last_liveness.isoformat() if self._last_liveness else None,
            "dependencies": list(self._dependency_checks.keys()),
        }
