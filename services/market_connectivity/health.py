"""
Connectivity Health Checker — Liveness, readiness, and startup probes
for the Market Connectivity Platform with circuit breaker patterns.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConnectivityHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    NOT_INITIALIZED = "not_initialized"


class ProbeType(str, Enum):
    LIVENESS = "liveness"
    READINESS = "readiness"
    STARTUP = "startup"


@dataclass
class ComponentHealth:
    component: str
    status: ConnectivityHealthStatus
    probe_type: ProbeType
    message: str = ""
    latency_ms: float = 0.0
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consecutive_failures: int = 0
    circuit_open: bool = False


@dataclass
class ConnectivityHealthReport:
    platform_id: str = "icyquant-connectivity"
    overall_status: ConnectivityHealthStatus = ConnectivityHealthStatus.HEALTHY
    components: list[ComponentHealth] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class ConnectivityHealthChecker:
    """
    Health checker for the Market Connectivity Platform.

    Monitors all connectivity components with liveness, readiness,
    and startup probes plus circuit breaker protection.

    Components:
        - MarketConnectivityPlatform, ConnectivityRuntime
        - ConnectionManager, SessionPool, ProtocolManager
        - HeartbeatMonitor, ReconnectManager, FailoverManager
        - EndpointDiscovery, ExchangeRegistry
        - CredentialManager, CertificateManager

    Usage::

        checker = ConnectivityHealthChecker()
        await checker.initialize()
        await checker.inject_component("connection_manager", manager)
        report = await checker.check_all(ProbeType.READINESS)
    """

    COMPONENTS = [
        "connectivity_runtime",
        "connection_manager",
        "session_pool",
        "protocol_manager",
        "heartbeat_monitor",
        "reconnect_manager",
        "failover_manager",
        "endpoint_discovery",
        "exchange_registry",
        "credential_manager",
    ]

    def __init__(
        self,
        max_consecutive_failures: int = 3,
        circuit_reset_timeout: float = 30.0,
    ) -> None:
        self.max_consecutive_failures = max_consecutive_failures
        self.circuit_reset_timeout = circuit_reset_timeout
        self._components: dict[str, ComponentHealth] = {}
        self._injectables: dict[str, Any] = {}
        self._started_at: float = 0.0

    async def initialize(self) -> None:
        """Initialize the health checker."""
        self._started_at = time.monotonic()
        for name in self.COMPONENTS:
            self._components[name] = ComponentHealth(
                component=name,
                status=ConnectivityHealthStatus.NOT_INITIALIZED,
                probe_type=ProbeType.LIVENESS,
            )
        logger.info("ConnectivityHealthChecker initialized with %d components.", len(self.COMPONENTS))

    async def stop(self) -> None:
        """Stop the health checker."""
        logger.info("ConnectivityHealthChecker stopped.")

    def inject_component(self, name: str, component: Any) -> None:
        """Inject a component for health checking."""
        self._injectables[name] = component

    # ---- Health Checks ----

    async def check_liveness(self) -> ConnectivityHealthReport:
        """Perform liveness probe (is the platform alive?)."""
        return await self._probe(ProbeType.LIVENESS)

    async def check_readiness(self) -> ConnectivityHealthReport:
        """Perform readiness probe (can the platform serve traffic?)."""
        return await self._probe(ProbeType.READINESS)

    async def check_startup(self) -> ConnectivityHealthReport:
        """Perform startup probe (has the platform finished initializing?)."""
        return await self._probe(ProbeType.STARTUP)

    async def check_all(self, probe_type: ProbeType = ProbeType.READINESS) -> ConnectivityHealthReport:
        """Perform a complete health check on all components."""
        return await self._probe(probe_type)

    async def check_component(self, name: str) -> Optional[ComponentHealth]:
        """Check a single component's health."""
        if name not in self._components:
            return None

        component_health = self._components[name]
        component = self._injectables.get(name)

        if component_health.circuit_open:
            logger.debug("Circuit open for %s, skipping check", name)
            return component_health

        start = time.monotonic()
        try:
            health = await self._check_component_internal(name, component)
            latency = (time.monotonic() - start) * 1000
            component_health.status = health
            component_health.latency_ms = latency
            component_health.last_checked = datetime.now(timezone.utc)
            component_health.consecutive_failures = 0
            component_health.message = f"{name}: {health.value}"
        except Exception as e:
            component_health.consecutive_failures += 1
            component_health.latency_ms = (time.monotonic() - start) * 1000
            component_health.last_checked = datetime.now(timezone.utc)
            component_health.message = str(e)

            if component_health.consecutive_failures >= self.max_consecutive_failures:
                component_health.circuit_open = True
                component_health.status = ConnectivityHealthStatus.UNHEALTHY
                logger.error("Circuit opened for %s after %d failures", name, self.max_consecutive_failures)
            else:
                component_health.status = ConnectivityHealthStatus.DEGRADED

        return component_health

    async def reset_component(self, name: str) -> None:
        """Reset the health state of a component."""
        if name in self._components:
            self._components[name] = ComponentHealth(
                component=name,
                status=ConnectivityHealthStatus.NOT_INITIALIZED,
                probe_type=ProbeType.LIVENESS,
            )
            logger.info("Health state reset for %s", name)

    # ---- Internal ----

    async def _probe(self, probe_type: ProbeType) -> ConnectivityHealthReport:
        """Execute a health probe across all components."""
        report = ConnectivityHealthReport(probe_type=probe_type)

        tasks = [self.check_component(name) for name in self.COMPONENTS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        components = []
        unhealthy = 0
        degraded = 0

        for result in results:
            if isinstance(result, ComponentHealth):
                components.append(result)
                if result.status == ConnectivityHealthStatus.UNHEALTHY:
                    unhealthy += 1
                elif result.status == ConnectivityHealthStatus.DEGRADED:
                    degraded += 1

        report.components = components
        report.uptime_seconds = time.monotonic() - self._started_at

        # Determine overall status
        if unhealthy > 0:
            report.overall_status = ConnectivityHealthStatus.UNHEALTHY
        elif degraded > 0:
            report.overall_status = ConnectivityHealthStatus.DEGRADED
        else:
            report.overall_status = ConnectivityHealthStatus.HEALTHY

        report.details = {
            "total_components": len(components),
            "healthy": len(components) - unhealthy - degraded,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "probe_type": probe_type.value,
        }

        return report

    async def _check_component_internal(
        self, name: str, component: Any
    ) -> ConnectivityHealthStatus:
        """Internal component health logic."""
        if component is None:
            return ConnectivityHealthStatus.NOT_INITIALIZED

        # Runtime / connectivity checks
        if name == "connectivity_runtime":
            status = await component.get_status()
            return (
                ConnectivityHealthStatus.HEALTHY
                if status.get("status") == "running"
                else ConnectivityHealthStatus.DEGRADED
            )

        if name == "connection_manager":
            summary = await component.get_summary()
            return (
                ConnectivityHealthStatus.HEALTHY
                if summary.get("connected", 0) > 0
                else ConnectivityHealthStatus.DEGRADED
            )

        if name == "session_pool":
            status = await component.get_status()
            return (
                ConnectivityHealthStatus.HEALTHY
                if status.get("total_available", 0) > 0
                else ConnectivityHealthStatus.DEGRADED
            )

        if name == "protocol_manager":
            protocols = component.list_protocols()
            return (
                ConnectivityHealthStatus.HEALTHY
                if protocols
                else ConnectivityHealthStatus.UNHEALTHY
            )

        if name == "heartbeat_monitor":
            summary = await component.get_summary()
            dead = summary.get("dead", 0)
            return (
                ConnectivityHealthStatus.UNHEALTHY if dead > 0
                else ConnectivityHealthStatus.HEALTHY
            )

        if name in ("reconnect_manager", "failover_manager"):
            summary = await component.get_summary()
            failed = summary.get("failed", 0)
            return (
                ConnectivityHealthStatus.UNHEALTHY if failed > 0
                else ConnectivityHealthStatus.HEALTHY
            )

        if name == "endpoint_discovery":
            summary = await component.get_summary()
            unhealthy_endpoints = summary.get("unhealthy_endpoints", 0)
            total = summary.get("total_endpoints", 0)
            if total == 0:
                return ConnectivityHealthStatus.DEGRADED
            ratio = unhealthy_endpoints / total
            if ratio > 0.5:
                return ConnectivityHealthStatus.UNHEALTHY
            if ratio > 0.2:
                return ConnectivityHealthStatus.DEGRADED
            return ConnectivityHealthStatus.HEALTHY

        if name == "exchange_registry":
            await component.get_summary()
            return ConnectivityHealthStatus.HEALTHY

        if name == "credential_manager":
            summary = await component.get_summary()
            return (
                ConnectivityHealthStatus.HEALTHY
                if summary.get("active", 0) > 0
                else ConnectivityHealthStatus.DEGRADED
            )

        return ConnectivityHealthStatus.HEALTHY
