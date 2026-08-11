"""
Health — Unified health endpoint for the Control Plane.

Aggregates health information from all sub-engines and domains.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Health:
    """
    Unified health check for the Control Plane.

    Aggregates health signals from all engines and provides a single
    health status endpoint.
    """

    def __init__(self):
        self._last_check: float = 0.0
        self._status: str = "HEALTHY"
        self._checks: dict[str, bool] = {}

    async def check(self) -> dict:
        """Run all health checks."""
        self._last_check = time.time()
        return {
            "status": self._status,
            "timestamp": self._last_check,
            "checks": self._checks,
        }

    def set_component_health(self, component: str, healthy: bool):
        """Update the health of a specific component."""
        self._checks[component] = healthy
        if not healthy:
            self._status = "DEGRADED"

    def stats(self) -> dict:
        return {
            "status": self._status,
            "last_check": self._last_check,
            "components": self._checks,
        }
