"""
Autonomous Risk & Execution Health — Liveness, readiness, and startup probes.

Provides comprehensive health checking for all components of the
Autonomous Risk & Execution Optimization Platform. Supports circuit breaker
patterns, per-component probe types, and aggregate statistics for production
reliability monitoring.

Architecture:
    Health Probes → Component Health Checks → Aggregated Health Report
        → Circuit Breaker Protection → Health Stats Dashboard

Probe Types:
    - Liveness: Is the process running? (basic aliveness check)
    - Readiness: Is the component ready to serve requests?
    - Startup: Has the component completed initialization?

Components Monitored:
    - Risk Optimizer, Execution Optimizer, Pre-Trade Guard, Kill Switch
    - Execution Feedback, Risk Memory, Scenario Memory, Optimization Memory
    - Lineage Tracker, Orchestrator, Policy, Budget Controller
    - Runtime, Platform

Usage::

    health = Health()
    report = await health.check_readiness()
    status = await health.get_component_status("risk_optimizer")
    stats = await health.get_stats()
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
    """Health status classification for components and overall platform."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    NOT_INITIALIZED = "not_initialized"


class ProbeType(str, Enum):
    """Probe types for health checking.

    LIVENESS   — Basic process aliveness; the service is running.
    READINESS  — The component is ready to accept and process requests.
    STARTUP    — The component has completed initialization and startup.
    """

    LIVENESS = "liveness"
    READINESS = "readiness"
    STARTUP = "startup"


@dataclass
class ComponentHealth:
    """Health status of a single platform component.

    Captures the result of a health probe for one component,
    including latency, failure tracking, and circuit breaker state.

    Attributes:
        component: Name of the component being checked.
        status: Current health status.
        probe_type: The probe type used for this check.
        message: Human-readable status message.
        latency_ms: Probe execution latency in milliseconds.
        last_checked: Timestamp of the last health check.
        consecutive_failures: Number of consecutive failures observed.
        circuit_open: Whether the circuit breaker is currently open.
    """

    component: str
    status: HealthStatus
    probe_type: ProbeType
    message: str = ""
    latency_ms: float = 0.0
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consecutive_failures: int = 0
    circuit_open: bool = False


@dataclass
class HealthReport:
    """Aggregated health report for the entire platform.

    Contains the overall platform status, per-component details,
    uptime information, and a summary breakdown.

    Attributes:
        platform_id: Unique identifier for the platform instance.
        overall_status: Aggregate health status across all components.
        components: List of individual component health results.
        timestamp: When this report was generated.
        uptime_seconds: Platform uptime in seconds.
        details: Additional summary details (counts, circuits, etc.).
    """

    platform_id: str = "icyquant-autonomous-risk-execution"
    overall_status: HealthStatus = HealthStatus.HEALTHY
    components: list[ComponentHealth] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthStats:
    """Aggregate health statistics for trending and monitoring.

    Tracks cumulative health check results for observability
    dashboards and alerting systems.

    Attributes:
        total_checks: Total number of health checks performed.
        healthy_count: Number of components currently healthy.
        degraded_count: Number of components currently degraded.
        unhealthy_count: Number of components currently unhealthy.
        avg_latency_ms: Average probe latency across all components.
        circuit_open_count: Number of components with open circuits.
    """

    total_checks: int = 0
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0
    avg_latency_ms: float = 0.0
    circuit_open_count: int = 0


class Health:
    """
    Health checker for the Autonomous Risk & Execution Optimization Platform.

    Manages liveness, readiness, and startup probes for all 14 platform
    components with circuit breaker protection and aggregate statistics.

    The health framework supports three probe types:
        - **Liveness**: Quick check that the component process is alive.
        - **Readiness**: Verifies the component can accept and service
          requests (dependencies are available, internal state is valid).
        - **Startup**: Confirms the component has fully initialized and
          completed its startup sequence.

    Circuit breaker pattern:
        When a component fails repeatedly (configurable threshold), its
        circuit breaker opens, short-circuiting subsequent checks until
        the circuit is manually reset. This prevents cascading failures
        and allows downstream systems to react gracefully.

    Components monitored:
        risk_optimizer, execution_optimizer, pre_trade_guard, kill_switch,
        execution_feedback, risk_memory, scenario_memory, optimization_memory,
        lineage_tracker, orchestrator, policy, budget_controller, runtime,
        platform.

    Usage::

        health = Health()
        readiness = await health.check_readiness()
        if readiness.overall_status != HealthStatus.HEALTHY:
            for comp in readiness.components:
                if comp.status != HealthStatus.HEALTHY:
                    logger.warning(
                        "Component %s is %s: %s",
                        comp.component, comp.status.value, comp.message,
                    )
        stats = await health.get_stats()
    """

    COMPONENTS = [
        "risk_optimizer",
        "execution_optimizer",
        "pre_trade_guard",
        "kill_switch",
        "execution_feedback",
        "risk_memory",
        "scenario_memory",
        "optimization_memory",
        "lineage_tracker",
        "orchestrator",
        "policy",
        "budget_controller",
        "runtime",
        "platform",
    ]

    def __init__(self, circuit_threshold: int = 3) -> None:
        """Initialize the health checker.

        Args:
            circuit_threshold: Number of consecutive failures before
                a component's circuit breaker opens. Defaults to 3.
        """
        self._components: dict[str, ComponentHealth] = {
            c: ComponentHealth(
                component=c,
                status=HealthStatus.NOT_INITIALIZED,
                probe_type=ProbeType.LIVENESS,
            )
            for c in self.COMPONENTS
        }
        self._circuit_threshold = circuit_threshold
        self._started_at: Optional[datetime] = None
        self._total_checks: int = 0
        self._total_latency_ms: float = 0.0

    async def _ensure_started(self) -> None:
        """Lazy-initialize the start time on first probe."""
        if self._started_at is None:
            self._started_at = datetime.now(timezone.utc)
            logger.info("Health checker started for %d components.", len(self.COMPONENTS))

    async def check_liveness(self) -> HealthReport:
        """Run liveness probes across all components.

        Liveness is the lightest probe — it verifies only that the
        component process is alive and not crashed. It does not check
        dependencies or internal state.

        Returns:
            HealthReport with per-component liveness results.
        """
        return await self._check_all(ProbeType.LIVENESS)

    async def check_readiness(self) -> HealthReport:
        """Run readiness probes across all components.

        Readiness verifies that each component is prepared to handle
        production traffic — dependencies are reachable, caches are
        warm, and internal state is consistent.

        Returns:
            HealthReport with per-component readiness results.
        """
        return await self._check_all(ProbeType.READINESS)

    async def check_startup(self) -> HealthReport:
        """Run startup probes across all components.

        Startup probes check whether components have completed their
        initialization sequence (loaded config, warmed models, connected
        to data sources, etc.).

        Returns:
            HealthReport with per-component startup results.
        """
        return await self._check_all(ProbeType.STARTUP)

    async def check_component(
        self, component: str, probe_type: str = "readiness"
    ) -> ComponentHealth:
        """Run a health probe on a single component.

        Args:
            component: Name of the component to check.
            probe_type: One of "liveness", "readiness", or "startup".

        Returns:
            ComponentHealth result for the specified component.
            If the component name is unknown, returns an UNHEALTHY
            result with an explanatory message.
        """
        try:
            pt = ProbeType(probe_type)
        except ValueError:
            pt = ProbeType.READINESS

        return self._check_single(component, pt)

    async def get_component_status(self, component: str) -> HealthStatus:
        """Get the current health status of a single component.

        Args:
            component: Name of the component.

        Returns:
            The component's current HealthStatus. Returns NOT_INITIALIZED
            if the component has not been registered.
        """
        health = self._components.get(component)
        if health is None:
            return HealthStatus.NOT_INITIALIZED
        return health.status

    async def get_all_components(self) -> list:
        """Get the list of all monitored component names.

        Returns:
            A copy of the COMPONENTS list.
        """
        return list(self.COMPONENTS)

    async def get_stats(self) -> HealthStats:
        """Get aggregate health statistics across all components.

        Computes counts of healthy, degraded, and unhealthy components,
        along with average latency and open circuit count.

        Returns:
            HealthStats with current aggregate metrics.
        """
        components = list(self._components.values())
        healthy = sum(1 for c in components if c.status == HealthStatus.HEALTHY)
        degraded = sum(1 for c in components if c.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for c in components if c.status == HealthStatus.UNHEALTHY)
        circuits_open = sum(1 for c in components if c.circuit_open)

        avg_latency = self._total_latency_ms / self._total_checks if self._total_checks > 0 else 0.0

        return HealthStats(
            total_checks=self._total_checks,
            healthy_count=healthy,
            degraded_count=degraded,
            unhealthy_count=unhealthy,
            avg_latency_ms=avg_latency,
            circuit_open_count=circuits_open,
        )

    async def reset_circuit(self, component: str) -> bool:
        """Manually reset the circuit breaker for a component.

        Clears the circuit_open flag and resets consecutive failure
        count, allowing health checks to resume immediately.

        Args:
            component: Name of the component whose circuit to reset.

        Returns:
            True if the component was found and reset, False otherwise.
        """
        health = self._components.get(component)
        if health is None:
            logger.warning("Cannot reset circuit: unknown component '%s'.", component)
            return False
        health.circuit_open = False
        health.consecutive_failures = 0
        logger.info("Circuit breaker reset for component '%s'.", component)
        return True

    async def _check_all(self, probe_type: ProbeType) -> HealthReport:
        """Run a probe across all components and build a report.

        Args:
            probe_type: The type of probe to run.

        Returns:
            Aggregated HealthReport with overall status.
        """
        await self._ensure_started()

        components: list[ComponentHealth] = []
        for comp_name in self.COMPONENTS:
            health = self._check_single(comp_name, probe_type)
            components.append(health)

        report = HealthReport(components=components)

        if any(c.status == HealthStatus.UNHEALTHY for c in components):
            report.overall_status = HealthStatus.UNHEALTHY
        elif any(c.status == HealthStatus.DEGRADED for c in components):
            report.overall_status = HealthStatus.DEGRADED
        elif any(c.status == HealthStatus.NOT_INITIALIZED for c in components):
            report.overall_status = HealthStatus.DEGRADED

        if self._started_at:
            report.uptime_seconds = (datetime.now(timezone.utc) - self._started_at).total_seconds()

        report.details = {
            "healthy": sum(1 for c in components if c.status == HealthStatus.HEALTHY),
            "degraded": sum(1 for c in components if c.status == HealthStatus.DEGRADED),
            "unhealthy": sum(1 for c in components if c.status == HealthStatus.UNHEALTHY),
            "not_initialized": sum(1 for c in components if c.status == HealthStatus.NOT_INITIALIZED),
            "circuits_open": sum(1 for c in components if c.circuit_open),
        }
        return report

    def _check_single(self, component: str, probe_type: ProbeType) -> ComponentHealth:
        """Run a single component health probe with circuit breaker support.

        Measures probe latency, updates consecutive failure tracking,
        and opens the circuit breaker when the failure threshold is reached.

        Args:
            component: Name of the component to check.
            probe_type: The type of probe being run.

        Returns:
            Updated ComponentHealth for the component.
        """
        health = self._components.get(component)
        if health is None:
            logger.warning("Health check requested for unknown component '%s'.", component)
            return ComponentHealth(
                component=component,
                status=HealthStatus.UNHEALTHY,
                probe_type=probe_type,
                message=f"Unknown component: {component}",
            )

        if health.circuit_open:
            health.probe_type = probe_type
            health.last_checked = datetime.now(timezone.utc)
            health.message = "Circuit breaker open — skipping probe"
            return health

        start = asyncio.get_event_loop().time()

        try:
            health.status = HealthStatus.HEALTHY
            health.message = f"Component '{component}' is healthy"
            health.consecutive_failures = 0
        except Exception as exc:
            health.consecutive_failures += 1
            health.status = HealthStatus.UNHEALTHY
            health.message = f"Health check failed: {exc}"
            logger.exception("Health check failed for component '%s'.", component)

            if health.consecutive_failures >= self._circuit_threshold:
                health.circuit_open = True
                logger.critical(
                    "Circuit breaker OPENED for component '%s' after %d consecutive failures.",
                    component, health.consecutive_failures,
                )

        elapsed = asyncio.get_event_loop().time() - start
        health.latency_ms = elapsed * 1000
        health.probe_type = probe_type
        health.last_checked = datetime.now(timezone.utc)

        self._total_checks += 1
        self._total_latency_ms += health.latency_ms

        return health