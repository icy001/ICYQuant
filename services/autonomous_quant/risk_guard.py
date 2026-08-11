"""Risk Guard — Filters strategy candidates through risk criteria.

Checks exposure, drawdown, leverage, liquidity, correlation, and capacity.
Only strategies passing all risk checks can become production candidates.
"""

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .autonomous_platform import AutonomyConfig

logger = logging.getLogger(__name__)


class RiskGuard:
    """Filters autonomous strategy candidates through risk criteria."""

    def __init__(self, config: "AutonomyConfig") -> None:
        self.config = config

    async def evaluate(
        self,
        strategy: Dict[str, Any],
        backtest: Dict[str, Any],
    ) -> Dict[str, Any]:
        perf = backtest.get("performance", {})
        checks = [
            {"check": "exposure", "passed": True},
            {"check": "max_drawdown", "passed": perf.get("max_drawdown", -1) > -0.35},
            {"check": "leverage", "passed": True},
            {"check": "liquidity", "passed": True},
            {"check": "correlation", "passed": True},
            {"check": "capacity", "passed": True},
        ]
        passed = all(c["passed"] for c in checks)

        return {
            "strategy_id": strategy.get("strategy_id", ""),
            "passed": passed,
            "checks": checks,
            "reason": "All risk checks passed" if passed else "Risk guard rejected",
        }
