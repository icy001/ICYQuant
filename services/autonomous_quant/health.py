"""Autonomous Quant Health — Health check endpoints."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)


class AutonomyHealth:
    """Health check service for the autonomous quant platform."""

    def __init__(self) -> None:
        self._start_time: datetime = datetime.now(timezone.utc)
        self._healthy: bool = True

    async def check(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._healthy else "degraded",
            "uptime_seconds": (datetime.now(timezone.utc) - self._start_time).total_seconds(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "0.4.0-alpha2",
            "components": {
                "scanner": self._healthy,
                "discovery": self._healthy,
                "hypothesis": self._healthy,
                "factor_miner": self._healthy,
                "alpha_discovery": self._healthy,
                "strategy_generator": self._healthy,
                "backtest": self._healthy,
                "registry": self._healthy,
            },
        }

    def set_healthy(self, healthy: bool) -> None:
        self._healthy = healthy
