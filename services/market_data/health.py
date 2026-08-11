"""
Market Data Health Checker — liveness, readiness, and startup probes
with circuit breaker support for the normalization pipeline.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Component health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPING = "stopping"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component."""

    component: str = ""
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    last_checked: Optional[datetime] = None
    details: dict[str, Any] = field(default_factory=dict)

    # Circuit breaker
    consecutive_failures: int = 0
    circuit_open: bool = False
    failure_threshold: int = 5
    recovery_timeout_s: float = 30.0
    last_failure_time: Optional[datetime] = None

    def record_success(self) -> None:
        self.status = HealthStatus.HEALTHY
        self.consecutive_failures = 0
        self.circuit_open = False
        self.last_checked = datetime.now(timezone.utc)

    def record_failure(self, message: str = "") -> None:
        self.consecutive_failures += 1
        self.last_failure_time = datetime.now(timezone.utc)
        self.last_checked = datetime.now(timezone.utc)
        self.message = message

        if self.consecutive_failures >= self.failure_threshold:
            self.circuit_open = True
            self.status = HealthStatus.UNHEALTHY
        else:
            self.status = HealthStatus.DEGRADED

    def check_recovery(self) -> bool:
        """Check if circuit breaker can be reset."""
        if not self.circuit_open or self.last_failure_time is None:
            return False

        elapsed = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
        if elapsed >= self.recovery_timeout_s:
            self.circuit_open = False
            self.status = HealthStatus.HEALTHY
            self.consecutive_failures = 0
            return True
        return False


@dataclass
class HealthReport:
    """Aggregated health report for all components."""

    status: HealthStatus = HealthStatus.UNKNOWN
    components: dict[str, ComponentHealth] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    uptime_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def healthy_count(self) -> int:
        return sum(1 for c in self.components.values() if c.status == HealthStatus.HEALTHY)

    @property
    def degraded_count(self) -> int:
        return sum(1 for c in self.components.values() if c.status == HealthStatus.DEGRADED)

    @property
    def unhealthy_count(self) -> int:
        return sum(1 for c in self.components.values() if c.status == HealthStatus.UNHEALTHY)


class MarketDataHealthChecker:
    """
    Health checker for the market data normalization pipeline.

    Monitors 10+ components:
    - MarketDataEngine
    - MarketDataPipeline
    - Normalizers (per asset class)
    - Validators
    - Quality Engine
    - Cache
    - Detectors (duplicate, gap, outlier)
    - Symbol/Exchange Mappers
    - Schema Registry
    - Instrument Registry

    Supports:
    - Liveness probes: Is the process alive?
    - Readiness probes: Is the service ready to accept work?
    - Startup probes: Has the service initialized?
    - Circuit breakers: Prevent cascading failures
    """

    def __init__(self) -> None:
        self._components: dict[str, ComponentHealth] = {}
        self._start_time = time.perf_counter()
        self._is_ready = False
        self._is_initialized = False

    async def initialize(self) -> None:
        """Mark the service as initialized (startup probe)."""
        self._is_initialized = True
        logger.info("MarketDataHealthChecker initialized")

    async def mark_ready(self) -> None:
        """Mark the service as ready to accept work."""
        self._is_ready = True
        logger.info("Market data service marked ready")

    # ── Component registration ─────────────────────

    async def register_component(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_s: float = 30.0,
    ) -> ComponentHealth:
        """Register a component for health monitoring."""
        health = ComponentHealth(
            component=name,
            status=HealthStatus.STARTING,
            failure_threshold=failure_threshold,
            recovery_timeout_s=recovery_timeout_s,
            last_checked=datetime.now(timezone.utc),
        )
        self._components[name] = health
        return health

    async def report_healthy(self, component: str, message: str = "") -> None:
        """Report a component as healthy."""
        health = self._components.get(component)
        if health:
            health.record_success()
            health.message = message

    async def report_unhealthy(self, component: str, message: str = "") -> None:
        """Report a component as unhealthy."""
        health = self._components.get(component)
        if health:
            health.record_failure(message)

    async def report_degraded(self, component: str, message: str = "") -> None:
        """Report a component as degraded."""
        health = self._components.get(component)
        if health:
            health.status = HealthStatus.DEGRADED
            health.message = message
            health.last_checked = datetime.now(timezone.utc)

    # ── Probes ─────────────────────────────────────

    async def liveness(self) -> tuple[bool, HealthStatus]:
        """Liveness probe — is the process alive?"""
        return True, HealthStatus.HEALTHY

    async def readiness(self) -> tuple[bool, HealthStatus]:
        """Readiness probe — is the service ready to accept work?"""
        if not self._is_ready:
            return False, HealthStatus.STARTING

        # Check for any unhealthy components
        for health in self._components.values():
            if health.circuit_open:
                return False, HealthStatus.DEGRADED

        return True, HealthStatus.HEALTHY

    async def startup(self) -> tuple[bool, HealthStatus]:
        """Startup probe — has the service initialized?"""
        if not self._is_initialized:
            return False, HealthStatus.STARTING
        return True, HealthStatus.HEALTHY

    async def full_health_check(self) -> HealthReport:
        """Run a comprehensive health check across all components."""

        # Check circuit breaker recovery
        for health in self._components.values():
            health.check_recovery()

        # Determine overall status
        unhealthy = any(c.status == HealthStatus.UNHEALTHY for c in self._components.values())
        degraded = any(c.status == HealthStatus.DEGRADED for c in self._components.values())

        if unhealthy:
            overall = HealthStatus.UNHEALTHY
        elif degraded:
            overall = HealthStatus.DEGRADED
        elif not self._is_ready:
            overall = HealthStatus.STARTING
        else:
            overall = HealthStatus.HEALTHY

        return HealthReport(
            status=overall,
            components=dict(self._components),
            timestamp=datetime.now(timezone.utc),
            uptime_seconds=time.perf_counter() - self._start_time,
        )

    # ── Query ──────────────────────────────────────

    async def get_component_health(self, component: str) -> Optional[ComponentHealth]:
        """Get health status for a specific component."""
        return self._components.get(component)

    async def get_unhealthy_components(self) -> list[ComponentHealth]:
        """Get all unhealthy or degraded components."""
        return [c for c in self._components.values()
                if c.status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED)]

    @property
    def component_count(self) -> int:
        return len(self._components)

    @property
    def uptime_seconds(self) -> float:
        return time.perf_counter() - self._start_time
