"""Workflow Health — health check for workflow engine components.

Provides a unified health check for all workflow sub-systems:
* Workflow Engine
* Runtime
* Repository
* Registry
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Health status for a single component."""

    component: str
    healthy: bool
    message: str = ""
    checked_at: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "healthy": self.healthy,
            "message": self.message,
            "checked_at": self.checked_at.isoformat(),
            "details": self.details,
        }


class WorkflowHealthChecker:
    """Aggregates health checks for all workflow engine components."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._components: Dict[str, Any] = {}
        self._last_check: Optional[datetime] = None

    def register_component(self, name: str, component: Any) -> None:
        """Register a component for health checking."""
        with self._lock:
            self._components[name] = component

    def check_all(self) -> Dict[str, Any]:
        """Run health checks on all registered components."""
        with self._lock:
            results: Dict[str, HealthStatus] = {}
            all_healthy = True

            for name, component in self._components.items():
                status = self._check_component(name, component)
                results[name] = status
                if not status.healthy:
                    all_healthy = False

            self._last_check = datetime.utcnow()

            return {
                "healthy": all_healthy,
                "checked_at": self._last_check.isoformat(),
                "components": {
                    name: status.to_dict()
                    for name, status in results.items()
                },
            }

    def _check_component(self, name: str, component: Any) -> HealthStatus:
        """Check a single component's health."""
        try:
            if hasattr(component, "health_report"):
                report = component.health_report()
                return HealthStatus(
                    component=name,
                    healthy=report.get("is_ready", report.get("healthy", True)),
                    message="OK",
                    details=report,
                )
            elif hasattr(component, "is_ready"):
                ready = component.is_ready
                return HealthStatus(
                    component=name,
                    healthy=ready if isinstance(ready, bool) else True,
                    message="OK" if ready else "Not ready",
                )
            else:
                return HealthStatus(
                    component=name,
                    healthy=True,
                    message="OK (no health check available)",
                )
        except Exception as exc:
            logger.warning("Health check failed for %s: %s", name, exc)
            return HealthStatus(
                component=name,
                healthy=False,
                message=str(exc),
            )

    def get_last_check(self) -> Optional[datetime]:
        with self._lock:
            return self._last_check
