"""
Streaming Health Checker — liveness, readiness, and startup probes
for the real-time streaming platform.

Commit 16 Part 1.4
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


class StreamingHealthStatus(str, Enum):
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
    """Health status of a streaming component."""
    component: str
    status: StreamingHealthStatus
    probe_type: ProbeType
    message: str = ""
    latency_ms: float = 0.0
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consecutive_failures: int = 0
    circuit_open: bool = False


@dataclass
class StreamingHealthReport:
    """Complete health report."""
    platform_id: str = "icyquant-streaming"
    overall_status: StreamingHealthStatus = StreamingHealthStatus.HEALTHY
    components: list[ComponentHealth] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class StreamingHealthChecker:
    """
    Health checker for the streaming platform.

    Monitors: StreamingEngine, StreamingRuntime, TopicRegistry,
    Publisher, Subscriber, EventRouter, WindowManager,
    CheckpointManager, ExactlyOnceEngine, DeadLetterQueue,
    BackpressureController.

    Usage::

        checker = StreamingHealthChecker()
        await checker.initialize()
        checker.inject_component("streaming_engine", engine)
        report = await checker.readiness()
    """

    COMPONENTS = [
        "streaming_engine",
        "streaming_runtime",
        "topic_registry",
        "publisher",
        "subscriber",
        "event_router",
        "event_dispatcher",
        "window_manager",
        "aggregation_engine",
        "checkpoint_manager",
        "exactly_once_engine",
        "dead_letter_queue",
        "backpressure_controller",
        "retry_manager",
        "enrichment_engine",
        "state_store",
        "schema_registry",
    ]

    def __init__(self, max_consecutive_failures: int = 3, circuit_reset_timeout: float = 30.0) -> None:
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
                status=StreamingHealthStatus.NOT_INITIALIZED,
                probe_type=ProbeType.LIVENESS,
            )
        logger.info("StreamingHealthChecker initialized (%d components).", len(self.COMPONENTS))

    async def stop(self) -> None:
        """Stop the health checker."""
        logger.info("StreamingHealthChecker stopped.")

    def inject_component(self, name: str, component: Any) -> None:
        """Inject a component for health checking."""
        self._injectables[name] = component
        if name in self._components:
            self._components[name].status = StreamingHealthStatus.HEALTHY
            self._components[name].message = "Component injected"

    async def _check_component(self, name: str, probe_type: ProbeType) -> ComponentHealth:
        """Check a single component."""
        health = self._components.get(name)
        if health is None:
            health = ComponentHealth(component=name, status=StreamingHealthStatus.NOT_INITIALIZED, probe_type=probe_type)
            self._components[name] = health

        start = time.monotonic()
        component = self._injectables.get(name)

        if health.circuit_open:
            if (time.monotonic() - health.last_checked.timestamp()) > self.circuit_reset_timeout:
                health.circuit_open = False
            else:
                health.status = StreamingHealthStatus.DEGRADED
                health.message = "Circuit open"
                return health

        if component is None:
            if probe_type == ProbeType.STARTUP:
                health.status = StreamingHealthStatus.NOT_INITIALIZED
                health.message = "Not initialized"
            elif probe_type == ProbeType.LIVENESS:
                health.status = StreamingHealthStatus.HEALTHY
                health.message = "Component not injected (liveness OK)"
            else:
                health.status = StreamingHealthStatus.DEGRADED
                health.message = "Not available"
        else:
            health.status = StreamingHealthStatus.HEALTHY
            health.message = "OK"
            health.consecutive_failures = 0

        health.latency_ms = (time.monotonic() - start) * 1000
        health.last_checked = datetime.now(timezone.utc)
        health.probe_type = probe_type
        return health

    async def check_all(self, probe_type: ProbeType = ProbeType.READINESS) -> StreamingHealthReport:
        """Check all components."""
        tasks = [self._check_component(name, probe_type) for name in self.COMPONENTS]
        components = await asyncio.gather(*tasks)

        report = StreamingHealthReport(
            components=list(components),
            uptime_seconds=time.monotonic() - self._started_at,
        )

        statuses = [c.status for c in report.components]
        if StreamingHealthStatus.UNHEALTHY in statuses:
            report.overall_status = StreamingHealthStatus.UNHEALTHY
        elif StreamingHealthStatus.DEGRADED in statuses:
            report.overall_status = StreamingHealthStatus.DEGRADED
        elif StreamingHealthStatus.NOT_INITIALIZED in statuses:
            if probe_type == ProbeType.STARTUP:
                report.overall_status = StreamingHealthStatus.NOT_INITIALIZED
            else:
                report.overall_status = StreamingHealthStatus.DEGRADED
        else:
            report.overall_status = StreamingHealthStatus.HEALTHY

        healthy = sum(1 for c in components if c.status == StreamingHealthStatus.HEALTHY)
        degraded = sum(1 for c in components if c.status == StreamingHealthStatus.DEGRADED)
        unhealthy = sum(1 for c in components if c.status == StreamingHealthStatus.UNHEALTHY)

        report.details = {
            "healthy_count": healthy,
            "degraded_count": degraded,
            "unhealthy_count": unhealthy,
            "total_components": len(components),
        }

        logger.info("Health check [%s]: %s (%d/%d/%d)", probe_type.value, report.overall_status.value, healthy, degraded, unhealthy)
        return report

    async def liveness(self) -> StreamingHealthReport:
        """Run liveness probe."""
        return await self.check_all(ProbeType.LIVENESS)

    async def readiness(self) -> StreamingHealthReport:
        """Run readiness probe."""
        return await self.check_all(ProbeType.READINESS)

    async def startup(self) -> StreamingHealthReport:
        """Run startup probe."""
        return await self.check_all(ProbeType.STARTUP)
