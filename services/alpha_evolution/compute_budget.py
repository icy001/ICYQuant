"""Compute Budget — Tracks and limits compute resource usage during evolution."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ComputeBudget:
    """Tracks and enforces compute resource limits."""

    def __init__(
        self,
        max_backtests: int = 50000,
        max_compute_hours: float = 72.0,
        max_gpu_hours: float = 8.0,
        max_memory_gb: float = 64.0,
    ):
        self._max_backtests = max_backtests
        self._max_compute_hours = max_compute_hours
        self._max_gpu_hours = max_gpu_hours
        self._max_memory_gb = max_memory_gb

        self._backtests_used = 0
        self._compute_hours_used = 0.0
        self._gpu_hours_used = 0.0
        self._started_at: Optional[datetime] = None

    async def start(self) -> None:
        self._started_at = datetime.now(timezone.utc)

    async def consume_backtest(self, count: int = 1) -> bool:
        if self._backtests_used + count > self._max_backtests:
            return False
        self._backtests_used += count
        return True

    async def consume_compute(self, hours: float) -> bool:
        if self._compute_hours_used + hours > self._max_compute_hours:
            return False
        self._compute_hours_used += hours
        return True

    async def is_exhausted(self) -> bool:
        return (
            self._backtests_used >= self._max_backtests
            or self._compute_hours_used >= self._max_compute_hours
            or self._gpu_hours_used >= self._max_gpu_hours
        )

    def get_usage(self) -> Dict[str, Any]:
        return {
            "backtests": {
                "used": self._backtests_used,
                "max": self._max_backtests,
                "remaining": self._max_backtests - self._backtests_used,
            },
            "compute_hours": {
                "used": self._compute_hours_used,
                "max": self._max_compute_hours,
                "remaining": max(0, self._max_compute_hours - self._compute_hours_used),
            },
            "gpu_hours": {
                "used": self._gpu_hours_used,
                "max": self._max_gpu_hours,
            },
        }

    def reset(self) -> None:
        self._backtests_used = 0
        self._compute_hours_used = 0.0
        self._gpu_hours_used = 0.0
        self._started_at = None
