"""Service discovery health checks.

Provides a unified health check interface for the ICYQuant service
discovery subsystem, verifying the registry, repository, resolver,
and backend adapter components and producing an aggregate health
report.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ComponentHealthResult:
    """Result of a single component health probe."""

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


class ServiceDiscoveryHealth:
    """Unified health check for the service discovery subsystem.

    Runs probes against the registry, repository, resolver, and
    backend adapter to produce an aggregate health report.

    Args:
        registry: Optional ``ServiceRegistry`` instance.
        repository: Optional ``ServiceRepository`` instance.
        resolver: Optional ``ServiceResolver`` instance.
        adapter: Optional ``RegistryAdapter`` instance.
    """

    def __init__(
        self,
        registry: Any = None,
        repository: Any = None,
        resolver: Any = None,
        adapter: Any = None,
    ) -> None:
        self._registry = registry
        self._repository = repository
        self._resolver = resolver
        self._adapter = adapter
        self._last_results: List[ComponentHealthResult] = []
        self._last_check_time: float = 0.0

    async def check(self) -> Dict[str, Any]:
        """Run all health checks and return a combined result.

        Returns:
            Dictionary with overall health status and individual
            component results.
        """
        start = time.monotonic()
        results: List[ComponentHealthResult] = [
            self._check_component("registry", self._registry),
            self._check_component("repository", self._repository),
            self._check_component("resolver", self._resolver),
            self._check_adapter(),
        ]

        overall_healthy = all(r.healthy for r in results)
        total_latency = (time.monotonic() - start) * 1000.0

        self._last_results = results
        self._last_check_time = time.time()

        return {
            "healthy": overall_healthy,
            "timestamp": self._last_check_time,
            "total_latency_ms": total_latency,
            "registry": results[0].healthy,
            "repository": results[1].healthy,
            "resolver": results[2].healthy,
            "adapter": results[3].healthy,
            "checks": [r.to_dict() for r in results],
            "summary": {
                "total": len(results),
                "healthy_count": sum(1 for r in results if r.healthy),
                "unhealthy_count": sum(1 for r in results if not r.healthy),
            },
        }

    def check_registry(self) -> Dict[str, Any]:
        """Check the service registry component."""
        return self._check_component("registry", self._registry).to_dict()

    def check_repository(self) -> Dict[str, Any]:
        """Check the service repository component."""
        return self._check_component("repository", self._repository).to_dict()

    def check_resolver(self) -> Dict[str, Any]:
        """Check the service resolver component."""
        return self._check_component("resolver", self._resolver).to_dict()

    def check_adapter(self) -> Dict[str, Any]:
        """Check the backend adapter component."""
        return self._check_adapter().to_dict()

    def is_healthy(self) -> bool:
        """Return True if the last health check was fully healthy."""
        if not self._last_results:
            return False
        return all(r.healthy for r in self._last_results)

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics from the last health check."""
        return {
            "last_check_time": self._last_check_time,
            "total_checks": len(self._last_results),
            "healthy_checks": sum(1 for r in self._last_results if r.healthy),
            "unhealthy_checks": sum(
                1 for r in self._last_results if not r.healthy
            ),
            "results": [r.to_dict() for r in self._last_results],
            "registry_available": self._registry is not None,
            "repository_available": self._repository is not None,
            "resolver_available": self._resolver is not None,
            "adapter_available": self._adapter is not None,
        }

    # ── Internal helpers ──

    def _check_component(
        self, name: str, component: Any
    ) -> ComponentHealthResult:
        """Run a defensive health probe against a component."""
        check_start = time.monotonic()
        try:
            if component is None:
                return ComponentHealthResult(
                    name=name,
                    healthy=True,
                    message=f"No {name} configured; skipping.",
                    latency_ms=(time.monotonic() - check_start) * 1000.0,
                )
            get_stats = getattr(component, "get_stats", None)
            stats: Dict[str, Any] = {}
            if callable(get_stats):
                stats = get_stats() or {}
            return ComponentHealthResult(
                name=name,
                healthy=True,
                message=f"{name.capitalize()} accessible.",
                latency_ms=(time.monotonic() - check_start) * 1000.0,
                details={"stats": stats},
            )
        except Exception as e:
            logger.error("%s health check failed: %s", name, e)
            return ComponentHealthResult(
                name=name,
                healthy=False,
                message=f"{name.capitalize()} check failed: {e}",
                latency_ms=(time.monotonic() - check_start) * 1000.0,
                details={"error": str(e)},
            )

    def _check_adapter(self) -> ComponentHealthResult:
        """Run a health probe against the backend adapter."""
        check_start = time.monotonic()
        try:
            if self._adapter is None:
                return ComponentHealthResult(
                    name="adapter",
                    healthy=True,
                    message="No adapter configured; skipping.",
                    latency_ms=(time.monotonic() - check_start) * 1000.0,
                )
            is_connected = getattr(self._adapter, "is_connected", None)
            connected = bool(is_connected()) if callable(is_connected) else True
            get_stats = getattr(self._adapter, "get_stats", None)
            stats: Dict[str, Any] = {}
            if callable(get_stats):
                stats = get_stats() or {}
            return ComponentHealthResult(
                name="adapter",
                healthy=connected,
                message=(
                    "Adapter connected."
                    if connected
                    else "Adapter is not connected."
                ),
                latency_ms=(time.monotonic() - check_start) * 1000.0,
                details={"connected": connected, "stats": stats},
            )
        except Exception as e:
            logger.error("Adapter health check failed: %s", e)
            return ComponentHealthResult(
                name="adapter",
                healthy=False,
                message=f"Adapter check failed: {e}",
                latency_ms=(time.monotonic() - check_start) * 1000.0,
                details={"error": str(e)},
            )
