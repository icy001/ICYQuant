"""Integration Health — aggregated health checking for all platform integrations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


class IntegrationHealthChecker:
    """Aggregates health status across all integration adapters."""

    def __init__(self) -> None:
        self._last_check: str = ""

    async def check_all(self, integration_manager) -> Dict[str, Any]:
        """Run all health checks and return aggregated report."""
        self._last_check = datetime.utcnow().isoformat()
        adapters = integration_manager.list_adapters()
        report = integration_manager.health_report()

        all_healthy = all(adapters.values())

        return {
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": self._last_check,
            "adapters": adapters,
            "details": report,
        }
