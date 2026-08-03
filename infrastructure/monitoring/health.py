"""
Monitoring health aggregation.

Provides health check aggregation across
all infrastructure components, producing
a unified health status for the application.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .config import MonitoringConfig
from .models import HealthSnapshot


class MonitoringHealth:
    """
    Monitoring health aggregator.

    Collects and aggregates health status
    from all registered infrastructure
    components, producing a unified
    health view for the application.

    Usage:
        health = MonitoringHealth(config)
        health.register_checker("database", db_check)
        health.register_checker("redis", redis_check)
        result = await health.check()
    """

    def __init__(
        self,
        config: Optional[MonitoringConfig] = None,
    ) -> None:
        """
        Initialize monitoring health.

        Args:
            config: Monitoring configuration.
        """

        self._config = config or MonitoringConfig()
        self._checkers: Dict[str, Callable] = {}
        self._last_result: Optional[HealthSnapshot] = None

    def register_checker(
        self,
        name: str,
        checker: Callable,
    ) -> None:
        """
        Register a health checker.

        Args:
            name: Component name.
            checker: Async callable returning health status.
        """

        self._checkers[name] = checker

    def unregister_checker(
        self,
        name: str,
    ) -> None:
        """
        Remove a health checker.

        Args:
            name: Component name.
        """

        self._checkers.pop(name, None)

    async def check(
        self,
    ) -> Dict[str, Any]:
        """
        Perform aggregated health check.

        Returns:
            Health status dictionary with
            overall health and per-component
            details.
        """

        components: Dict[str, Any] = {}
        all_healthy = True

        for name, checker in self._checkers.items():
            try:
                result = checker()
                if hasattr(result, "__await__"):
                    result = await result

                components[name] = result
                if isinstance(result, dict):
                    if not result.get("healthy", False):
                        all_healthy = False
                elif isinstance(result, tuple):
                    healthy, _ = result
                    components[name] = {"healthy": healthy}
                    if not healthy:
                        all_healthy = False
                elif isinstance(result, bool):
                    components[name] = {"healthy": result}
                    if not result:
                        all_healthy = False
                else:
                    components[name] = {
                        "healthy": True,
                        "raw": str(result),
                    }
            except Exception as exc:
                components[name] = {
                    "healthy": False,
                    "error": str(exc),
                }
                all_healthy = False

        self._last_result = HealthSnapshot(
            healthy=all_healthy,
            components=components,
        )

        return self._last_result.to_dict()

    @property
    def last_result(
        self,
    ) -> Optional[HealthSnapshot]:
        """Get last health check result."""
        return self._last_result

    @property
    def checker_count(
        self,
    ) -> int:
        """Get number of registered checkers."""
        return len(self._checkers)

    def get_checker_names(
        self,
    ) -> List[str]:
        """Get list of checker names."""
        return list(self._checkers.keys())

    def is_component_healthy(
        self,
        name: str,
    ) -> Optional[bool]:
        """
        Check if a specific component is healthy.

        Args:
            name: Component name.

        Returns:
            Health status or None if unknown.
        """

        if self._last_result is None:
            return None

        component = self._last_result.components.get(name)
        if component is None:
            return None

        if isinstance(component, dict):
            return component.get("healthy", False)
        return None
