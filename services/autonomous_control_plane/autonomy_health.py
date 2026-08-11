"""
Autonomy Health — Health monitoring for the autonomy subsystem.
"""

from __future__ import annotations

import time
import logging

logger = logging.getLogger(__name__)


class AutonomyHealth:
    def __init__(self):
        self._last_check = 0.0
        self._status = "HEALTHY"

    async def check(self) -> dict:
        self._last_check = time.time()
        return {"status": self._status, "timestamp": self._last_check}

    def set_status(self, status: str):
        self._status = status
