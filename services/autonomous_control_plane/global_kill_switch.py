"""
Global Kill Switch — System-wide emergency shutdown.

Highest-level safety: stops all new autonomous orders, freezes
strategy promotion, portfolio rebalance, and autonomous execution.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GlobalKillSwitch:
    """
    Global kill switch for the autonomous system.

    When activated:
        - STOP all new autonomous orders
        - Freeze strategy promotion
        - Freeze portfolio rebalance
        - Freeze autonomous execution
        - Enter Recovery Controller

    Requires manual reset to reactivate.
    """

    def __init__(self, requires_manual_reset: bool = True):
        self._activated: bool = False
        self._requires_manual_reset = requires_manual_reset
        self._activation_history: list[dict] = []
        self._activation_count = 0
        self._check_count = 0

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    async def activate_kill_switch(self, reason: str) -> None:
        """Activate the global kill switch."""
        self._activated = True
        self._activation_count += 1
        self._activation_history.append({
            "action": "activate",
            "reason": reason,
            "timestamp": time.time(),
        })
        logger.critical("GLOBAL KILL SWITCH ACTIVATED: %s", reason)

    def deactivate(self) -> bool:
        """Deactivate the kill switch (manual reset required)."""
        if self._requires_manual_reset:
            logger.info("Kill switch deactivated manually")
        self._activated = False
        self._activation_history.append({
            "action": "deactivate",
            "timestamp": time.time(),
        })
        return True

    # ------------------------------------------------------------------
    # Check
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self._activated

    async def check(self, context) -> object:
        """Check if kill switch is active."""
        from .decision_result import DecisionResult

        self._check_count += 1

        if self._activated:
            return DecisionResult.halted("Global kill switch active")

        return DecisionResult.allowed_result()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "activated": self._activated,
            "activation_count": self._activation_count,
            "total_checks": self._check_count,
            "requires_manual_reset": self._requires_manual_reset,
        }
