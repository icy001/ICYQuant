"""
Data Lake Health Checker — Liveness, readiness, and startup probes
for the enterprise historical data lake with circuit breaker patterns.

Commit 16 Part 1.3
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


class HealthStatus(str, Enum):
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
    """Health status of a single data lake component."""
    component: str
    status: HealthStatus
    probe_type: ProbeType
    message: str = ""
    latency_ms: float = 0.0
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consecutive_failures: int = 0
    circuit_open: bool = False


@dataclass
class DataLakeHealthReport:
    """Complete health report for the data lake platform."""
    platform_id: str = "icyquant-data-lake"
    overall_status: HealthStatus = HealthStatus.HEALTHY
    components: list[ComponentHealth] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class DataLakeHealthChecker:
    """
    Health checker for the enterprise historical data lake.

    Monitors all data lake components with liveness, readiness,
    and startup probes plus circuit breaker protection.

    Components monitored:
        - DataLakeEngine, DataLakeRuntime
        - StorageManager, ParquetWriter, ParquetReader
        - DatasetRegistry, MetadataCatalog, SchemaCatalog
        - VersionManager, RetentionManager, LifecycleManager
        - ReplayEngine, ReplayScheduler
        - ManifestManager, ChecksumValidator, LineageTracker
        - IndexManager, BloomFilterManager

    Usage::

        checker = DataLakeHealthChecker()
        await checker.initialize()
        await checker.inject_component("data_lake_engine", engine)
        report = await checker.check_all(ProbeType.READINESS)
    """

    COMPONENTS = [
        "data_lake_engine",
        "data_lake_runtime",
        "storage_manager",
        "parquet_writer",
        "parquet_reader",
        "dataset_registry",
        "metadata_catalog",
        "schema_catalog",
        "version_manager",
        "retention_manager",
        "lifecycle_manager",
        "replay_engine",
        "replay_scheduler",
        "manifest_manager",
        "checksum_validator",
        "lineage_tracker",
        "index_manager",
        "bloom_filter_manager",
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
                status=HealthStatus.NOT_INITIALIZED,
                probe_type=ProbeType.LIVENESS,
            )
        logger.info(
            "DataLakeHealthChecker initialized with %d components.",
            len(self.COMPONENTS),
        )

    async def stop(self) -> None:
        """Stop the health checker."""
        logger.info("DataLakeHealthChecker stopped.")

    def inject_component(self, name: str, component: Any) -> None:
        """Inject a component for health checking."""
        self._injectables[name] = component
        if name in self._components:
            self._components[name].status = HealthStatus.HEALTHY
            self._components[name].message = "Component injected"

    # ── Health Check Methods ──────────────────────────────────────

    async def _check_component(
        self, name: str, probe_type: ProbeType
    ) -> ComponentHealth:
        """Check the health of a single component."""
        health = self._components.get(name)
        if health is None:
            health = ComponentHealth(
                component=name,
                status=HealthStatus.NOT_INITIALIZED,
                probe_type=probe_type,
            )
            self._components[name] = health

        start = time.monotonic()
        component = self._injectables.get(name)

        # Circuit breaker check
        if health.circuit_open:
            now = time.monotonic()
            if (now - health.last_checked.timestamp()) > self.circuit_reset_timeout:
                health.circuit_open = False
                logger.info("Circuit reset for %s, retrying health check.", name)
            else:
                health.status = HealthStatus.DEGRADED
                health.message = "Circuit open — health check skipped"
                return health

        if component is None:
            if probe_type == ProbeType.STARTUP:
                health.status = HealthStatus.NOT_INITIALIZED
                health.message = "Component not initialized yet"
            elif probe_type == ProbeType.LIVENESS:
                health.status = HealthStatus.HEALTHY
                health.message = "Component not injected (liveness OK)"
            else:
                health.status = HealthStatus.DEGRADED
                health.message = "Component not available for readiness"
            health.latency_ms = (time.monotonic() - start) * 1000
            health.last_checked = datetime.now(timezone.utc)
            return health

        # Perform actual health check
        try:
            is_healthy = await self._probe_component(name, component, probe_type)
            if is_healthy:
                health.status = HealthStatus.HEALTHY
                health.message = "OK"
                health.consecutive_failures = 0
            else:
                health.consecutive_failures += 1
                if health.consecutive_failures >= self.max_consecutive_failures:
                    health.circuit_open = True
                    health.status = HealthStatus.UNHEALTHY
                    health.message = (
                        f"Component unhealthy after {health.consecutive_failures} "
                        f"consecutive failures — circuit open"
                    )
                else:
                    health.status = HealthStatus.DEGRADED
                    health.message = f"Health check failed ({health.consecutive_failures}/{self.max_consecutive_failures})"
        except Exception as e:
            health.consecutive_failures += 1
            if health.consecutive_failures >= self.max_consecutive_failures:
                health.circuit_open = True
            health.status = HealthStatus.UNHEALTHY
            health.message = f"Error: {e}"

        health.latency_ms = (time.monotonic() - start) * 1000
        health.last_checked = datetime.now(timezone.utc)
        health.probe_type = probe_type
        return health

    async def _probe_component(
        self, name: str, component: Any, probe_type: ProbeType
    ) -> bool:
        """Probe a specific component for health."""
        probe_methods = {
            "data_lake_engine": lambda c: hasattr(c, "ingest"),
            "data_lake_runtime": lambda c: hasattr(c, "stats"),
            "storage_manager": lambda c: hasattr(c, "write_batch"),
            "parquet_writer": lambda c: hasattr(c, "write_batch"),
            "parquet_reader": lambda c: hasattr(c, "read_file"),
            "dataset_registry": lambda c: hasattr(c, "register"),
            "metadata_catalog": lambda c: hasattr(c, "register_entry"),
            "schema_catalog": lambda c: hasattr(c, "register_schema"),
            "version_manager": lambda c: hasattr(c, "get_current"),
            "retention_manager": lambda c: hasattr(c, "evaluate"),
            "lifecycle_manager": lambda c: hasattr(c, "get_stage"),
            "replay_engine": lambda c: hasattr(c, "replay"),
            "replay_scheduler": lambda c: hasattr(c, "submit"),
            "manifest_manager": lambda c: hasattr(c, "create_manifest"),
            "checksum_validator": lambda c: hasattr(c, "compute"),
            "lineage_tracker": lambda c: hasattr(c, "record_event"),
            "index_manager": lambda c: hasattr(c, "create_index"),
            "bloom_filter_manager": lambda c: hasattr(c, "get_or_create"),
        }

        probe = probe_methods.get(name)
        if probe is None:
            return True  # Unknown component, assume OK

        try:
            return probe(component)
        except Exception:
            return False

    # ── Probe Methods ─────────────────────────────────────────────

    async def check_all(self, probe_type: ProbeType = ProbeType.READINESS) -> DataLakeHealthReport:
        """Check health of all components."""
        tasks = [
            self._check_component(name, probe_type)
            for name in self.COMPONENTS
        ]
        components = await asyncio.gather(*tasks)

        report = DataLakeHealthReport(
            components=list(components),
            uptime_seconds=time.monotonic() - self._started_at,
        )

        # Compute overall status
        statuses = [c.status for c in report.components]
        if HealthStatus.UNHEALTHY in statuses:
            report.overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            report.overall_status = HealthStatus.DEGRADED
        elif HealthStatus.NOT_INITIALIZED in statuses:
            if probe_type == ProbeType.STARTUP:
                report.overall_status = HealthStatus.NOT_INITIALIZED
            else:
                report.overall_status = HealthStatus.DEGRADED
        else:
            report.overall_status = HealthStatus.HEALTHY

        healthy = sum(1 for c in components if c.status == HealthStatus.HEALTHY)
        degraded = sum(1 for c in components if c.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for c in components if c.status == HealthStatus.UNHEALTHY)

        report.details = {
            "healthy_count": healthy,
            "degraded_count": degraded,
            "unhealthy_count": unhealthy,
            "total_components": len(components),
            "circuits_open": sum(1 for c in components if c.circuit_open),
        }

        logger.info(
            "Health check [%s]: %s (%d healthy, %d degraded, %d unhealthy)",
            probe_type.value, report.overall_status.value,
            healthy, degraded, unhealthy,
        )
        return report

    async def liveness(self) -> DataLakeHealthReport:
        """Run liveness probe (binary: alive or not)."""
        return await self.check_all(ProbeType.LIVENESS)

    async def readiness(self) -> DataLakeHealthReport:
        """Run readiness probe (ready to serve traffic)."""
        return await self.check_all(ProbeType.READINESS)

    async def startup(self) -> DataLakeHealthReport:
        """Run startup probe (initialization complete)."""
        return await self.check_all(ProbeType.STARTUP)

    async def get_component_health(self, name: str) -> Optional[ComponentHealth]:
        """Get health status for a specific component."""
        return self._components.get(name)

    async def reset_circuit(self, name: str) -> bool:
        """Manually reset the circuit breaker for a component."""
        health = self._components.get(name)
        if health:
            health.circuit_open = False
            health.consecutive_failures = 0
            logger.info("Circuit manually reset for: %s", name)
            return True
        return False
