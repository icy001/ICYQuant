"""Scheduler Health — unified health checks for the scheduler engine.

Aggregates health reports from all scheduler subsystems:
* Engine state
* Registry integrity
* Runtime status
* Repository connectivity
* Event bus health
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .runtime.runtime_health import HealthStatus, HealthCheck, RuntimeHealthChecker


class SchedulerHealth:
    """Unified health checker for the scheduler engine.

    Aggregates health reports from all subsystems and exposes
    a single health endpoint for monitoring and alerting.

    Usage::

        health = SchedulerHealth()
        health.register_component("engine", engine)
        report = health.check_all()
    """

    def __init__(self) -> None:
        self._checker = RuntimeHealthChecker()
        self._components: Dict[str, Any] = {}

    def register_component(self, name: str, component: Any) -> None:
        """Register a scheduler component for health checking.

        The component must expose a `health_report() -> Dict` method.
        """
        self._components[name] = component

        # Auto-register a check that calls health_report()
        self._checker.register(name, lambda comp=component: _safe_health_report(comp))

    def unregister_component(self, name: str) -> None:
        """Remove a component from health checking."""
        self._components.pop(name, None)
        self._checker.unregister(name)

    def check_all(self) -> Dict[str, Any]:
        """Run all health checks and return aggregated results."""
        results = self._checker.run_all()
        overall = self._checker.overall_status()

        component_reports: Dict[str, Any] = {}
        for name, component in self._components.items():
            try:
                report = _safe_health_report(component)
                component_reports[name] = report
            except Exception as exc:
                component_reports[name] = {"error": str(exc)}

        return {
            "status": overall.value,
            "timestamp": results[0].checked_at.isoformat() if results else None,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "duration_ms": c.duration_ms,
                }
                for c in results
            ],
            "components": component_reports,
        }

    def quick_status(self) -> HealthStatus:
        """Return a quick status without running full checks."""
        self._checker.run_all()
        return self._checker.overall_status()

    def health_report(self) -> Dict[str, Any]:
        """Produce a comprehensive health report."""
        return self.check_all()


def _safe_health_report(component: Any) -> Dict[str, Any]:
    """Safely call health_report() on a component."""
    if hasattr(component, "health_report"):
        try:
            result = component.health_report()
            if isinstance(result, dict):
                return result
            return {"result": str(result)}
        except Exception as exc:
            return {"error": str(exc)}
    return {"warning": "no health_report method"}
