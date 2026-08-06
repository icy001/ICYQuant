"""Integration Health — aggregated health checks for the platform integration layer.

The :class:`IntegrationHealth` aggregates health reports from all
platform adapters into a single status for monitoring dashboards.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class IntegrationHealth:
    """Aggregated health checker for the platform integration layer.

    Checks:
    * Workflow adapter health
    * EventBus adapter health
    * Service mesh connectivity
    * Configuration center health
    * Business adapter health
    * Dashboard API availability

    Usage::

        health = IntegrationHealth()
        status = health.check(adapters={
            "workflow": wf_adapter,
            "eventbus": eb_adapter,
            ...
        })
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._check_count: int = 0
        self._last_status: Optional[Dict[str, Any]] = None
        self._last_check_at: Optional[datetime] = None

    @property
    def check_count(self) -> int:
        return self._check_count

    @property
    def last_status(self) -> Optional[Dict[str, Any]]:
        return self._last_status

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    def check(self, adapters: Dict[str, Any]) -> Dict[str, Any]:
        """Run a health check across all adapters.

        Args:
            adapters: Dict of adapter_name → adapter_instance

        Returns:
            Aggregated health status with per-component details
        """
        self._check_count += 1
        self._last_check_at = datetime.now(timezone.utc)

        components = {}
        overall = self.HEALTHY

        # Infrastructure
        infra_checks = ["service_mesh", "configuration", "discovery", "secrets", "feature_flag"]
        for name in infra_checks:
            components[name] = self._check_adapter(name, adapters.get(name))

        # Observability
        obs_checks = ["telemetry", "tracing", "metrics"]
        for name in obs_checks:
            components[name] = self._check_adapter(name, adapters.get(name))

        # Integration
        int_checks = ["workflow", "eventbus"]
        for name in int_checks:
            components[name] = self._check_adapter(name, adapters.get(name))

        # Business
        biz_checks = ["strategy", "ai", "research", "market_data", "order", "risk", "execution", "settlement", "ledger"]
        for name in biz_checks:
            components[name] = self._check_adapter(name, adapters.get(name))

        # Interfaces
        components["dashboard"] = self._check_adapter("dashboard", adapters.get("dashboard"))
        components["notification"] = self._check_adapter("notification", adapters.get("notification"))

        # Determine overall status
        statuses = [c["status"] for c in components.values()]
        if self.UNHEALTHY in statuses:
            overall = self.UNHEALTHY
        elif self.DEGRADED in statuses or self.UNKNOWN in statuses:
            overall = self.DEGRADED

        result = {
            "status": overall,
            "timestamp": self._last_check_at.isoformat(),
            "components": components,
            "summary": {
                "healthy": statuses.count(self.HEALTHY),
                "degraded": statuses.count(self.DEGRADED),
                "unhealthy": statuses.count(self.UNHEALTHY),
                "unknown": statuses.count(self.UNKNOWN),
            },
        }

        self._last_status = result
        return result

    def quick_check(self, adapters: Dict[str, Any]) -> str:
        """Quick overall health check (returns status string)."""
        result = self.check(adapters)
        return result["status"]

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _check_adapter(name: str, adapter: Any) -> Dict[str, Any]:
        """Check health of a single adapter."""
        if adapter is None:
            return {"name": name, "status": IntegrationHealth.UNKNOWN, "message": "not configured"}

        connected = getattr(adapter, "_connected", None)
        state = getattr(adapter, "_state", None)

        if connected is False:
            return {"name": name, "status": IntegrationHealth.UNHEALTHY, "message": "disconnected"}
        if state is not None:
            state_str = str(state) if hasattr(state, "value") else str(state)
            if "error" in state_str.lower():
                return {"name": name, "status": IntegrationHealth.UNHEALTHY, "message": state_str}
            if "degraded" in state_str.lower():
                return {"name": name, "status": IntegrationHealth.DEGRADED, "message": state_str}
        if connected is True:
            return {"name": name, "status": IntegrationHealth.HEALTHY, "message": "connected"}

        return {"name": name, "status": IntegrationHealth.UNKNOWN, "message": "unknown state"}
