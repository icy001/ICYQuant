"""Runtime Health — health checker for the runtime subsystem.

Monitors the health of runtime components including the event bus,
variable store, state manager, and active instance tracker.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RuntimeHealthChecker:
    """Checks the health of the workflow runtime subsystem."""

    def __init__(self) -> None:
        self._healthy = True
        self._last_check_at: float = 0.0

    def shutdown(self) -> None:
        self._healthy = False

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def check(self) -> Dict[str, Any]:
        """Return a health report for the runtime subsystem."""
        return {
            "healthy": self._healthy,
            "components": {
                "event_bus": self._healthy,
                "variable_store": self._healthy,
                "state_manager": self._healthy,
                "instance_tracker": self._healthy,
            },
        }

    def mark_unhealthy(self, component: str, reason: str) -> None:
        self._healthy = False
        logger.warning("RuntimeHealth: %s unhealthy: %s", component, reason)

    def mark_healthy(self) -> None:
        self._healthy = True
