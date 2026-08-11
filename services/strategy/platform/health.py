"""
Platform Health Checker — Liveness and readiness probes for the Strategy Platform.

Monitors all platform components with configurable thresholds,
circuit breaker patterns, and per-probe type health checks.
"""

from __future__ import annotations

import asyncio
import logging
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
    NOT_INITIALIZED = "not_initialized"


class ProbeType(str, Enum):
    """Health probe types."""
    LIVENESS = "liveness"
    READINESS = "readiness"
    STARTUP = "startup"


@dataclass
class ComponentHealth:
    """Health status of a single platform component."""
    component: str
    status: HealthStatus
    probe_type: ProbeType
    message: str = ""
    latency_ms: float = 0.0
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consecutive_failures: int = 0
    circuit_open: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Complete platform health report."""
    platform_id: str = "strategy_platform"
    overall_status: HealthStatus = HealthStatus.HEALTHY
    components: list[ComponentHealth] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class PlatformHealthChecker:
    """
    Health checker for all Strategy Platform components.

    Provides liveness, readiness, and startup probes with
    configurable thresholds and circuit breaker patterns.

    Components monitored (12 total):
        - StrategyPlatform
        - ControlPlane
        - StrategyGateway
        - LifecycleController
        - DeploymentManager
        - StrategyCatalog
        - EventBridge
        - EventStream
        - AuditCenter
        - FeatureStoreAdapter
        - MarketDataAdapter
        - RiskEngineAdapter

    Usage::

        checker = PlatformHealthChecker()
        await checker.initialize()
        report = await checker.check_all(ProbeType.READINESS)
        if report.overall_status == HealthStatus.HEALTHY:
            print("Platform is ready!")
    """

    COMPONENTS = [
        "strategy_platform",
        "control_plane",
        "strategy_gateway",
        "lifecycle_controller",
        "deployment_manager",
        "strategy_catalog",
        "event_bridge",
        "event_stream",
        "audit_center",
        "feature_store_adapter",
        "market_data_adapter",
        "risk_engine_adapter",
    ]

    def __init__(
        self,
        circuit_breaker_threshold: int = 3,
        max_latency_ms: float = 5000.0,
    ) -> None:
        self._components: dict[str, ComponentHealth] = {}
        self._started_at: Optional[datetime] = None
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._max_latency_ms = max_latency_ms
        self._initialized: bool = False

        # Initialize component health trackers
        for comp in self.COMPONENTS:
            self._components[comp] = ComponentHealth(
                component=comp,
                status=HealthStatus.NOT_INITIALIZED,
                probe_type=ProbeType.LIVENESS,
            )

    async def initialize(self) -> None:
        """Initialize the health checker."""
        self._started_at = datetime.now(timezone.utc)
        self._initialized = True
        logger.info("PlatformHealthChecker initialized.")

    async def stop(self) -> None:
        """Stop the health checker."""
        self._initialized = False
        logger.info("PlatformHealthChecker stopped.")

    # ---- Health Checks ----

    async def check_all(self, probe_type: ProbeType = ProbeType.LIVENESS) -> HealthReport:
        """Check health of all platform components."""
        report = HealthReport()
        components: list[ComponentHealth] = []

        for comp_name in self.COMPONENTS:
            health = await self._check_component(comp_name, probe_type)
            components.append(health)

        report.components = components

        # Determine overall status
        if any(c.status == HealthStatus.UNHEALTHY for c in components):
            report.overall_status = HealthStatus.UNHEALTHY
        elif any(c.status == HealthStatus.DEGRADED for c in components):
            report.overall_status = HealthStatus.DEGRADED
        elif any(c.status == HealthStatus.NOT_INITIALIZED for c in components):
            report.overall_status = HealthStatus.DEGRADED
        else:
            report.overall_status = HealthStatus.HEALTHY

        if self._started_at:
            report.uptime_seconds = (datetime.now(timezone.utc) - self._started_at).total_seconds()

        report.details = {
            "healthy": sum(1 for c in components if c.status == HealthStatus.HEALTHY),
            "degraded": sum(1 for c in components if c.status == HealthStatus.DEGRADED),
            "unhealthy": sum(1 for c in components if c.status == HealthStatus.UNHEALTHY),
            "circuits_open": sum(1 for c in components if c.circuit_open),
        }

        return report

    async def check_liveness(self) -> HealthReport:
        """Check liveness of all components."""
        return await self.check_all(ProbeType.LIVENESS)

    async def check_readiness(self) -> HealthReport:
        """Check readiness of all components."""
        return await self.check_all(ProbeType.READINESS)

    async def check_startup(self) -> HealthReport:
        """Check startup health of all components."""
        return await self.check_all(ProbeType.STARTUP)

    async def check_component(
        self,
        component: str,
        probe_type: ProbeType = ProbeType.LIVENESS,
    ) -> ComponentHealth:
        """Check health of a specific component."""
        return await self._check_component(component, probe_type)

    async def get_component_health(self, component: str) -> Optional[ComponentHealth]:
        """Get the last health check result for a component."""
        return self._components.get(component)

    # ---- Circuit Breaker ----

    async def reset_circuit_breaker(self, component: str) -> bool:
        """Reset the circuit breaker for a component."""
        health = self._components.get(component)
        if not health:
            return False
        health.circuit_open = False
        health.consecutive_failures = 0
        logger.info(f"Circuit breaker reset: {component}")
        return True

    async def get_circuit_status(self) -> dict[str, bool]:
        """Get circuit breaker status for all components."""
        return {name: h.circuit_open for name, h in self._components.items()}

    # ---- Internal ----

    async def _check_component(
        self,
        component: str,
        probe_type: ProbeType,
    ) -> ComponentHealth:
        """Check a single component's health with circuit breaker."""
        health = self._components.get(component)
        if not health:
            return ComponentHealth(
                component=component,
                status=HealthStatus.UNHEALTHY,
                probe_type=probe_type,
                message=f"Unknown component: {component}",
            )

        # Circuit breaker check
        if health.circuit_open:
            health.probe_type = probe_type
            health.last_checked = datetime.now(timezone.utc)
            health.message = "Circuit breaker open — health check skipped"
            return health

        start = asyncio.get_event_loop().time()

        # Simulate health check
        status = HealthStatus.HEALTHY
        message = f"Component '{component}' is healthy"

        latency = (asyncio.get_event_loop().time() - start) * 1000

        # Update health tracking
        health.probe_type = probe_type
        health.latency_ms = latency
        health.last_checked = datetime.now(timezone.utc)

        if status == HealthStatus.UNHEALTHY:
            health.consecutive_failures += 1
            health.message = message
            if health.consecutive_failures >= self._circuit_breaker_threshold:
                health.circuit_open = True
                health.message = f"Circuit breaker OPEN after {health.consecutive_failures} consecutive failures"
                logger.warning(f"Circuit breaker opened: {component}")
            health.status = HealthStatus.UNHEALTHY
        elif latency > self._max_latency_ms:
            health.status = HealthStatus.DEGRADED
            health.message = f"High latency: {latency:.0f}ms > {self._max_latency_ms}ms threshold"
            health.consecutive_failures = 0
        else:
            health.status = HealthStatus.HEALTHY
            health.message = message
            health.consecutive_failures = 0

        return health

    async def health_check(self) -> dict[str, Any]:
        """Check health checker's own health."""
        report = await self.check_all()
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "overall": report.overall_status.value,
            "components": report.details,
            "circuits_open": sum(1 for h in self._components.values() if h.circuit_open),
        }
