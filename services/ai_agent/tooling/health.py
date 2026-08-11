"""Tool Health Checker — component-level health monitoring for the tooling subsystem.

Checks:
    - Tool Registry health
    - Tool Catalog health
    - Tool Runtime health
    - Tool Executor health
    - Permission Manager health
    - Policy Engine health
    - Sandbox health
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Enums ──

class HealthStatus(str, Enum):
    """Component health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# ── ComponentHealth ──

@dataclass
class ComponentHealth:
    """Health status of a single component."""

    component: str
    status: HealthStatus = HealthStatus.UNKNOWN
    details: str = ""
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = 0.0
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "component": self.component,
            "status": self.status.value,
            "details": self.details,
            "last_checked": self.last_checked.isoformat(),
            "latency_ms": round(self.latency_ms, 2),
            "error": self.error,
            "metrics": self.metrics,
        }


# ── HealthReport ──

@dataclass
class HealthReport:
    """Aggregated health report for the tooling subsystem."""

    overall_status: HealthStatus = HealthStatus.UNKNOWN
    components: List[ComponentHealth] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_latency_ms: float = 0.0

    @property
    def is_healthy(self) -> bool:
        return self.overall_status == HealthStatus.HEALTHY

    @property
    def unhealthy_components(self) -> List[ComponentHealth]:
        return [c for c in self.components if c.status == HealthStatus.UNHEALTHY]

    @property
    def degraded_components(self) -> List[ComponentHealth]:
        return [c for c in self.components if c.status == HealthStatus.DEGRADED]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "overall_status": self.overall_status.value,
            "is_healthy": self.is_healthy,
            "components": [c.to_dict() for c in self.components],
            "unhealthy_count": len(self.unhealthy_components),
            "degraded_count": len(self.degraded_components),
            "generated_at": self.generated_at.isoformat(),
            "total_latency_ms": round(self.total_latency_ms, 2),
        }


# ── ToolHealthChecker ──

class ToolHealthChecker:
    """Component-level health checker for the tooling subsystem.

    Periodically checks the health of all tooling components
    (registry, catalog, runtime, executor, permission, policy,
    sandbox) and produces a comprehensive health report.

    Supports:
        - Per-component health checks
        - Aggregated health report
        - Degradation detection
        - Health history

    Usage:
        checker = ToolHealthChecker(registry, catalog, runtime)
        report = await checker.check_all()
        if not report.is_healthy:
            logger.warning(f"Unhealthy components: {report.unhealthy_components}")
    """

    def __init__(
        self,
        registry: Any = None,
        catalog: Any = None,
        runtime: Any = None,
        executor: Any = None,
        permission_manager: Any = None,
        policy_engine: Any = None,
        sandbox: Any = None,
    ) -> None:
        """Initialize the health checker.

        Args:
            registry: ToolRegistry instance.
            catalog: ToolCatalog instance.
            runtime: ToolRuntime instance.
            executor: ToolExecutor instance.
            permission_manager: ToolPermissionManager instance.
            policy_engine: ToolPolicyEngine instance.
            sandbox: ToolSandbox instance.
        """
        self._components: Dict[str, Any] = {
            "registry": registry,
            "catalog": catalog,
            "runtime": runtime,
            "executor": executor,
            "permission_manager": permission_manager,
            "policy_engine": policy_engine,
            "sandbox": sandbox,
        }
        self._history: List[HealthReport] = []
        self._max_history: int = 100

        self._initialized: bool = False
        logger.info("ToolHealthChecker created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the health checker."""
        self._initialized = True
        logger.info("ToolHealthChecker initialized")

    async def shutdown(self) -> None:
        """Shutdown the health checker."""
        self._history.clear()
        self._initialized = False
        logger.info("ToolHealthChecker shutdown complete")

    # ── Health Checks ──

    async def check_all(self) -> HealthReport:
        """Run health checks on all components.

        Returns:
            A comprehensive HealthReport.
        """
        start = time.monotonic()
        components: List[ComponentHealth] = []

        # Check each component
        components.append(await self._check_registry())
        components.append(await self._check_catalog())
        components.append(await self._check_runtime())
        components.append(await self._check_executor())
        components.append(await self._check_permissions())
        components.append(await self._check_policy())
        components.append(await self._check_sandbox())

        # Determine overall status
        unhealthy = [c for c in components if c.status == HealthStatus.UNHEALTHY]
        degraded = [c for c in components if c.status == HealthStatus.DEGRADED]

        if unhealthy:
            overall = HealthStatus.UNHEALTHY
        elif degraded:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        total_latency = (time.monotonic() - start) * 1000

        report = HealthReport(
            overall_status=overall,
            components=components,
            total_latency_ms=total_latency,
        )

        self._history.append(report)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        logger.info(
            f"Health check complete: {overall.value} "
            f"({len(unhealthy)} unhealthy, {len(degraded)} degraded, "
            f"{total_latency:.1f}ms)"
        )

        return report

    async def check_component(self, component_name: str) -> Optional[ComponentHealth]:
        """Check health of a specific component.

        Args:
            component_name: The component to check.

        Returns:
            ComponentHealth or None if component not found.
        """
        check_map = {
            "registry": self._check_registry,
            "catalog": self._check_catalog,
            "runtime": self._check_runtime,
            "executor": self._check_executor,
            "permission_manager": self._check_permissions,
            "policy_engine": self._check_policy,
            "sandbox": self._check_sandbox,
        }
        checker = check_map.get(component_name)
        if checker:
            return await checker()
        return None

    # ── Individual Checks ──

    async def _check_registry(self) -> ComponentHealth:
        """Check registry health."""
        registry = self._components.get("registry")
        if registry is None:
            return ComponentHealth(
                component="registry",
                status=HealthStatus.UNKNOWN,
                details="No registry configured",
            )

        try:
            count = getattr(registry, "count", 0)
            active = getattr(registry, "active_count", 0)

            if count == 0:
                return ComponentHealth(
                    component="registry",
                    status=HealthStatus.DEGRADED,
                    details="No tools registered",
                    metrics={"total_tools": 0, "active_tools": 0},
                )
            return ComponentHealth(
                component="registry",
                status=HealthStatus.HEALTHY,
                details=f"{active}/{count} tools active",
                metrics={"total_tools": count, "active_tools": active},
            )
        except Exception as e:
            return ComponentHealth(
                component="registry",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )

    async def _check_catalog(self) -> ComponentHealth:
        """Check catalog health."""
        catalog = self._components.get("catalog")
        if catalog is None:
            return ComponentHealth(
                component="catalog",
                status=HealthStatus.UNKNOWN,
                details="No catalog configured",
            )

        try:
            entries = getattr(catalog, "entry_count", 0)
            categories = getattr(catalog, "category_count", 0)
            return ComponentHealth(
                component="catalog",
                status=HealthStatus.HEALTHY,
                details=f"{entries} entries in {categories} categories",
                metrics={"entries": entries, "categories": categories},
            )
        except Exception as e:
            return ComponentHealth(
                component="catalog",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )

    async def _check_runtime(self) -> ComponentHealth:
        """Check runtime health."""
        runtime = self._components.get("runtime")
        if runtime is None:
            return ComponentHealth(
                component="runtime",
                status=HealthStatus.UNKNOWN,
                details="No runtime configured",
            )

        try:
            active = getattr(runtime, "active_count", 0)
            at_capacity = getattr(runtime, "is_at_capacity", False)
            status = HealthStatus.DEGRADED if at_capacity else HealthStatus.HEALTHY
            return ComponentHealth(
                component="runtime",
                status=status,
                details=f"{active} active executions" + (" (at capacity)" if at_capacity else ""),
                metrics={"active_executions": active, "at_capacity": at_capacity},
            )
        except Exception as e:
            return ComponentHealth(
                component="runtime",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )

    async def _check_executor(self) -> ComponentHealth:
        """Check executor health."""
        executor = self._components.get("executor")
        if executor is None:
            return ComponentHealth(
                component="executor",
                status=HealthStatus.UNKNOWN,
                details="No executor configured",
            )

        try:
            observers = len(getattr(executor, "_observers", []))
            return ComponentHealth(
                component="executor",
                status=HealthStatus.HEALTHY,
                details=f"{observers} observers attached",
                metrics={"observers": observers},
            )
        except Exception as e:
            return ComponentHealth(
                component="executor",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )

    async def _check_permissions(self) -> ComponentHealth:
        """Check permission manager health."""
        pm = self._components.get("permission_manager")
        if pm is None:
            return ComponentHealth(
                component="permission_manager",
                status=HealthStatus.UNKNOWN,
                details="No permission manager configured",
            )

        try:
            roles = len(getattr(pm, "_roles", {}))
            policies = len(getattr(pm, "_policies", []))
            return ComponentHealth(
                component="permission_manager",
                status=HealthStatus.HEALTHY,
                details=f"{roles} roles, {policies} policies",
                metrics={"roles": roles, "policies": policies},
            )
        except Exception as e:
            return ComponentHealth(
                component="permission_manager",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )

    async def _check_policy(self) -> ComponentHealth:
        """Check policy engine health."""
        pe = self._components.get("policy_engine")
        if pe is None:
            return ComponentHealth(
                component="policy_engine",
                status=HealthStatus.UNKNOWN,
                details="No policy engine configured",
            )

        try:
            policies = len(getattr(pe, "_policies", {}))
            enabled = sum(1 for p in getattr(pe, "_policies", {}).values() if getattr(p, "enabled", False))
            return ComponentHealth(
                component="policy_engine",
                status=HealthStatus.HEALTHY,
                details=f"{enabled}/{policies} policies enabled",
                metrics={"total_policies": policies, "enabled": enabled},
            )
        except Exception as e:
            return ComponentHealth(
                component="policy_engine",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )

    async def _check_sandbox(self) -> ComponentHealth:
        """Check sandbox health."""
        sandbox = self._components.get("sandbox")
        if sandbox is None:
            return ComponentHealth(
                component="sandbox",
                status=HealthStatus.UNKNOWN,
                details="No sandbox configured",
            )

        try:
            mode = getattr(sandbox._config, "mode", None)
            mode_str = mode.value if hasattr(mode, "value") else str(mode)
            return ComponentHealth(
                component="sandbox",
                status=HealthStatus.HEALTHY,
                details=f"Sandbox active in {mode_str} mode",
                metrics={"mode": mode_str},
            )
        except Exception as e:
            return ComponentHealth(
                component="sandbox",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )

    # ── History ──

    def get_history(self, limit: int = 10) -> List[HealthReport]:
        """Get health check history.

        Args:
            limit: Maximum results.

        Returns:
            List of recent health reports.
        """
        return self._history[-limit:]

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get health checker status."""
        configured = [name for name, comp in self._components.items() if comp is not None]
        return {
            "configured_components": configured,
            "unconfigured_components": [
                name for name, comp in self._components.items() if comp is None
            ],
            "history_count": len(self._history),
            "initialized": self._initialized,
        }
