"""Budget Controller — Enforces compute/research budget constraints.

Prevents autonomous system from consuming unlimited compute resources.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .autonomous_platform import AutonomyConfig

logger = logging.getLogger(__name__)


class BudgetController:
    """Controls compute budget for autonomous research."""

    def __init__(self, config: "AutonomyConfig") -> None:
        self.config = config
        self._daily_backtests: int = 0
        self._daily_experiments: int = 0
        self._daily_hypotheses: int = 0
        self._last_reset: datetime = datetime.now(timezone.utc)

    async def can_run_cycle(self) -> bool:
        self._maybe_reset_daily()
        if self._daily_backtests >= self.config.max_daily_backtests:
            logger.warning("Daily backtest budget exceeded")
            return False
        return True

    async def consume_backtest(self) -> None:
        self._daily_backtests += 1

    async def consume_experiment(self) -> None:
        self._daily_experiments += 1

    async def consume_hypothesis(self) -> None:
        self._daily_hypotheses += 1

    def _maybe_reset_daily(self) -> None:
        now = datetime.now(timezone.utc)
        if (now - self._last_reset).total_seconds() > 86400:
            self._daily_backtests = 0
            self._daily_experiments = 0
            self._daily_hypotheses = 0
            self._last_reset = now

    def remaining(self) -> Dict[str, int]:
        self._maybe_reset_daily()
        return {
            "backtests": max(0, self.config.max_daily_backtests - self._daily_backtests),
            "experiments": max(0, self.config.max_daily_experiments - self._daily_experiments),
            "hypotheses": max(0, self.config.max_daily_hypotheses - self._daily_hypotheses),
        }

    async def health(self) -> Dict[str, Any]:
        return {"remaining": self.remaining(), "consumed": {"backtests": self._daily_backtests, "experiments": self._daily_experiments, "hypotheses": self._daily_hypotheses}}
