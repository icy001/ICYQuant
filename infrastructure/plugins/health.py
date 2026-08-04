"""Plugin health checks.

Provides a unified health check interface for the ICYQuant plugin
framework, verifying the plugin registry, loader, dependency
resolution, and active plugin states.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a single health check probe."""

    name: str
    healthy: bool
    message: str
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the result to a dictionary."""
        return {
            "name": self.name,
            "healthy": self.healthy,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "details": dict(self.details),
        }


class PluginHealth:
    """Unified health check for the plugin system.

    Runs probes against the plugin registry, loader, dependency
    resolver, and active plugin states to produce an aggregate
    health report.
    """

    def __init__(self, registry: Any = None, loader: Any = None) -> None:
        self._registry = registry
        self._loader = loader
        self._last_results: List[HealthCheckResult] = []
        self._last_check_time: float = 0.0

    async def check(self) -> Dict[str, Any]:
        """Run all health checks and return a combined result.

        Returns:
            Dictionary with overall health status and individual
            check results.
        """
        start = time.monotonic()
        results: List[HealthCheckResult] = []

        results.append(await self._check_registry())
        results.append(await self._check_loader())
        results.append(await self._check_dependencies())
        results.append(await self._check_active_plugins())

        overall_healthy = all(r.healthy for r in results)
        total_latency = (time.monotonic() - start) * 1000.0

        self._last_results = results
        self._last_check_time = time.time()

        return {
            "healthy": overall_healthy,
            "timestamp": self._last_check_time,
            "total_latency_ms": total_latency,
            "checks": [r.to_dict() for r in results],
            "summary": {
                "total": len(results),
                "healthy_count": sum(1 for r in results if r.healthy),
                "unhealthy_count": sum(
                    1 for r in results if not r.healthy
                ),
            },
        }

    async def _check_registry(self) -> HealthCheckResult:
        """Check the plugin registry for availability and integrity."""
        check_start = time.monotonic()
        try:
            if self._registry is None:
                return HealthCheckResult(
                    name="registry",
                    healthy=True,
                    message="No registry configured; skipping.",
                    latency_ms=(time.monotonic() - check_start) * 1000.0,
                )
            plugin_count = 0
            method = getattr(self._registry, "count", None)
            if callable(method):
                plugin_count = method()
            list_method = getattr(self._registry, "list_ids", None)
            plugin_ids: List[str] = []
            if callable(list_method):
                plugin_ids = list_method()
            return HealthCheckResult(
                name="registry",
                healthy=True,
                message=f"Registry accessible; {plugin_count} plugins registered.",
                latency_ms=(time.monotonic() - check_start) * 1000.0,
                details={
                    "plugin_count": plugin_count,
                    "plugin_ids": plugin_ids[:20],
                },
            )
        except Exception as e:
            logger.error("Registry health check failed: %s", e)
            return HealthCheckResult(
                name="registry",
                healthy=False,
                message=f"Registry check failed: {e}",
                latency_ms=(time.monotonic() - check_start) * 1000.0,
                details={"error": str(e)},
            )

    async def _check_loader(self) -> HealthCheckResult:
        """Check the plugin loader for availability and integrity."""
        check_start = time.monotonic()
        try:
            if self._loader is None:
                return HealthCheckResult(
                    name="loader",
                    healthy=True,
                    message="No loader configured; skipping.",
                    latency_ms=(time.monotonic() - check_start) * 1000.0,
                )
            get_stats = getattr(self._loader, "get_stats", None)
            stats: Dict[str, Any] = {}
            if callable(get_stats):
                stats = get_stats()
            return HealthCheckResult(
                name="loader",
                healthy=True,
                message="Loader accessible; ready to load plugins.",
                latency_ms=(time.monotonic() - check_start) * 1000.0,
                details={"loader_stats": stats},
            )
        except Exception as e:
            logger.error("Loader health check failed: %s", e)
            return HealthCheckResult(
                name="loader",
                healthy=False,
                message=f"Loader check failed: {e}",
                latency_ms=(time.monotonic() - check_start) * 1000.0,
                details={"error": str(e)},
            )

    async def _check_dependencies(self) -> HealthCheckResult:
        """Check dependency resolution for all registered plugins."""
        check_start = time.monotonic()
        try:
            if self._registry is None:
                return HealthCheckResult(
                    name="dependencies",
                    healthy=True,
                    message="No registry; skipping dependency check.",
                    latency_ms=(time.monotonic() - check_start) * 1000.0,
                )
            get_all = getattr(self._registry, "get_all", None)
            plugins: List[Any] = []
            if callable(get_all):
                plugins = get_all()
            missing_deps: List[Dict[str, str]] = []
            for plugin in plugins:
                plugin_id = getattr(plugin, "id", str(plugin))
                dependencies = getattr(plugin, "dependencies", [])
                if not dependencies:
                    continue
                for dep in dependencies:
                    has_method = getattr(self._registry, "has", None)
                    if callable(has_method) and not has_method(dep):
                        missing_deps.append(
                            {"plugin": plugin_id, "missing_dependency": dep}
                        )
            healthy = len(missing_deps) == 0
            return HealthCheckResult(
                name="dependencies",
                healthy=healthy,
                message=(
                    "All dependencies resolved."
                    if healthy
                    else f"{len(missing_deps)} missing dependencies found."
                ),
                latency_ms=(time.monotonic() - check_start) * 1000.0,
                details={
                    "plugin_count": len(plugins),
                    "missing_dependencies": missing_deps,
                },
            )
        except Exception as e:
            logger.error("Dependency health check failed: %s", e)
            return HealthCheckResult(
                name="dependencies",
                healthy=False,
                message=f"Dependency check failed: {e}",
                latency_ms=(time.monotonic() - check_start) * 1000.0,
                details={"error": str(e)},
            )

    async def _check_active_plugins(self) -> HealthCheckResult:
        """Check the state of active (RUNNING) plugins."""
        check_start = time.monotonic()
        try:
            if self._registry is None:
                return HealthCheckResult(
                    name="active_plugins",
                    healthy=True,
                    message="No registry; skipping active plugin check.",
                    latency_ms=(time.monotonic() - check_start) * 1000.0,
                )
            get_all = getattr(self._registry, "get_all", None)
            plugins: List[Any] = []
            if callable(get_all):
                plugins = get_all()

            active_count = 0
            failed_count = 0
            stopped_count = 0
            active_details: List[Dict[str, Any]] = []
            for plugin in plugins:
                plugin_id = getattr(plugin, "id", str(plugin))
                state = getattr(plugin, "state", None)
                state_str = state.value if hasattr(state, "value") else str(state)
                if state_str == "running":
                    active_count += 1
                    active_details.append(
                        {"plugin_id": plugin_id, "state": state_str}
                    )
                elif state_str == "failed":
                    failed_count += 1
                    active_details.append(
                        {
                            "plugin_id": plugin_id,
                            "state": state_str,
                            "error": getattr(plugin, "error", None),
                        }
                    )
                elif state_str == "stopped":
                    stopped_count += 1

            healthy = failed_count == 0
            return HealthCheckResult(
                name="active_plugins",
                healthy=healthy,
                message=(
                    f"{active_count} active, {failed_count} failed, "
                    f"{stopped_count} stopped."
                ),
                latency_ms=(time.monotonic() - check_start) * 1000.0,
                details={
                    "active_count": active_count,
                    "failed_count": failed_count,
                    "stopped_count": stopped_count,
                    "plugins": active_details,
                },
            )
        except Exception as e:
            logger.error("Active plugins health check failed: %s", e)
            return HealthCheckResult(
                name="active_plugins",
                healthy=False,
                message=f"Active plugin check failed: {e}",
                latency_ms=(time.monotonic() - check_start) * 1000.0,
                details={"error": str(e)},
            )

    def is_healthy(self) -> bool:
        """Return True if the last health check was fully healthy.

        Returns:
            True if all checks passed, False otherwise.
        """
        if not self._last_results:
            return False
        return all(r.healthy for r in self._last_results)

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics from the last health check.

        Returns:
            Dictionary with last check details and results.
        """
        return {
            "last_check_time": self._last_check_time,
            "total_checks": len(self._last_results),
            "healthy_checks": sum(
                1 for r in self._last_results if r.healthy
            ),
            "unhealthy_checks": sum(
                1 for r in self._last_results if not r.healthy
            ),
            "results": [r.to_dict() for r in self._last_results],
            "registry_available": self._registry is not None,
            "loader_available": self._loader is not None,
        }